"""Bounded reqAllOpenOrders observation. Opaque activity blocks; no order writes."""
import hashlib
import hmac
import json
import re
import socket
import struct
import time
from pathlib import Path

from .ibkr import ProbeError, Wire, check_error, paper_account, save_snapshot
from .market import canonical, read_key
from .reconciliation import TTL

SOURCE = 'ibkr_paper_req_all_open_orders'
SCOPE = 'api_visible_current_session'
LIMIT = 65536


def query_message(command):
    # reqAllOpenOrders, legacy version 1. No client-0 binding or order mutation.
    if command != 'all_open_orders': raise PermissionError('Order mutation or binding unavailable')
    return b'16\x001\x00'


def collect_orders(config, connector=socket.create_connection, clock=time.time):
    if not config.expected_account: raise ProbeError('exact_account_pin_required')
    started = clock()
    deadline = time.monotonic() + config.timeout
    activity = []
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
            if fields[0] not in {'4','9'}: raise ProbeError('unexpected_frame_before_order_query')
        if account is None: raise ProbeError('account_frame_limit')
        body = query_message('all_open_orders')
        remaining = deadline-time.monotonic()
        if remaining <= 0: raise ProbeError('broker_timeout')
        sock.settimeout(remaining); sock.sendall(struct.pack('!I',len(body))+body)
        for _ in range(2000):
            fields = wire.receive(); check_error(fields)
            if fields[0] == '15':
                if len(fields) != 3 or paper_account(fields[2],account) != account:
                    raise ProbeError('account_changed_during_order_query')
            elif fields[0] in {'5','3'}:
                # Variable order/status layouts are deliberately not interpreted.
                # Never infer accounts, quantities, prices or cash reservations.
                if len(fields) < 2: raise ProbeError('invalid_order_activity_frame')
                if len(activity) >= 200: raise ProbeError('order_activity_limit')
                activity.append(hashlib.sha256(canonical(fields)).hexdigest())
            elif fields[0] == '53':
                if fields != ['53','1']: raise ProbeError('invalid_open_order_end')
                break
            elif fields[0] not in {'4','9'}:
                raise ProbeError('unexpected_order_query_frame')
        else: raise ProbeError('order_query_frame_limit')
    payload = {'schema_version':1, 'source':SOURCE, 'protocol_version':178,
               'account_sha256':hashlib.sha256(account.encode()).hexdigest(),
               'started_at':started, 'received_at':clock(), 'expires_at':started+TTL,
               'query_complete':True, 'scope':SCOPE, 'manual_order_coverage_verified':False,
               'reservation_amounts_verified':False, 'activity_frame_digests':activity}
    return validate_orders(payload,config.expected_account,clock())


def validate_orders(payload, account, now=None):
    now = time.time() if now is None else now
    keys = {'schema_version','source','protocol_version','account_sha256','started_at',
            'received_at','expires_at','query_complete','scope','manual_order_coverage_verified',
            'reservation_amounts_verified','activity_frame_digests'}
    if not isinstance(payload,dict) or set(payload) != keys: raise ProbeError('invalid_orders_schema')
    if (type(payload['schema_version']) is not int or payload['schema_version'] != 1
            or payload['source'] != SOURCE or type(payload['protocol_version']) is not int
            or payload['protocol_version'] != 178 or not account
            or payload['account_sha256'] != hashlib.sha256(account.encode()).hexdigest()
            or payload['query_complete'] is not True or payload['scope'] != SCOPE
            or payload['manual_order_coverage_verified'] is not False
            or payload['reservation_amounts_verified'] is not False):
        raise ProbeError('invalid_orders_identity_or_scope')
    times = [payload[k] for k in ('started_at','received_at','expires_at')]
    if any(type(t) not in (int,float) or not 0<t<1e12 for t in times): raise ProbeError('invalid_orders_time')
    start, received, expiry = times
    if not start<=received<=now<expiry or expiry != start+TTL: raise ProbeError('orders_expired_or_future')
    digests = payload['activity_frame_digests']
    if not isinstance(digests,list) or len(digests)>200 or any(
            not isinstance(d,str) or not re.fullmatch(r'[0-9a-f]{64}',d) for d in digests):
        raise ProbeError('invalid_order_activity_digests')
    return payload


def save_orders(config, key_path, path):
    key = read_key(key_path)
    payload = collect_orders(config)
    receipt = {'payload':payload,'signature':hmac.new(key,canonical(payload),hashlib.sha256).hexdigest()}
    if len(json.dumps(receipt).encode())>LIMIT: raise ProbeError('orders_receipt_size_limit')
    digest = save_snapshot(path,receipt)
    return {'status':'api_order_query_collected','receipt_sha256':digest,
            'activity_frame_count':len(payload['activity_frame_digests']),
            'manual_order_coverage_verified':False,'reservation_amounts_verified':False,
            'execution_authorized':False}


def load_orders(config, key_path, path):
    with Path(path).open('rb') as stream: body = stream.read(LIMIT+1)
    if len(body)>LIMIT: raise ProbeError('orders_receipt_size_limit')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    try:
        receipt = json.loads(body,object_pairs_hook=unique)
        if not isinstance(receipt,dict) or set(receipt)!={'payload','signature'} or not isinstance(receipt['signature'],str): raise ValueError()
        actual = hmac.new(read_key(key_path),canonical(receipt['payload']),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual,receipt['signature']): raise ValueError()
    except (ValueError,TypeError): raise ProbeError('invalid_orders_receipt_signature') from None
    return validate_orders(receipt['payload'],config.expected_account)
