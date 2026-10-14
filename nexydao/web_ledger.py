"""Paper-only, fixed-GET Client Portal ledger reader; TLS verification is mandatory."""
import hashlib
import hmac
import http.client
import json
import math
import os
import re
import ssl
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .ibkr import BrokerConfig, ProbeError, paper_account, save_snapshot
from .market import canonical, read_key
from .reconciliation import TTL, currency, number

SOURCE = 'ibkr_paper_web_currency_ledger'
LIMIT = 65536
SSO_INTERVAL = 61
ACCOUNTS_INTERVAL = 5.1
USER_AGENT = 'NexyDAO/0.1 (paper currency ledger)'


@dataclass(frozen=True)
class WebConfig:
    expected_account: str
    ca_file: Path
    timeout: int = 90

    def __post_init__(self):
        BrokerConfig(expected_account=self.expected_account)
        if not self.expected_account: raise ProbeError('exact_account_pin_required')
        if type(self.timeout) is not int or not 70<=self.timeout<=120: raise ValueError('Web collection timeout must be 70 to 120 seconds')
        if not self.ca_file.is_file(): raise ValueError('Explicit trusted local CA file required')

    @classmethod
    def from_env(cls):
        ca=os.environ.get('NEXYDAO_WEB_CA_FILE','')
        if not ca: raise ValueError('Trusted Client Portal CA file required')
        return cls(os.environ.get('NEXYDAO_IBKR_EXPECTED_ACCOUNT',''),Path(ca),
                   int(os.environ.get('NEXYDAO_WEB_TIMEOUT_SECONDS','90')))


def claim_request(config,path,now=None):
    """Persist attempted request times across CLI processes, including failures.

    This is local pacing coordination, not tamper-resistant authorization. All
    collectors sharing this Gateway must use the same protected CA directory.
    """
    now=time.time() if now is None else now
    if type(now) not in (int,float) or not math.isfinite(now) or now<=0:
        raise ProbeError('web_pacing_clock_invalid')
    endpoint='sso' if path.endswith('/sso/validate') else 'accounts' if path.endswith('/portfolio/accounts') else 'ledger'
    interval={'sso':SSO_INTERVAL,'accounts':ACCOUNTS_INTERVAL,'ledger':1}[endpoint]
    path=config.ca_file.parent/'web-pacing.sqlite3'
    if path.is_symlink(): raise ProbeError('web_pacing_storage_invalid')
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
    except FileExistsError: pass
    if os.name=='posix' and path.stat().st_mode & 0o077:
        raise ProbeError('web_pacing_storage_not_private')
    connection=sqlite3.connect(path,timeout=1)
    try:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('CREATE TABLE IF NOT EXISTS requests(endpoint TEXT PRIMARY KEY, attempted REAL NOT NULL)')
        row=connection.execute('SELECT attempted FROM requests WHERE endpoint=?',(endpoint,)).fetchone()
        if row and (type(row[0]) not in (int,float) or not math.isfinite(row[0]) or row[0]<=0):
            raise ProbeError('web_pacing_storage_invalid')
        if row and now-row[0]<interval: raise ProbeError('web_request_pacing_wait_required')
        connection.execute('INSERT OR REPLACE INTO requests VALUES (?,?)',(endpoint,now))
        connection.commit()
    except sqlite3.Error: raise ProbeError('web_pacing_storage_failed') from None
    finally: connection.close()


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


def parse_json(body,decimal=True):
    if len(body)>LIMIT: raise ProbeError('web_response_size_limit')
    def constant(value): raise ValueError('Nonfinite JSON')
    try: return json.loads(body,parse_float=Decimal if decimal else float,parse_constant=constant,object_pairs_hook=unique)
    except (ValueError,TypeError,UnicodeError): raise ProbeError('invalid_web_json') from None


def get_json(config,path,timeout):
    allowed={'/v1/api/sso/validate','/v1/api/portfolio/accounts',
             f'/v1/api/portfolio/{config.expected_account}/ledger'}
    if path not in allowed: raise PermissionError('Web mutations and arbitrary paths unavailable')
    # No environment proxies, redirects, cookies from the browser, or login automation.
    context=ssl.create_default_context(cafile=str(config.ca_file))
    if context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname:
        raise ProbeError('web_tls_verification_required')
    claim_request(config,path)
    connection=http.client.HTTPSConnection('127.0.0.1',5000,timeout=min(timeout,15),context=context)
    try:
        connection.request('GET',path,headers={'Accept':'application/json','Accept-Encoding':'identity','User-Agent':USER_AGENT})
        response=connection.getresponse()
        if response.status!=200:
            error={401:'web_authentication_required',403:'web_access_denied',429:'web_rate_limited'}.get(response.status,'web_request_not_successful')
            raise ProbeError(error)
        if response.getheader('Content-Type','').split(';')[0].strip().lower()!='application/json':
            raise ProbeError('web_json_content_required')
        if response.getheader('Content-Encoding','identity').lower()!='identity':
            raise ProbeError('web_compression_unavailable')
        return parse_json(response.read(LIMIT+1))
    except (OSError,http.client.HTTPException): raise ProbeError('web_transport_failed') from None
    finally: connection.close()


def session_identity(data):
    # Current official documentation uses success.value; legacy Gateway is flat.
    # Never guess recursively or accept conflicting outer identity fields.
    if isinstance(data,dict) and set(data)=={'success'}:
        success=data['success']
        if isinstance(success,dict) and set(success)=={'value'}: data=success['value']
    if not isinstance(data,dict) or data.get('RESULT') is not True: raise ProbeError('web_session_unverified')
    modes=[data[k] for k in ('LOGIN_TYPE','loginType') if k in data]
    if not modes or any(type(x) is not int or x!=2 for x in modes): raise ProbeError('web_paper_session_required')
    auth,remaining=data.get('AUTH_TIME'),data.get('EXPIRES')
    if type(auth) is not int or not 0<auth<10**15 or type(remaining) is not int or not 0<remaining<10**9:
        raise ProbeError('web_session_time_unverified')
    return auth,remaining


def check_accounts(data,expected):
    if not isinstance(data,list) or len(data)!=1 or not isinstance(data[0],dict): raise ProbeError('single_web_account_required')
    row=data[0]
    if row.get('id')!=expected or row.get('accountId')!=expected: raise ProbeError('web_account_mismatch')
    paper_account(row['id'],expected)


def monetary(value):
    if type(value) not in (int,Decimal): raise ProbeError('web_numeric_cash_required')
    decimal=Decimal(value)
    if not decimal.is_finite() or decimal.adjusted()>15 or decimal.as_tuple().exponent < -12:
        raise ProbeError('web_numeric_cash_required')
    result=format(decimal,'f');number(result)
    return result


def collect_web_ledger(config,get=get_json,clock=time.time,monotonic=time.monotonic,sleep=time.sleep):
    identity_started=clock();deadline=monotonic()+config.timeout
    def read(path):
        remaining=deadline-monotonic()
        if remaining<=0: raise ProbeError('web_collection_timeout')
        result=get(config,path,remaining)
        if monotonic()>deadline: raise ProbeError('web_collection_timeout')
        return result
    auth,remaining=session_identity(read('/v1/api/sso/validate'))
    session_expiry=identity_started+remaining/1000
    def pause(seconds):
        if monotonic()+seconds>=deadline or clock()+seconds>=session_expiry:
            raise ProbeError('web_collection_timeout')
        sleep(seconds)
    # Wait before collecting cash so both identity checks respect 1/min while
    # native cash timestamps and the final receipt retain their 60-second TTL.
    pause(SSO_INTERVAL)
    started=clock()
    check_accounts(read('/v1/api/portfolio/accounts'),config.expected_account)
    accounts_checked=monotonic()
    data=read(f'/v1/api/portfolio/{config.expected_account}/ledger')
    if not isinstance(data,dict) or not 1<=len(data)<=40: raise ProbeError('invalid_web_currency_ledger')
    rows=[]
    for denomination,row in sorted(data.items()):
        if not (currency(denomination) or denomination=='BASE') or not isinstance(row,dict):
            raise ProbeError('invalid_web_ledger_currency')
        if row.get('acctcode')!=config.expected_account or row.get('currency')!=denomination:
            raise ProbeError('web_ledger_identity_mismatch')
        if denomination=='BASE': continue
        stamp=row.get('timestamp')
        if type(stamp) is not int or not 0<stamp<10**12: raise ProbeError('web_ledger_time_unverified')
        rows.append({'currency':denomination,'cash_balance':monetary(row.get('cashbalance')),
                     'settled_cash':monetary(row.get('settledcash')),'observed_at':stamp})
    if not rows: raise ProbeError('web_currency_ledger_missing')
    if session_identity(read('/v1/api/sso/validate'))[0]!=auth: raise ProbeError('web_session_changed_during_collection')
    pause(max(0,ACCOUNTS_INTERVAL-(monotonic()-accounts_checked)))
    check_accounts(read('/v1/api/portfolio/accounts'),config.expected_account)
    received=clock()
    expiry=min(started+TTL,session_expiry,min(r['observed_at']+TTL for r in rows))
    payload={'schema_version':1,'source':SOURCE,'scope':'per_currency_ledger',
             'account_sha256':hashlib.sha256(config.expected_account.encode()).hexdigest(),
             'paper_session_verified':True,'started_at':started,'received_at':received,
             'expires_at':expiry,'cash':rows}
    return validate_web_ledger(payload,config.expected_account,received)


def validate_web_ledger(payload,account,now=None):
    now=time.time() if now is None else now
    keys={'schema_version','source','scope','account_sha256','paper_session_verified',
          'started_at','received_at','expires_at','cash'}
    if not isinstance(payload,dict) or set(payload)!=keys: raise ProbeError('invalid_web_ledger_schema')
    paper_account(account,account)
    if (type(payload['schema_version']) is not int or payload['schema_version']!=1 or payload['source']!=SOURCE
            or payload['scope']!='per_currency_ledger' or payload['paper_session_verified'] is not True
            or payload['account_sha256']!=hashlib.sha256(account.encode()).hexdigest()):
        raise ProbeError('invalid_web_ledger_identity')
    start,received,expiry=[payload[k] for k in ('started_at','received_at','expires_at')]
    if any(type(t) not in (float,int) or not 0<t<1e12 for t in (start,received,expiry)):
        raise ProbeError('invalid_web_receipt_time')
    if not start<=received<=now<expiry<=start+TTL: raise ProbeError('web_ledger_expired_or_future')
    rows=payload['cash']
    if not isinstance(rows,list) or not 1<=len(rows)<=40: raise ProbeError('invalid_web_ledger_rows')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'currency','cash_balance','settled_cash','observed_at'}:
            raise ProbeError('invalid_web_ledger_row')
        if not currency(row['currency']) or row['currency'] in seen: raise ProbeError('invalid_web_ledger_currency')
        seen.add(row['currency']);number(row['cash_balance']);number(row['settled_cash'])
        stamp=row['observed_at']
        if type(stamp) is not int or not 0<stamp<=received or expiry>stamp+TTL:
            raise ProbeError('web_ledger_native_timestamp_invalid')
    return payload


def save_web_ledger(config,key_path,path):
    key=read_key(key_path);payload=collect_web_ledger(config)
    receipt={'payload':payload,'signature':hmac.new(key,canonical(payload),hashlib.sha256).hexdigest()}
    if len(canonical(receipt))>LIMIT: raise ProbeError('web_receipt_size_limit')
    return {'status':'web_currency_ledger_collected','receipt_sha256':save_snapshot(path,receipt),
            'currencies':[r['currency'] for r in payload['cash']],
            'negative_cash_currencies':[r['currency'] for r in payload['cash'] if min(number(r['cash_balance']),number(r['settled_cash']))<0],
            'funding_authorized':False,'execution_authorized':False}


def load_web_ledger(config,key_path,path):
    with Path(path).open('rb') as stream: body=stream.read(LIMIT+1)
    receipt=parse_json(body,decimal=False)
    try:
        if not isinstance(receipt,dict) or set(receipt)!={'payload','signature'} or not isinstance(receipt['signature'],str): raise ValueError()
        actual=hmac.new(read_key(key_path),canonical(receipt['payload']),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual,receipt['signature']): raise ValueError()
    except (ValueError,TypeError): raise ProbeError('invalid_web_ledger_signature') from None
    return validate_web_ledger(receipt['payload'],config.expected_account)
