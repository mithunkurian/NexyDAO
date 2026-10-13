"""Operator-only cash/position snapshots. No orders, FX conversions or ledger imports."""
import hashlib
import hmac
import json
import re
import socket
import struct
import time
from decimal import Decimal
from pathlib import Path

from .ibkr import ProbeError, Wire, paper_account, check_error, save_snapshot
from .market import canonical, read_key

SOURCE = 'ibkr_paper_cash_positions'
TTL = 60
CASH_TAGS = {'CashBalance', 'SettledCash', 'TotalCashBalance'}
NUMBER = r'-?[0-9]{1,16}(?:\.[0-9]{1,12})?'


def cash_tag(tag):
    # Gateway 1050 observed prefix for currency ledger values. No fuzzy aliases.
    return tag.removeprefix('$LEDGER-')


def number(value):
    if not isinstance(value, str) or not re.fullmatch(NUMBER, value):
        raise ProbeError('invalid_reconciliation_number')
    return Decimal(value)


def currency(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Z]{3}', value) is not None


def state_message(command, config):
    if not config.expected_account: raise ProbeError('exact_account_pin_required')
    messages = {'cash': (6, 2, 1, config.expected_account),
                'cancel_cash': (6, 2, 0, config.expected_account),
                'positions': (61, 1), 'cancel_positions': (64, 1)}
    if command not in messages: raise PermissionError('Broker mutation commands unavailable')
    return ('\0'.join(map(str, messages[command])) + '\0').encode('ascii')


def position(fields, account):
    # Official API 10.51.01 processPositionDataMsg, legacy response version 3.
    if len(fields) != 16 or fields[:2] != ['61', '3'] or fields[2] != account:
        raise ProbeError('invalid_position_account_or_layout')
    if not re.fullmatch(r'[0-9]{1,12}', fields[3]) or int(fields[3]) <= 0:
        raise ProbeError('invalid_position_contract')
    if (not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}', fields[4])
            or not re.fullmatch(r'[A-Z]{1,8}', fields[5]) or not currency(fields[11])):
        raise ProbeError('unsupported_position_metadata')
    # Keep unsupported instruments as observations and flag them in the report.
    # Quantity alone is sufficient for comparison; avgCost is never a valuation.
    number(fields[14]); number(fields[15])
    return {'contract_id': int(fields[3]), 'symbol': fields[4], 'security_type': fields[5],
            'currency': fields[11], 'quantity': fields[14], 'average_cost': fields[15]}


def collect_state(config, connector=socket.create_connection, clock=time.time):
    if not config.expected_account: raise ProbeError('exact_account_pin_required')
    started = clock()
    deadline = time.monotonic() + config.timeout
    cash, holdings = {}, {}
    schedule_unparsed = False
    scope_verified = True
    schedules = {}
    with connector((config.host, config.port), timeout=config.timeout) as sock:
        sock.sendall(b'API\0' + struct.pack('!I', 9) + b'v100..178')
        wire = Wire(sock, deadline)
        handshake = wire.receive()
        if len(handshake) != 2 or handshake[0] != '178': raise ProbeError('unsupported_protocol_version')
        wire.send('start', config.client_id); wire.send('accounts')
        account = None
        for _ in range(2000):
            fields = wire.receive(); check_error(fields)
            if fields[0] == '15':
                if len(fields) != 3: raise ProbeError('invalid_account_response')
                account = paper_account(fields[2], config.expected_account)
                break
        if account is None: raise ProbeError('account_frame_limit')

        def send(command):
            body = state_message(command, config)
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise ProbeError('broker_timeout')
            sock.settimeout(remaining)
            sock.sendall(struct.pack('!I', len(body)) + body)

        def receive():
            fields = wire.receive(); check_error(fields)
            if fields[0] == '15':
                if len(fields) != 3 or paper_account(fields[2], account) != account:
                    raise ProbeError('account_changed_during_state_download')
            return fields

        send('cash')
        try:
            for _ in range(2000):
                fields = receive()
                if fields[0] == '6':
                    if len(fields) != 6 or fields[1] != '2' or fields[5] != account:
                        raise ProbeError('invalid_cash_update_account_or_layout')
                    tag, value, denomination = fields[2:5]
                    if tag == 'AccountReady' and value != 'true': raise ProbeError('broker_account_not_ready')
                    if tag == 'SettledCashByDate':
                        schedule_unparsed = True
                        if not (currency(denomination) or denomination == 'BASE') or len(value) > 4096:
                            raise ProbeError('invalid_settlement_observation')
                        if denomination in schedules: raise ProbeError('duplicate_settlement_observation')
                        if len(schedules) >= 40: raise ProbeError('settlement_currency_limit')
                        schedules[denomination] = value
                    ledger_prefixed = tag.startswith('$LEDGER-')
                    tag = cash_tag(tag)
                    if tag not in CASH_TAGS or denomination == 'BASE': continue
                    if not currency(denomination): raise ProbeError('invalid_cash_currency')
                    if not ledger_prefixed: scope_verified = False
                    number(value)
                    key = tag, denomination
                    if key in cash: raise ProbeError('duplicate_cash_observation')
                    if len(cash) >= 120: raise ProbeError('cash_currency_limit')
                    cash[key] = value
                elif fields[0] == '54':
                    if fields != ['54', '1', account]: raise ProbeError('invalid_cash_download_end')
                    if not cash: raise ProbeError('missing_per_currency_cash')
                    break
            else: raise ProbeError('cash_frame_limit')
        finally:
            try: send('cancel_cash')
            except (OSError, ProbeError): pass
        send('positions')
        unsubscribe_notice_seen = False
        try:
            for _ in range(2000):
                fields = wire.receive()
                # Own completed subscription was explicitly cancelled. Handle
                # exactly one global cancellation acknowledgement in this phase.
                # The same code during an active cash subscription still fails.
                notice_layout = len(fields) == 5 or (len(fields) == 6 and fields[5] == '')
                if fields[:4] == ['4','2','-1','2100'] and notice_layout and not unsubscribe_notice_seen:
                    unsubscribe_notice_seen = True
                    continue
                check_error(fields)
                if fields[0] == '15':
                    if len(fields) != 3 or paper_account(fields[2], account) != account:
                        raise ProbeError('account_changed_during_state_download')
                # Late cash updates are validated for identity but invalidate the
                # observation window if relevant balances changed after its end.
                if fields[0] == '6':
                    if len(fields) != 6 or fields[1] != '2' or fields[5] != account: raise ProbeError('invalid_cash_update_account_or_layout')
                    if fields[2] == 'AccountReady' and fields[3] != 'true': raise ProbeError('broker_account_not_ready')
                    if fields[2] == 'SettledCashByDate' and schedules.get(fields[4]) != fields[3]:
                        raise ProbeError('settlement_changed_during_positions')
                    tag = cash_tag(fields[2])
                    if tag in CASH_TAGS and fields[4] != 'BASE':
                        if scope_verified and not fields[2].startswith('$LEDGER-'):
                            raise ProbeError('cash_scope_changed_during_positions')
                        if cash.get((tag, fields[4])) != fields[3]: raise ProbeError('cash_changed_during_positions')
                elif fields[0] == '61':
                    item = position(fields, account)
                    key = item['contract_id']
                    if key in holdings: raise ProbeError('duplicate_position_observation')
                    if len(holdings) >= 200: raise ProbeError('position_count_limit')
                    holdings[key] = item
                elif fields[0] == '62':
                    if fields != ['62', '1']: raise ProbeError('invalid_position_download_end')
                    break
            else: raise ProbeError('position_frame_limit')
        finally:
            try: send('cancel_positions')
            except (OSError, ProbeError): pass
    payload = {'schema_version': 3, 'source': SOURCE, 'protocol_version': 178,
               'account_sha256': hashlib.sha256(account.encode()).hexdigest(),
               'started_at': started, 'received_at': clock(), 'expires_at': started + TTL,
               'cash_download_complete': True, 'positions_download_complete': True,
               'per_currency_scope_verified':scope_verified,
               'settled_cash_schedule_unparsed': schedule_unparsed,
               'settlement_observations': [{'currency':c,'raw_value':v} for c,v in sorted(schedules.items())],
               'cash': [{'tag': t, 'currency': c, 'value': v} for (t,c),v in sorted(cash.items())],
               'positions': [holdings[k] for k in sorted(holdings)]}
    validate_state(payload, config.expected_account, clock())
    return payload


def validate_state(payload, expected_account, now=None):
    now = time.time() if now is None else now
    keys = {'schema_version','source','protocol_version','account_sha256','started_at',
            'received_at','expires_at','cash_download_complete','positions_download_complete',
            'settled_cash_schedule_unparsed','cash','positions'}
    version = payload.get('schema_version') if isinstance(payload,dict) else None
    if type(version) is int and version in (2,3): keys.add('settlement_observations')
    if type(version) is int and version == 3: keys.add('per_currency_scope_verified')
    if not isinstance(payload, dict) or set(payload) != keys: raise ProbeError('invalid_state_schema')
    if (type(payload['schema_version']) is not int or payload['schema_version'] not in (1,2,3)
            or payload['source'] != SOURCE or type(payload['protocol_version']) is not int or payload['protocol_version'] != 178
            or not expected_account or payload['account_sha256'] != hashlib.sha256(expected_account.encode()).hexdigest()
            or payload['cash_download_complete'] is not True or payload['positions_download_complete'] is not True
            or type(payload['settled_cash_schedule_unparsed']) is not bool):
        raise ProbeError('invalid_state_identity_or_completion')
    times = [payload[k] for k in ('started_at','received_at','expires_at')]
    if any(type(t) not in (int,float) or not 0 < t < 1e12 for t in times): raise ProbeError('invalid_state_time')
    start, received, expiry = times
    if not start <= received <= now < expiry or expiry != start + TTL: raise ProbeError('state_expired_or_future')
    if version == 3 and type(payload['per_currency_scope_verified']) is not bool:
        raise ProbeError('invalid_cash_scope_flag')
    if version in (2,3):
        schedules = payload['settlement_observations']
        if not isinstance(schedules,list) or len(schedules) > 40: raise ProbeError('invalid_settlement_observation')
        seen = set()
        for row in schedules:
            if (not isinstance(row,dict) or set(row) != {'currency','raw_value'}
                    or not (currency(row['currency']) or row['currency']=='BASE')
                    or not isinstance(row['raw_value'],str) or len(row['raw_value']) > 4096
                    or any(ord(c)<32 for c in row['raw_value'])): raise ProbeError('invalid_settlement_observation')
            if row['currency'] in seen: raise ProbeError('duplicate_settlement_observation')
            seen.add(row['currency'])
        if bool(schedules) != payload['settled_cash_schedule_unparsed']: raise ProbeError('invalid_settlement_presence_flag')
    cash, holdings = payload['cash'], payload['positions']
    if not isinstance(cash,list) or not 1 <= len(cash) <= 120: raise ProbeError('invalid_state_cash')
    if not isinstance(holdings,list) or len(holdings) > 200: raise ProbeError('invalid_state_positions')
    seen = set()
    for row in cash:
        if (not isinstance(row,dict) or set(row) != {'tag','currency','value'}
                or not isinstance(row['tag'],str) or row['tag'] not in CASH_TAGS or not currency(row['currency'])):
            raise ProbeError('invalid_state_cash')
        number(row['value'])
        key = row['tag'],row['currency']
        if key in seen: raise ProbeError('duplicate_cash_observation')
        seen.add(key)
    seen = set()
    for item in holdings:
        if (not isinstance(item,dict) or set(item) != {'contract_id','symbol','security_type','currency','quantity','average_cost'}
                or type(item['contract_id']) is not int or not 0 < item['contract_id'] < 10**12
                or not isinstance(item['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',item['symbol'])
                or not isinstance(item['security_type'],str) or not re.fullmatch(r'[A-Z]{1,8}',item['security_type'])
                or not currency(item['currency'])): raise ProbeError('invalid_state_positions')
        number(item['quantity']);number(item['average_cost'])
        if item['contract_id'] in seen: raise ProbeError('duplicate_position_observation')
        seen.add(item['contract_id'])
    return payload


def save_state(config, key_path, path):
    key = read_key(key_path)
    payload = collect_state(config)
    receipt = {'payload':payload, 'signature':hmac.new(key,canonical(payload),hashlib.sha256).hexdigest()}
    if len(json.dumps(receipt,sort_keys=True,indent=2).encode()) > 131072:
        raise ProbeError('state_receipt_size_limit')
    digest = save_snapshot(path, receipt)
    return {'status':'cash_positions_collected', 'receipt_sha256':digest,
            'cash_rows':len(payload['cash']), 'position_rows':len(payload['positions']), 'execution_authorized':False}


def load_state(config, key_path, path):
    with Path(path).open('rb') as stream: body = stream.read(131073)
    if len(body) > 131072: raise ProbeError('state_receipt_size_limit')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    try:
        receipt = json.loads(body, object_pairs_hook=unique)
        if not isinstance(receipt,dict) or set(receipt) != {'payload','signature'} or not isinstance(receipt['signature'],str): raise ValueError()
        actual = hmac.new(read_key(key_path), canonical(receipt['payload']), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual,receipt['signature']): raise ValueError()
    except (ValueError,TypeError): raise ProbeError('invalid_state_receipt_signature') from None
    return validate_state(receipt['payload'],config.expected_account)


def reconcile_state(payload, config, ledger, now=None):
    validate_state(payload,config.expected_account,now)
    snapshot = ledger.snapshot()
    cash = {(r['tag'],r['currency']):number(r['value']) for r in payload['cash']}
    currencies = {c for _,c in cash}
    scope = payload.get('per_currency_scope_verified',False)
    complete = scope and all(('CashBalance',c) in cash and ('SettledCash',c) in cash for c in currencies)
    usd = cash.get(('SettledCash','USD')) if scope else None
    cash_comparison = 'USD_not_observed' if usd is None else ('match' if usd == Decimal(snapshot['settled_cash_usd']) else 'differs')
    observed = {(p['contract_id'],p['currency']):number(p['quantity']) for p in payload['positions'] if number(p['quantity']) != 0}
    expected = {(p['contract_id'],'USD'):Decimal(p['quantity']) for p in snapshot['positions']}
    identified = all(p['contract_id'] is not None for p in snapshot['positions'])
    matched = identified and observed == expected
    return {'status':'partial_cash_position_comparison', 'internal_simulation_reconciliation':True,
            'cash_currency_count':len(currencies), 'per_currency_cash_pairs_complete':complete,
            'per_currency_scope_verified':scope,
            'settled_cash_schedule_unparsed':payload['settled_cash_schedule_unparsed'],
            'usd_settled_cash_observed':usd is not None, 'simulated_cash_comparison':cash_comparison,
            'negative_currency_cash_observed':any(v<0 for v in cash.values()),
            'positions_match_simulation':matched, 'simulated_contract_identity_complete':identified,
            'broker_position_count':len(observed), 'simulated_position_count':len(expected),
            'short_position_observed':any(number(p['quantity'])<0 for p in payload['positions']),
            'unsupported_instrument_observed':any(p['security_type']!='STK' for p in payload['positions']),
            'ledger_revision':snapshot['revision'], 'broker_reconciliation':False,
            'broker_funding_verified':False, 'broker_balances_imported':False,
            'observation_atomic':False, 'fx_conversion_performed':False,
            'missing_checks': ([] if complete else ['per_currency_settled_cash']) + ([] if scope else ['per_currency_cash_scope']) + ['open_orders_and_reservations','fills_fees_and_external_transfers',
                              'funding_allocation_and_fx','atomic_or_stable_account_state'],
            'execution_authorized':False}
