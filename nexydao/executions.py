"""Bounded read-only protocol-178 executions/fees; no broker or ledger writes.

Current Gateway query visibility is not an account history or reconciliation.
Wire layout checked against official API 10.51.01 client/decoder sources.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import time

from .ibkr import ProbeError, Wire, check_error, paper_account, save_snapshot
from .market import canonical
from . import research_signatures as signatures

REQUEST_ID=9181
TTL=60
LIMIT=65536
MAX_ROWS=50
SOURCE='ibkr_paper_req_executions'
DOMAIN=b'NexyDAO:broker-executions:ed25519:v1\x00'
ROW_FIELDS={'execution_sha256','correction_group_sha256','correction_sequence','contract_id',
            'symbol','security_type','contract_exchange','execution_exchange','currency','order_id','client_id','permanent_id','side','quantity','price',
            'cumulative_quantity','average_price','broker_time','liquidation','last_liquidity',
            'pending_price_revision','commission','commission_currency','raw_frame_sha256'}
PAYLOAD_FIELDS={'schema_version','source','protocol_version','account_sha256','started_at',
                'received_at','expires_at','query_complete','commission_links_complete','scope',
                'manual_order_coverage_verified','transfer_coverage_verified','broker_reconciliation',
                'executions','correction_observed','pending_price_revision_observed','fee_currency_mismatch_observed'}


def _hash(value):return hashlib.sha256(value.encode()).hexdigest()


def _digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def _amount(value,*,positive=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?[0-9]{1,16}(?:\.[0-9]{1,12})?',value):
        raise ProbeError('invalid_execution_amount')
    result=Decimal(value)
    if positive and result<=0:raise ProbeError('nonpositive_execution_amount')
    return result


def _integer(value,minimum,maximum):
    if not isinstance(value,str) or not re.fullmatch(r'-?[0-9]{1,19}',value):raise ProbeError('invalid_execution_integer')
    number=int(value)
    if not minimum<=number<=maximum:raise ProbeError('invalid_execution_integer')
    return number


def _text(value,limit=128):
    return isinstance(value,str) and len(value)<=limit and all(32<=ord(c)<=126 for c in value)


def _broker_time(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{8} {1,2}[0-9]{2}:[0-9]{2}:[0-9]{2}(?: [A-Za-z0-9_+/\-]{1,40})?',value):
        raise ProbeError('invalid_execution_time')
    try:datetime.strptime(' '.join(value.split()[:2]),'%Y%m%d %H:%M:%S')
    except ValueError:raise ProbeError('invalid_execution_time') from None


def request_message(config,command='executions'):
    if command!='executions':raise PermissionError('Execution query only; order writes unavailable')
    if not config.expected_account:raise ProbeError('exact_account_pin_required')
    # reqExecutions version 3: client filter 0, exact account, no extra filters.
    # This is not a client-0 API connection or an order-binding command.
    return ('\0'.join(map(str,(7,3,REQUEST_ID,0,config.expected_account,'','','','','')))+'\0').encode('ascii')


def execution_frame(fields,account):
    if len(fields)!=32 or fields[:2]!=['11',str(REQUEST_ID)]:raise ProbeError('invalid_execution_layout_or_request')
    if fields[16]!=account:raise ProbeError('execution_account_mismatch')
    if (fields[5]!='STK' or fields[6]!='' or fields[7] not in ('0','0.0') or fields[8]!=''
            or fields[9] not in ('','1') or fields[27]!='' or fields[28] not in ('0','0.0') or fields[29]!=''):
        raise ProbeError('unsupported_execution_contract_or_model')
    if any(not _text(value) for value in fields):raise ProbeError('invalid_execution_text')
    if (not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',fields[4]) or not re.fullmatch('[A-Z]{3}',fields[11])
            or not re.fullmatch(r'[A-Z0-9.]{1,32}',fields[10]) or not re.fullmatch(r'[A-Z0-9.]{1,32}',fields[17])
            or fields[18] not in ('BOT','SLD') or fields[31] not in ('0','1')):
        raise ProbeError('invalid_execution_metadata')
    identifier=fields[14]
    if not re.fullmatch(r'[A-Za-z0-9_\-]{1,32}(?:\.[A-Za-z0-9_\-]{1,32}){1,3}\.[0-9]{1,3}',identifier):
        raise ProbeError('unsupported_execution_identifier')
    _broker_time(fields[15])
    for index in (19,20,24,25):_amount(fields[index],positive=True)
    if _amount(fields[24])<_amount(fields[19]):raise ProbeError('invalid_execution_cumulative_quantity')
    return identifier,{'execution_sha256':_hash(identifier),'correction_group_sha256':_hash(identifier.rsplit('.',1)[0]),
        'correction_sequence':_integer(identifier.rsplit('.',1)[1],1,999),
        'contract_id':_integer(fields[3],1,10**12-1),'symbol':fields[4],'security_type':'STK',
        'contract_exchange':fields[10],'execution_exchange':fields[17],'currency':fields[11],
        'order_id':_integer(fields[2],-2**31,2**31-1),'client_id':_integer(fields[22],0,2**31-1),
        'permanent_id':_integer(fields[21],0,2**63-1),'side':fields[18],
        'quantity':fields[19],'price':fields[20],'cumulative_quantity':fields[24],'average_price':fields[25],
        'broker_time':fields[15],'liquidation':_integer(fields[23],0,2),'last_liquidity':_integer(fields[30],0,4),
        'pending_price_revision':fields[31]=='1','raw_frame_sha256':hashlib.sha256(canonical(fields)).hexdigest()}


def commission_frame(fields):
    if len(fields)!=8 or fields[:2]!=['59','1']:raise ProbeError('invalid_commission_layout')
    if any(not _text(value) for value in fields) or not re.fullmatch('[A-Z]{3}',fields[4]):
        raise ProbeError('invalid_commission_metadata')
    _amount(fields[3])  # Negative rebates are observations, never imported cash.
    for ignored in fields[5:7]:
        if ignored:
            try:valid=Decimal(ignored).is_finite()
            except Exception:valid=False
            if not valid:raise ProbeError('invalid_commission_auxiliary_number')
    _integer(fields[7],0,99999999)
    return fields[2],{'commission':fields[3],'commission_currency':fields[4]}


def _flags(rows):
    groups=[row['correction_group_sha256'] for row in rows]
    return {'correction_observed':len(set(groups))!=len(groups) or any(row['correction_sequence']>1 for row in rows),
            'pending_price_revision_observed':any(row['pending_price_revision'] for row in rows),
            'fee_currency_mismatch_observed':any(row['currency']!=row['commission_currency'] for row in rows)}


def collect_executions(config,connector=socket.create_connection,clock=time.time):
    body=request_message(config)
    started=clock();deadline=time.monotonic()+config.timeout
    executions={};fees={};ended=False
    with connector((config.host,config.port),timeout=config.timeout) as sock:
        sock.sendall(b'API\0'+struct.pack('!I',9)+b'v100..178')
        wire=Wire(sock,deadline)
        handshake=wire.receive()
        if len(handshake)!=2 or handshake[0]!='178':raise ProbeError('unsupported_protocol_version')
        wire.send('start',config.client_id);wire.send('accounts')
        for _ in range(2000):
            fields=wire.receive();check_error(fields)
            if fields[0]=='15':
                if len(fields)!=3:raise ProbeError('invalid_account_response')
                account=paper_account(fields[2],config.expected_account);break
            if fields[0] not in ('4','9'):raise ProbeError('unexpected_frame_before_execution_query')
        else:raise ProbeError('account_frame_limit')
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ProbeError('broker_timeout')
        sock.settimeout(remaining);sock.sendall(struct.pack('!I',len(body))+body)
        for _ in range(2000):
            fields=wire.receive();check_error(fields)
            if fields[0]=='15':
                if len(fields)!=3 or paper_account(fields[2],account)!=account:raise ProbeError('execution_account_changed')
            elif fields[0]=='11':
                if ended:raise ProbeError('execution_after_query_end')
                identifier,row=execution_frame(fields,account)
                if identifier in executions or len(executions)>=MAX_ROWS:raise ProbeError('duplicate_or_excess_execution')
                executions[identifier]=row
            elif fields[0]=='59':
                identifier,row=commission_frame(fields)
                if identifier in fees or len(fees)>=MAX_ROWS:raise ProbeError('duplicate_or_excess_commission')
                fees[identifier]=row
            elif fields[0]=='55':
                if ended or fields!=['55','1',str(REQUEST_ID)]:raise ProbeError('invalid_execution_end')
                ended=True
            elif fields[0] not in ('4','9'):raise ProbeError('unexpected_execution_query_frame')
            if ended:
                if not set(fees)<=set(executions):raise ProbeError('unmatched_commission')
                if set(fees)==set(executions):break
        else:raise ProbeError('execution_frame_limit')
    rows=[{**executions[key],**fees[key]} for key in sorted(executions)]
    payload={'schema_version':1,'source':SOURCE,'protocol_version':178,'account_sha256':_hash(account),
        'started_at':started,'received_at':clock(),'expires_at':started+TTL,'query_complete':True,
        'commission_links_complete':True,'scope':'api_visible_gateway_recent_query',
        'manual_order_coverage_verified':False,'transfer_coverage_verified':False,'broker_reconciliation':False,
        'executions':rows,**_flags(rows)}
    return validate_executions(payload,config.expected_account,clock())


def validate_executions(payload,account,now=None):
    now=time.time() if now is None else now
    if not isinstance(payload,dict) or set(payload)!=PAYLOAD_FIELDS:raise ProbeError('invalid_executions_schema')
    if (type(payload['schema_version']) is not int or payload['schema_version']!=1 or payload['source']!=SOURCE
            or type(payload['protocol_version']) is not int or payload['protocol_version']!=178 or not account
            or paper_account(account)!=account or payload['account_sha256']!=_hash(account)
            or payload['scope']!='api_visible_gateway_recent_query' or payload['query_complete'] is not True
            or payload['commission_links_complete'] is not True
            or any(payload[key] is not False for key in ('manual_order_coverage_verified','transfer_coverage_verified','broker_reconciliation'))):
        raise ProbeError('invalid_executions_identity_or_scope')
    times=[payload[key] for key in ('started_at','received_at','expires_at')]
    if any(type(value) not in (int,float) or not 0<value<1e12 for value in times):raise ProbeError('invalid_executions_time')
    start,received,expiry=times
    if not start<=received<=now<expiry or expiry!=start+TTL:raise ProbeError('executions_expired_or_future')
    rows=payload['executions'];seen=set()
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ProbeError('invalid_execution_rows')
    for row in rows:
        if not isinstance(row,dict) or set(row)!=ROW_FIELDS:raise ProbeError('invalid_execution_row_schema')
        if (any(not _digest(row[key]) for key in ('execution_sha256','correction_group_sha256','raw_frame_sha256'))
                or row['execution_sha256'] in seen or not isinstance(row['symbol'],str)
                or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',row['symbol']) or row['side'] not in ('BOT','SLD')
                or row['security_type']!='STK' or any(not isinstance(row[key],str) or not re.fullmatch(r'[A-Z0-9.]{1,32}',row[key]) for key in ('contract_exchange','execution_exchange'))
                or any(not isinstance(row[key],str) or not re.fullmatch('[A-Z]{3}',row[key]) for key in ('currency','commission_currency'))
                or type(row['pending_price_revision']) is not bool):raise ProbeError('invalid_execution_row_metadata')
        seen.add(row['execution_sha256'])
        for key,low,high in (('contract_id',1,10**12-1),('order_id',-2**31,2**31-1),('client_id',0,2**31-1),
                            ('permanent_id',0,2**63-1),('correction_sequence',1,999),('liquidation',0,2),('last_liquidity',0,4)):
            if type(row[key]) is not int or not low<=row[key]<=high:raise ProbeError('invalid_execution_row_integer')
        for key in ('quantity','price','cumulative_quantity','average_price'):_amount(row[key],positive=True)
        _amount(row['commission']);_broker_time(row['broker_time'])
        if _amount(row['cumulative_quantity'])<_amount(row['quantity']):raise ProbeError('invalid_execution_cumulative_quantity')
    flags=_flags(rows)
    if any(type(payload[key]) is not bool or payload[key]!=value for key,value in flags.items()):raise ProbeError('invalid_execution_risk_flags')
    return payload


@dataclass(frozen=True)
class ExecutionReceiptConfig:
    public_path:Path
    public_sha256:str
    signing_path:Path|None=field(default=None,repr=False)
    openssl_path:Path=signatures.DEFAULT_OPENSSL

    @classmethod
    def from_env(cls):
        public=os.environ.get('NEXYDAO_EXECUTION_RECEIPT_PUBLIC_KEY_FILE','')
        pin=os.environ.get('NEXYDAO_EXECUTION_RECEIPT_PUBLIC_KEY_SHA256','')
        if not public or not _digest(pin):raise ProbeError('execution_public_key_and_pin_required')
        private=os.environ.get('NEXYDAO_EXECUTION_RECEIPT_SIGNING_KEY_FILE','')
        return cls(Path(public),pin,Path(private) if private else None,
                   Path(os.environ.get('NEXYDAO_OPENSSL_PATH',str(signatures.DEFAULT_OPENSSL))))


def save_executions(config,settings,path):
    try:signatures.check_signer(settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path)
    except signatures.ReceiptSignatureError:raise ProbeError('execution_signer_unavailable') from None
    payload=collect_executions(config)
    try:receipt=signatures.sign(payload,settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except signatures.ReceiptSignatureError:raise ProbeError('execution_signing_failed') from None
    if len(json.dumps(receipt,indent=2,sort_keys=True).encode())>LIMIT:raise ProbeError('executions_receipt_size')
    validate_executions(payload,config.expected_account)
    digest=save_snapshot(path,receipt)
    return {**execution_report(payload),'receipt_sha256':digest}


def executions_from_bytes(raw,config,settings,now=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT:raise ProbeError('executions_receipt_size')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        receipt=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        signatures.verify(receipt,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except (ValueError,TypeError,RecursionError):raise ProbeError('execution_receipt_signature_denied') from None
    return validate_executions(receipt['payload'],config.expected_account,now)


def load_executions(config,settings,path):
    try:raw=signatures._read(path,LIMIT)
    except signatures.ReceiptSignatureError:raise ProbeError('execution_receipt_unavailable') from None
    return executions_from_bytes(raw,config,settings)


def execution_report(payload):
    return {'status':'execution_fee_observations_verified','execution_count':len(payload['executions']),
            'commission_links_complete':True,**_flags(payload['executions']),
            'manual_order_coverage_verified':False,'transfer_coverage_verified':False,
            'broker_reconciliation':False,'ledger_imported':False,'execution_authorized':False}
