"""Shadow-only signed permit protocol. No broker, provider or order authority.

This is an S3 protocol foundation, not the independent production authorizer.
Callers must be trusted: current funding/risk/reconciliation acceptance is absent.
The dedicated shadow domain/purpose can never be an executable order permit.
"""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time

from . import research_signatures as signatures
from .owner_policy import amount

DOMAIN = b'NexyDAO:paper-shadow-permit:ed25519:v1\x00'
PURPOSE = 'paper_shadow_only'
INTENT_FIELDS = {'account','contract_id','symbol','currency','side','quantity',
                 'limit_price_usd','fee_cap_usd','max_debit_usd','reservation_id',
                 'quote_sha256','portfolio_sha256','review_sha256'}
PAYLOAD_FIELDS = {'schema_version','purpose','mode','intent','policy_sha256',
                  'policy_version','epoch','nonce','issued_at','expires_at'}


class PermitError(ValueError):
    """Fixed error codes, without private state or crypto tool output."""


def _hex(value, length=64):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None


def _number(value, zero=False):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,8}(?:\.[0-9]{1,8})?',value):
        raise PermitError('invalid_shadow_amount')
    number=Decimal(value)
    if number<0 or (not zero and number==0):raise PermitError('invalid_shadow_amount')
    return number


def validate_intent(intent, policy):
    if not isinstance(intent,dict) or set(intent)!=INTENT_FIELDS:
        raise PermitError('invalid_shadow_intent')
    if (not isinstance(intent['account'],str) or not re.fullmatch(r'DU[0-9]{1,12}',intent['account'])
            or type(intent['contract_id']) is not int or not 0<intent['contract_id']<2**31
            or not isinstance(intent['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,11}',intent['symbol'])
            or intent['currency']!='USD' or intent['side']!='BUY'
            or not _hex(intent['reservation_id'],32)
            or any(not _hex(intent[name]) for name in ('quote_sha256','portfolio_sha256','review_sha256'))):
        raise PermitError('invalid_shadow_scope')
    quantity=_number(intent['quantity']);price=_number(intent['limit_price_usd'])
    fees=_number(intent['fee_cap_usd'],zero=True);debit=_number(intent['max_debit_usd'])
    document=policy.document()
    if (quantity*price+fees>debit or debit>amount(document['max_position_usd'])
            or intent['symbol'] in document['blocked_symbols'] or document['additional_rules']):
        raise PermitError('shadow_policy_or_debit_denied')


def _now(now):
    value=int(time.time()) if now is None else now
    if type(value) is not int or not 0<value<2**53:raise PermitError('invalid_shadow_clock')
    return value


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise PermitError('duplicate_shadow_field')
        result[key]=value
    return result


def decode(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=8192:raise PermitError('shadow_permit_size')
    try:
        return json.loads(raw,object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(PermitError('invalid_shadow_json')))
    except (UnicodeError,ValueError,RecursionError):
        raise PermitError('invalid_shadow_json') from None


def _validate_payload(payload, intent, policy, now):
    if not isinstance(payload,dict) or set(payload)!=PAYLOAD_FIELDS:
        raise PermitError('invalid_shadow_payload')
    if (type(payload['schema_version']) is not int or payload['schema_version']!=1
            or payload['purpose']!=PURPOSE or payload['mode']!='paper'
            or payload['intent']!=intent or payload['policy_sha256']!=policy.digest
            or type(payload['policy_version']) is not int or payload['policy_version']!=policy.document()['policy_version']
            or not _hex(payload['epoch'],32) or not _hex(payload['nonce'],32)
            or type(payload['issued_at']) is not int or type(payload['expires_at']) is not int
            or not 0<payload['issued_at']<=now<payload['expires_at']
            or not 0<payload['expires_at']-payload['issued_at']<=60):
        raise PermitError('shadow_binding_or_expiry_denied')


class ShadowLedger:
    """Dedicated private SQLite file; killed by default, explicit owner re-arm.

    No auto-create/reset on ordinary use. Keep this separate from the cost DB.
    File protection is enforced on Unix; Windows ACLs require operator setup.
    The database and code are trusted; rollback/restore is not prevented here.
    """
    def __init__(self,path):
        self.path=Path(path).absolute()

    def _metadata(self, file=True):
        parent=self.path.parent
        for component in (parent,*parent.parents):
            info=component.lstat()
            if not stat.S_ISDIR(info.st_mode):raise PermitError('shadow_ledger_parent')
        info=parent.lstat()
        if os.name=='posix' and (info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700):
            raise PermitError('shadow_ledger_parent')
        if file:
            info=self.path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                    or os.name=='posix' and (info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600)):
                raise PermitError('shadow_ledger_permissions')

    @contextmanager
    def _transaction(self):
        self._metadata()
        connection=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try:
            connection.execute('PRAGMA trusted_schema=OFF')
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.execute('COMMIT')
        except BaseException:
            if connection.in_transaction:connection.execute('ROLLBACK')
            raise
        finally:connection.close()

    def initialize(self):
        self._metadata(file=False)
        descriptor=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(descriptor)
        with self._transaction() as connection:
            connection.execute('CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1), killed INTEGER NOT NULL CHECK(killed IN (0,1)), epoch TEXT NOT NULL, policy TEXT NOT NULL)')
            connection.execute('INSERT INTO control VALUES (1,1,?,?)',(secrets.token_hex(16),''))
            connection.execute('CREATE TABLE consumed (nonce TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL, consumed_at INTEGER NOT NULL)')

    def stop(self):
        with self._transaction() as connection:
            connection.execute('UPDATE control SET killed=1,epoch=?,policy=? WHERE id=1',(secrets.token_hex(16),''))

    def arm(self,policy):
        policy.assert_current()
        with self._transaction() as connection:
            connection.execute('UPDATE control SET killed=0,epoch=?,policy=? WHERE id=1',(secrets.token_hex(16),policy.digest))

    @staticmethod
    def _active(connection,policy):
        rows=connection.execute('SELECT killed,epoch,policy FROM control').fetchall()
        if len(rows)!=1 or rows[0][0]!=0 or rows[0][2]!=policy.digest or not _hex(rows[0][1],32):
            raise PermitError('shadow_stopped_or_policy_changed')
        return rows[0][1]

    def epoch(self,policy):
        with self._transaction() as connection:return self._active(connection,policy)

    def _consume(self,payload,intent,policy,now=None):
        # A post-verification private operation; public entry point is consume_shadow.
        with self._transaction() as connection:
            policy.assert_current()
            validate_intent(intent,policy)
            _validate_payload(payload,intent,policy,_now(now))
            if self._active(connection,policy)!=payload['epoch']:raise PermitError('shadow_epoch_revoked')
            if connection.execute('SELECT count(*) FROM consumed').fetchone()[0]>=10000:
                raise PermitError('shadow_ledger_capacity_stop')
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            try:
                connection.execute('INSERT INTO consumed VALUES (?,?,?)',(payload['nonce'],digest,_now(now)))
            except sqlite3.IntegrityError:raise PermitError('shadow_replay_denied') from None
        policy.assert_current()


def issue_shadow(intent,policy,ledger,private_path,public_path,pin,executable,*,now=None,ttl=30):
    """Trusted fixture/shadow issuer, never proof of funding, reviews or risk."""
    policy.assert_current();validate_intent(intent,policy)
    issued=_now(now)
    if type(ttl) is not int or not 1<=ttl<=60:raise PermitError('shadow_ttl_limit')
    payload={'schema_version':1,'purpose':PURPOSE,'mode':'paper','intent':dict(intent),
             'policy_sha256':policy.digest,'policy_version':policy.document()['policy_version'],
             'epoch':ledger.epoch(policy),'nonce':secrets.token_hex(16),'issued_at':issued,'expires_at':issued+ttl}
    receipt=signatures.sign(payload,private_path,public_path,pin,executable,domain=DOMAIN)
    policy.assert_current()
    return receipt


def consume_shadow(raw,intent,policy,ledger,public_path,pin,executable,*,now=None):
    policy.assert_current();validate_intent(intent,policy)
    receipt=decode(raw)
    try:signatures.verify(receipt,public_path,pin,executable,domain=DOMAIN)
    except signatures.ReceiptSignatureError:raise PermitError('shadow_signature_denied') from None
    ledger._consume(receipt['payload'],intent,policy,now)
    return {'status':'shadow_permit_consumed','execution_authorized':False,'broker_submission':False}
