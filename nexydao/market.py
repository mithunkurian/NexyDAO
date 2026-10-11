"""Operator-only, bounded paper quote collection. No order messages or agent tools.

Protocol layout checked against official IBKR Python API 10.51.01 source.
Only legacy server protocol 178 is supported. Signed receipts attest local
collection integrity, not broker signatures or the validity of investment claims.
"""
import hashlib
import hmac
import json
import os
import re
import socket
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .ibkr import BrokerConfig, ProbeError, Wire, check_error, paper_account, save_snapshot

CONTRACT_REQUEST = 9201
QUOTE_REQUEST = 9202
MAX_AGE = 60
SOURCE = "ibkr_paper_tick_by_tick_bid_ask"


@dataclass(frozen=True)
class MarketConfig:
    broker: BrokerConfig
    key_path: Path
    symbol: str = "SPY"
    snapshot: Path = Path("data/market-quote.json")

    def __post_init__(self):
        if not self.broker.expected_account:
            raise ValueError("Exact paper-account pin required for market collection")
        if not re.fullmatch(r"[A-Z][A-Z0-9.]{0,11}", self.symbol):
            raise ValueError("Invalid US equity symbol")

    @classmethod
    def from_env(cls):
        key = os.environ.get("NEXYDAO_EVIDENCE_KEY_FILE", "")
        if not key:
            raise ValueError("Private evidence key file required")
        return cls(BrokerConfig.from_env(), Path(key),
                   os.environ.get("NEXYDAO_MARKET_SYMBOL", "SPY"),
                   Path(os.environ.get("NEXYDAO_MARKET_SNAPSHOT", "data/market-quote.json")))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_key(path):
    # Windows ACLs must be provisioned by the operator; Unix modes are enforceable here.
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise ValueError("Evidence key must have private file permissions")
    with path.open("rb") as f:
        key = f.read(33)
    if len(key) != 32:
        raise ValueError("Evidence key must be exactly 32 random bytes")
    return key


def positive(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,16}(?:\.[0-9]{1,12})?", value):
        raise ProbeError("invalid_quote_number")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ProbeError("invalid_quote_number") from None
    if not result.is_finite() or result <= 0:
        raise ProbeError("invalid_quote_number")
    return result


def validate_payload(payload, expected_account, now=None):
    now = time.time() if now is None else now
    keys = {"schema_version", "source", "protocol_version", "account_sha256", "contract",
            "quote", "received_at", "expires_at", "raw_sha256"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ProbeError("invalid_evidence_schema")
    if (type(payload['schema_version']) is not int or payload['schema_version'] != 1
            or payload['source'] != SOURCE or type(payload['protocol_version']) is not int
            or payload['protocol_version'] != 178):
        raise ProbeError("unsupported_evidence_source")
    if not expected_account or payload['account_sha256'] != hashlib.sha256(expected_account.encode()).hexdigest():
        raise ProbeError("evidence_account_mismatch")
    contract = payload['contract']
    if not isinstance(contract, dict) or set(contract) != {'con_id', 'symbol', 'security_type', 'currency', 'exchange', 'primary_exchange'}:
        raise ProbeError("invalid_contract")
    if (type(contract['con_id']) is not int or contract['con_id'] <= 0
            or not isinstance(contract['symbol'], str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,11}', contract['symbol'])
            or contract['security_type'] != 'STK' or contract['currency'] != 'USD'
            or contract['exchange'] != 'SMART' or not isinstance(contract['primary_exchange'], str)
            or not re.fullmatch(r'[A-Z0-9.]{1,20}', contract['primary_exchange'])):
        raise ProbeError("invalid_contract")
    quote = payload['quote']
    if not isinstance(quote, dict) or set(quote) != {'bid', 'ask', 'bid_size', 'ask_size', 'event_time', 'flags'}:
        raise ProbeError("invalid_quote")
    bid, ask = positive(quote['bid']), positive(quote['ask'])
    positive(quote['bid_size'])
    positive(quote['ask_size'])
    if bid > ask or type(quote['flags']) is not int or quote['flags'] != 0:
        raise ProbeError("crossed_or_flagged_quote")
    event, received, expires = quote['event_time'], payload['received_at'], payload['expires_at']
    if any(type(v) is not int for v in (event, received, expires)):
        raise ProbeError("invalid_evidence_time")
    if (event <= 0 or event > received + 2 or received > now + 2 or now < event - 2
            or received < event - 2 or received >= expires or expires != event + MAX_AGE or now >= expires):
        raise ProbeError("stale_or_future_quote")
    if not isinstance(payload['raw_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', payload['raw_sha256']):
        raise ProbeError("invalid_provenance_digest")


def market_message(command, config, contract=None):
    if command == 'contract':
        fields = (9, 8, CONTRACT_REQUEST, 0, config.symbol, 'STK', '', 0, '', '',
                  'SMART', '', 'USD', '', '', 0, '', '', '')
    elif command == 'quote' and contract is not None:
        # These fields come from a validated, uniquely resolved contract.
        fields = (97, QUOTE_REQUEST, contract['con_id'], contract['symbol'], 'STK', '', 0,
                  '', '', 'SMART', contract['primary_exchange'], 'USD', '', '', 'BidAsk', 0, 0)
    elif command == 'cancel_quote':
        fields = (98, QUOTE_REQUEST)
    else:
        raise PermissionError('Broker mutation commands are unavailable')
    if any('\0' in str(f) or '\n' in str(f) for f in fields):
        raise ProbeError('invalid_outbound_field')
    return ('\0'.join(str(f) for f in fields) + '\0').encode('ascii')


class MarketWire(Wire):
    def send_market(self, command, config, contract=None):
        body = market_message(command, config, contract)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError('broker_timeout')
        self.sock.settimeout(remaining)
        self.sock.sendall(struct.pack('!I', len(body)) + body)


def collect(config, connector=socket.create_connection, clock=time.time):
    deadline = time.monotonic() + config.broker.timeout
    with connector((config.broker.host, config.broker.port), timeout=config.broker.timeout) as sock:
        hello = b'v178..178'
        sock.sendall(b'API\0' + struct.pack('!I', len(hello)) + hello)
        wire = MarketWire(sock, deadline)
        handshake = wire.receive()
        if len(handshake) != 2 or handshake[0] != '178':
            raise ProbeError('unsupported_protocol_version')
        wire.send('start', config.broker.client_id)
        wire.send('accounts')
        phase, contracts, contract_raw = 'account', [], []
        subscribed = False
        try:
            for _ in range(128):
                fields = wire.receive()
                check_error(fields)
                if fields[0] == '15':
                    if len(fields) != 3:
                        raise ProbeError('invalid_account_response')
                    paper_account(fields[2], config.broker.expected_account)
                    if phase == 'account':
                        wire.send_market('contract', config)
                        phase = 'contract'
                elif fields[0] == '10' and phase == 'contract':
                    if len(fields) < 21 or fields[1] != str(CONTRACT_REQUEST):
                        raise ProbeError('unexpected_contract_response')
                    contract = {'con_id': int(fields[12]), 'symbol': fields[2], 'security_type': fields[3],
                                'exchange': fields[7], 'currency': fields[8], 'primary_exchange': fields[20]}
                    if (contract['symbol'] != config.symbol or contract['security_type'] != 'STK'
                            or contract['currency'] != 'USD' or contract['exchange'] != 'SMART'
                            or contract['con_id'] <= 0 or not re.fullmatch(r'[A-Z0-9.]{1,20}', contract['primary_exchange'])):
                        raise ProbeError('contract_mismatch')
                    contracts.append(contract)
                    contract_raw.append(fields)
                    if len(contracts) > 1:
                        raise ProbeError('ambiguous_contract')
                elif fields[0] == '52' and phase == 'contract':
                    if fields != ['52', '1', str(CONTRACT_REQUEST)] or len(contracts) != 1:
                        raise ProbeError('unique_contract_required')
                    wire.send_market('quote', config, contracts[0])
                    subscribed, phase = True, 'quote'
                elif fields[0] == '99' and phase == 'quote':
                    if len(fields) != 9 or fields[1:3] != [str(QUOTE_REQUEST), '3']:
                        raise ProbeError('unexpected_quote_response')
                    received = int(clock())
                    payload = {'schema_version': 1, 'source': SOURCE, 'protocol_version': 178,
                               'account_sha256': hashlib.sha256(config.broker.expected_account.encode()).hexdigest(),
                               'contract': contracts[0], 'quote': {'event_time': int(fields[3]), 'bid': fields[4],
                               'ask': fields[5], 'bid_size': fields[6], 'ask_size': fields[7], 'flags': int(fields[8])},
                               'received_at': received, 'expires_at': int(fields[3]) + MAX_AGE,
                               'raw_sha256': hashlib.sha256(canonical([contract_raw[0], fields])).hexdigest()}
                    validate_payload(payload, config.broker.expected_account, received)
                    return payload
            raise ProbeError('broker_message_limit')
        finally:
            if subscribed:
                try:
                    wire.send_market('cancel_quote', config)
                except (OSError, ProbeError):
                    pass


def run_market_check(config):
    key = read_key(config.key_path)  # Validate private key before opening a socket.
    payload = collect(config)
    receipt = {'payload': payload, 'signature': hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}
    digest = save_snapshot(config.snapshot, receipt)
    return {'status': 'fresh_paper_quote_collected', 'symbol': config.symbol,
            'expires_at': payload['expires_at'], 'snapshot_sha256': digest, 'execution_authorized': False}


def load_market_evidence(path, config, now=None):
    with path.open('rb') as f:
        raw = f.read(16001)
    if len(raw) > 16000:
        raise ProbeError('evidence_size_limit')
    receipt = json.loads(raw)
    if not isinstance(receipt, dict) or set(receipt) != {'payload', 'signature'}:
        raise ProbeError('unsigned_evidence')
    expected = hmac.new(read_key(config.key_path), canonical(receipt['payload']), hashlib.sha256).hexdigest()
    if not isinstance(receipt['signature'], str) or not hmac.compare_digest(expected, receipt['signature']):
        raise ProbeError('evidence_signature_mismatch')
    payload = receipt['payload']
    validate_payload(payload, config.broker.expected_account, now)
    if payload['contract']['symbol'] != config.symbol:
        raise ProbeError('evidence_symbol_mismatch')
    # Do not expose the account fingerprint, signing key or arbitrary broker text to models.
    summary = {'contract': payload['contract'], 'quote': payload['quote'], 'expires_at': payload['expires_at'],
               'scope': 'Fresh bid/ask observation only; investment thesis and other claims are unverified.'}
    return [{'id': 'quote-' + hashlib.sha256(canonical(payload)).hexdigest(),
             'source_url': 'ibkr://contract/' + str(payload['contract']['con_id']),
             'observed_at': datetime.fromtimestamp(payload['quote']['event_time'], timezone.utc).isoformat(),
             'summary': json.dumps(summary, sort_keys=True),
             'verification': 'verified_quote', 'expires_at': payload['expires_at']}]


def check_evidence_freshness(evidence, now=None):
    now = time.time() if now is None else now
    for item in evidence:
        if item.get('verification') == 'verified_quote':
            expiry = item.get('expires_at')
            if type(expiry) is not int or now >= expiry:
                raise ProbeError('quote_expired_during_deliberation')
