"""Read-only explicit SettledCash summary. Aggregate scope is never ledger cash."""
import hashlib
import hmac
import json
import socket
import struct
import time

from .ibkr import ProbeError, Wire, check_error, paper_account, save_snapshot
from .market import canonical, read_key
from .reconciliation import number, currency, TTL


def collect_settlement(config, connector=socket.create_connection, clock=time.time):
    if not config.expected_account: raise ProbeError('exact_account_pin_required')
    started = clock()
    deadline = time.monotonic()+config.timeout
    values = {}
    with connector((config.host,config.port),timeout=config.timeout) as sock:
        sock.sendall(b'API\0'+struct.pack('!I',9)+b'v100..178')
        wire = Wire(sock,deadline)
        handshake = wire.receive()
        if len(handshake)!=2 or handshake[0]!='178': raise ProbeError('unsupported_protocol_version')
        wire.send('start',config.client_id);wire.send('accounts')
        account = None
        for _ in range(2000):
            fields=wire.receive();check_error(fields)
            if fields[0]=='15':
                if len(fields)!=3:raise ProbeError('invalid_account_response')
                account=paper_account(fields[2],config.expected_account)
                break
            if fields[0] not in {'4','9'}:raise ProbeError('unexpected_settlement_startup_frame')
        if account is None:raise ProbeError('account_frame_limit')
        wire.send('settled_summary')
        try:
            for _ in range(2000):
                fields=wire.receive();check_error(fields)
                if fields[0]=='15':
                    if len(fields)!=3 or paper_account(fields[2],account)!=account:
                        raise ProbeError('account_changed_during_settlement')
                elif fields[0]=='63':
                    if len(fields)!=7 or fields[1:5]!=['1','9103',account,'SettledCash']:
                        raise ProbeError('invalid_settlement_account_request_or_tag')
                    value,denomination=fields[5:]
                    number(value)
                    if not currency(denomination):raise ProbeError('invalid_settlement_currency')
                    if denomination in values:raise ProbeError('duplicate_settlement_summary')
                    if len(values)>=40:raise ProbeError('settlement_summary_limit')
                    values[denomination]=value
                elif fields[0]=='64':
                    if fields!=['64','1','9103']:raise ProbeError('invalid_settlement_summary_end')
                    if not values:raise ProbeError('explicit_settled_cash_not_returned')
                    break
                elif fields[0] not in {'4','9'}:raise ProbeError('unexpected_settlement_frame')
            else:raise ProbeError('settlement_summary_frame_limit')
        finally:
            try:wire.send('cancel_settled_summary')
            except (OSError,ProbeError):pass
    received=clock()
    if not 0<started<=received<started+TTL:raise ProbeError('settlement_summary_expired')
    return {'schema_version':1,'source':'ibkr_paper_explicit_settled_cash_summary',
            'protocol_version':178,'account_sha256':hashlib.sha256(account.encode()).hexdigest(),
            'started_at':started,'received_at':received,'expires_at':started+TTL,
            'query_complete':True,'scope':'account_summary_aggregate',
            'per_currency_spendable_cash_verified':False,
            'values':[{'tag':'SettledCash','currency':c,'value':v} for c,v in sorted(values.items())]}


def save_settlement(config,key_path,path):
    key=read_key(key_path)
    payload=collect_settlement(config)
    receipt={'payload':payload,'signature':hmac.new(key,canonical(payload),hashlib.sha256).hexdigest()}
    if len(json.dumps(receipt).encode())>65536:raise ProbeError('settlement_summary_size_limit')
    digest=save_snapshot(path,receipt)
    return {'status':'explicit_settlement_summary_collected','receipt_sha256':digest,
            'query_complete':True,'scope':payload['scope'],
            'reported_currencies':[r['currency'] for r in payload['values']],
            'negative_summary_observed':any(number(r['value'])<0 for r in payload['values']),
            'per_currency_spendable_cash_verified':False,'funding_authorized':False,
            'execution_authorized':False}
