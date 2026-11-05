"""Diagnostic stable-prefix order decoding; advanced order fields remain opaque.

No monetary reservation, account-wide/manual coverage or executable permission.
Protocol-178 prefix and full orderStatus layout checked against official 10.51.01.
"""
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re

from .ibkr import ProbeError,save_snapshot
from .market import canonical
from .orders import collect_orders,validate_orders,LIMIT
from . import research_signatures as signatures

DOMAIN=b'NexyDAO:broker-open-orders:ed25519:v1\x00'
DETAIL_FIELDS={'order_cores','order_statuses','typed_scope','complete_order_layout_verified',
               'status_links_complete','unmatched_status_count','ambiguous_order_identity_observed',
               'quantity_disagreement_observed','order_versions_changed_observed'}
CORE_FIELDS={'activity_index','raw_frame_sha256','order_id','client_id','permanent_id',
             'contract_id','symbol','security_type','currency','exchange','side','total_quantity',
             'order_type','limit_price','auxiliary_price','time_in_force','oca_group_present',
             'order_reference_sha256','unparsed_field_count','unparsed_tail_sha256'}
STATUS_FIELDS={'activity_index','raw_frame_sha256','order_id','client_id','permanent_id','parent_id',
               'status','filled_quantity','remaining_quantity','average_fill_price','last_fill_price',
               'market_cap_price','held_reason_sha256'}


def _hash(value):return hashlib.sha256(value).hexdigest()


def _text(value,limit=128):
    return isinstance(value,str) and len(value)<=limit and all(32<=ord(c)<=126 for c in value)


def _number(value,*,positive=False):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,16}(?:\.[0-9]{1,12})?',value):
        raise ProbeError('invalid_typed_order_amount')
    result=Decimal(value)
    if positive and result<=0:raise ProbeError('invalid_typed_order_amount')
    return result


def _price(value):
    if value in ('','1.7976931348623157e+308','1.7976931348623157E+308'):return None
    _number(value)
    return value


def _integer(value,minimum,maximum):
    if not isinstance(value,str) or not re.fullmatch(r'-?[0-9]{1,19}',value):raise ProbeError('invalid_typed_order_integer')
    number=int(value)
    if not minimum<=number<=maximum:raise ProbeError('invalid_typed_order_integer')
    return number


def open_order_core(fields,account,index):
    # At protocol >=145 there is no legacy response-version field. First 26
    # fields are fixed through permId. Nothing about the variable tail is inferred.
    if not 27<=len(fields)<=1026 or fields[0]!='5':raise ProbeError('unsupported_open_order_prefix')
    if any(not _text(value) for value in fields[:26]):raise ProbeError('invalid_open_order_prefix_text')
    if fields[20]!=account:raise ProbeError('open_order_account_mismatch')
    if (fields[4]!='STK' or fields[5]!='' or fields[6] not in ('','0','0.0') or fields[7]!=''
            or fields[8] not in ('','1') or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',fields[3])
            or not re.fullmatch(r'[A-Z0-9.]{1,32}',fields[9]) or not re.fullmatch('[A-Z]{3}',fields[10])
            or fields[13] not in ('BUY','SELL') or not re.fullmatch('[A-Z ]{1,16}',fields[15])
            or not re.fullmatch('[A-Z]{1,8}',fields[18])):raise ProbeError('unsupported_open_order_core')
    _number(fields[14],positive=True)
    return {'activity_index':index,'raw_frame_sha256':_hash(canonical(fields)),
        'order_id':_integer(fields[1],-2**31,2**31-1),'client_id':_integer(fields[24],0,2**31-1),
        'permanent_id':_integer(fields[25],0,2**63-1),'contract_id':_integer(fields[2],1,10**12-1),
        'symbol':fields[3],'security_type':'STK','currency':fields[10],'exchange':fields[9],
        'side':fields[13],'total_quantity':fields[14],'order_type':fields[15],
        'limit_price':_price(fields[16]),'auxiliary_price':_price(fields[17]),'time_in_force':fields[18],
        'oca_group_present':bool(fields[19]),'order_reference_sha256':_hash(fields[23].encode()),
        'unparsed_field_count':len(fields)-26,'unparsed_tail_sha256':_hash(canonical(fields[26:]))}


def order_status(fields,index):
    if len(fields)!=12 or fields[0]!='3':raise ProbeError('unsupported_order_status_layout')
    if any(not _text(value) for value in fields) or not re.fullmatch('[A-Za-z]{1,32}',fields[2]):
        raise ProbeError('invalid_order_status_text')
    _number(fields[3]);_number(fields[4])
    return {'activity_index':index,'raw_frame_sha256':_hash(canonical(fields)),
        'order_id':_integer(fields[1],-2**31,2**31-1),'client_id':_integer(fields[9],0,2**31-1),
        'permanent_id':_integer(fields[6],0,2**63-1),'parent_id':_integer(fields[7],-2**31,2**31-1),
        'status':fields[2],'filled_quantity':fields[3],'remaining_quantity':fields[4],
        'average_fill_price':_price(fields[5]),'last_fill_price':_price(fields[8]),
        'market_cap_price':_price(fields[11]),'held_reason_sha256':_hash(fields[10].encode())}


def _links(cores,statuses):
    by_pair={};permanent_pairs={};versions={}
    for row in cores:
        pair=(row['client_id'],row['order_id']);identity=(*pair,row['permanent_id'])
        by_pair.setdefault(pair,[]).append(row)
        if row['permanent_id']>0:permanent_pairs.setdefault(row['permanent_id'],set()).add(pair)
        versions.setdefault(identity,set()).add(row['raw_frame_sha256'])
    ambiguous=any(len({row['permanent_id'] for row in rows})>1 for rows in by_pair.values()) or any(len(pairs)>1 for pairs in permanent_pairs.values())
    unmatched=0;quantity_disagreement=False;matched=set()
    for status in statuses:
        pair=(status['client_id'],status['order_id'])
        candidates=by_pair.get(pair,[])
        exact=[row for row in candidates if status['permanent_id']>0 and row['permanent_id']==status['permanent_id']]
        if not exact:
            unmatched+=1
            if candidates:ambiguous=True
            continue
        matched.add((*pair,status['permanent_id']))
        total=_number(status['filled_quantity'])+_number(status['remaining_quantity'])
        if any(total!=_number(row['total_quantity']) for row in exact):quantity_disagreement=True
    identities={(*pair,row['permanent_id']) for pair,rows in by_pair.items() for row in rows}
    return {'status_links_complete':not unmatched and not ambiguous and matched==identities,
            'unmatched_status_count':unmatched,'ambiguous_order_identity_observed':ambiguous,
            'quantity_disagreement_observed':quantity_disagreement,
            'order_versions_changed_observed':any(len(digests)>1 for digests in versions.values())}


def detail_payload(cores,statuses):
    return {'order_cores':cores,'order_statuses':statuses,'typed_scope':'stock_order_prefix_and_status',
            'complete_order_layout_verified':False,**_links(cores,statuses)}


def validate_details(payload):
    if payload['typed_scope']!='stock_order_prefix_and_status' or payload['complete_order_layout_verified'] is not False:
        raise ProbeError('invalid_typed_order_scope')
    cores,statuses=payload['order_cores'],payload['order_statuses'];indexes=set()
    for rows,fields in ((cores,CORE_FIELDS),(statuses,STATUS_FIELDS)):
        if not isinstance(rows,list) or len(rows)>100:raise ProbeError('typed_order_row_limit')
        for row in rows:
            if not isinstance(row,dict) or set(row)!=fields:raise ProbeError('invalid_typed_order_row_schema')
            index=row['activity_index']
            if (type(index) is not int or not 0<=index<len(payload['activity_frame_digests']) or index in indexes
                    or row['raw_frame_sha256']!=payload['activity_frame_digests'][index]):
                raise ProbeError('typed_order_activity_binding_failed')
            indexes.add(index)
            for key in (key for key in row if key.endswith('_sha256')):
                if not isinstance(row[key],str) or not re.fullmatch('[0-9a-f]{64}',row[key]):raise ProbeError('invalid_typed_order_digest')
            bounds=[('order_id',-2**31,2**31-1),('client_id',0,2**31-1),('permanent_id',0,2**63-1)]
            bounds+=([('contract_id',1,10**12-1),('unparsed_field_count',1,1000)] if fields is CORE_FIELDS else [('parent_id',-2**31,2**31-1)])
            for key,low,high in bounds:
                if type(row[key]) is not int or not low<=row[key]<=high:raise ProbeError('invalid_typed_order_row_integer')
            if fields is CORE_FIELDS:
                if (row['security_type']!='STK' or not isinstance(row['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',row['symbol'])
                        or not isinstance(row['exchange'],str) or not re.fullmatch(r'[A-Z0-9.]{1,32}',row['exchange'])
                        or not isinstance(row['currency'],str) or not re.fullmatch('[A-Z]{3}',row['currency'])
                        or row['side'] not in ('BUY','SELL') or not isinstance(row['order_type'],str) or not re.fullmatch('[A-Z ]{1,16}',row['order_type'])
                        or not isinstance(row['time_in_force'],str) or not re.fullmatch('[A-Z]{1,8}',row['time_in_force'])
                        or type(row['oca_group_present']) is not bool):raise ProbeError('invalid_typed_order_core_metadata')
                _number(row['total_quantity'],positive=True)
                prices=('limit_price','auxiliary_price')
            else:
                if not isinstance(row['status'],str) or not re.fullmatch('[A-Za-z]{1,32}',row['status']):raise ProbeError('invalid_typed_order_status')
                _number(row['filled_quantity']);_number(row['remaining_quantity'])
                prices=('average_fill_price','last_fill_price','market_cap_price')
            for key in prices:
                if row[key] is not None:_number(row[key])
    if indexes!=set(range(len(payload['activity_frame_digests']))):raise ProbeError('typed_order_activity_missing')
    expected=_links(cores,statuses)
    for key,value in expected.items():
        if type(payload[key]) is not type(value) or payload[key]!=value:raise ProbeError('invalid_typed_order_link_flags')


def typed_order_report(payload):
    cores=payload['order_cores'];statuses=payload['order_statuses']
    return {'status':'typed_order_prefix_observations_verified','open_order_callback_count':len(cores),
            'distinct_observed_order_identity_count':len({(row['client_id'],row['order_id'],row['permanent_id']) for row in cores}),
            'status_callback_count':len(statuses),**_links(cores,statuses),
            'complete_order_layout_verified':False,'manual_order_coverage_verified':False,
            'reservation_amounts_verified':False,'account_observation_atomic':False,'execution_authorized':False}


@dataclass(frozen=True)
class OrderReceiptConfig:
    public_path:Path
    public_sha256:str
    signing_path:Path|None=field(default=None,repr=False)
    openssl_path:Path=signatures.DEFAULT_OPENSSL

    @classmethod
    def from_env(cls):
        path=os.environ.get('NEXYDAO_ORDER_RECEIPT_PUBLIC_KEY_FILE','')
        pin=os.environ.get('NEXYDAO_ORDER_RECEIPT_PUBLIC_KEY_SHA256','')
        if not path or not re.fullmatch('[0-9a-f]{64}',pin):raise ProbeError('order_public_key_and_pin_required')
        private=os.environ.get('NEXYDAO_ORDER_RECEIPT_SIGNING_KEY_FILE','')
        return cls(Path(path),pin,Path(private) if private else None,Path(os.environ.get('NEXYDAO_OPENSSL_PATH',str(signatures.DEFAULT_OPENSSL))))


def save_typed_orders(config,settings,path):
    try:signatures.check_signer(settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path)
    except signatures.ReceiptSignatureError:raise ProbeError('order_signer_unavailable') from None
    payload=collect_orders(config,typed=True)
    try:receipt=signatures.sign(payload,settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except signatures.ReceiptSignatureError:raise ProbeError('order_signing_failed') from None
    if len(json.dumps(receipt,sort_keys=True,indent=2).encode())>LIMIT:raise ProbeError('orders_receipt_size_limit')
    validate_orders(payload,config.expected_account)
    digest=save_snapshot(path,receipt)
    return {**typed_order_report(payload),'receipt_sha256':digest}


def typed_orders_from_bytes(raw,config,settings,now=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT:raise ProbeError('orders_receipt_size_limit')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        receipt=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        signatures.verify(receipt,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except (ValueError,TypeError,RecursionError):raise ProbeError('typed_order_signature_denied') from None
    payload=validate_orders(receipt['payload'],config.expected_account,now)
    if payload['schema_version']!=2:raise ProbeError('typed_order_schema_required')
    return payload


def load_typed_orders(config,settings,path):
    try:raw=signatures._read(path,LIMIT)
    except signatures.ReceiptSignatureError:raise ProbeError('typed_order_receipt_unavailable') from None
    return typed_orders_from_bytes(raw,config,settings)
