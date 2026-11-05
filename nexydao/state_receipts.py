"""Dedicated public-only cash/position receipt verification, no HMAC fallback.

Reuses the existing read-only collection and schema-3 validation. A valid local
signature does not establish usable funding, atomicity or complete reconciliation.
"""
from dataclasses import dataclass,field
import json
import os
from pathlib import Path
import re

from .ibkr import ProbeError,save_snapshot
from .reconciliation import collect_state,validate_state
from . import research_signatures as signatures

DOMAIN=b'NexyDAO:broker-cash-positions:ed25519:v1\x00'
LIMIT=65536


@dataclass(frozen=True)
class StateReceiptConfig:
    public_path:Path
    public_sha256:str
    signing_path:Path|None=field(default=None,repr=False)
    openssl_path:Path=signatures.DEFAULT_OPENSSL

    @classmethod
    def from_env(cls):
        public=os.environ.get('NEXYDAO_STATE_RECEIPT_PUBLIC_KEY_FILE','')
        pin=os.environ.get('NEXYDAO_STATE_RECEIPT_PUBLIC_KEY_SHA256','')
        if not public or not re.fullmatch('[0-9a-f]{64}',pin):raise ProbeError('state_public_key_and_pin_required')
        private=os.environ.get('NEXYDAO_STATE_RECEIPT_SIGNING_KEY_FILE','')
        return cls(Path(public),pin,Path(private) if private else None,
                   Path(os.environ.get('NEXYDAO_OPENSSL_PATH',str(signatures.DEFAULT_OPENSSL))))


def _current_schema(payload,config,now=None):
    validate_state(payload,config.expected_account,now)
    if payload['schema_version']!=3:raise ProbeError('public_state_schema3_required')
    return payload


def state_report(payload):
    from .reconciliation import number
    cash={(row['tag'],row['currency']) for row in payload['cash']}
    currencies={currency for _,currency in cash}
    return {'status':'public_cash_position_observations_verified','cash_row_count':len(payload['cash']),
        'position_row_count':len(payload['positions']),'cash_currency_count':len({row['currency'] for row in payload['cash']}),
        'per_currency_scope_verified':payload['per_currency_scope_verified'],
        'per_currency_cash_pairs_complete':payload['per_currency_scope_verified'] and all(
            ('CashBalance',currency) in cash and ('SettledCash',currency) in cash for currency in currencies),
        'usd_settled_cash_observed':payload['per_currency_scope_verified'] and ('SettledCash','USD') in cash,
        'negative_currency_cash_observed':any(number(row['value'])<0 for row in payload['cash']),
        'short_position_observed':any(number(row['quantity'])<0 for row in payload['positions']),
        'unsupported_instrument_observed':any(row['security_type']!='STK' for row in payload['positions']),
        'settled_cash_schedule_unparsed':payload['settled_cash_schedule_unparsed'],
        'broker_reconciliation':False,'broker_funding_verified':False,'account_observation_atomic':False,
        'ledger_imported':False,'execution_authorized':False}


def save_public_state(config,settings,path):
    try:signatures.check_signer(settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path)
    except signatures.ReceiptSignatureError:raise ProbeError('state_signer_unavailable') from None
    payload=_current_schema(collect_state(config),config)
    try:receipt=signatures.sign(payload,settings.signing_path,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except signatures.ReceiptSignatureError:raise ProbeError('state_signing_failed') from None
    if len(json.dumps(receipt,sort_keys=True,indent=2).encode())>LIMIT:raise ProbeError('public_state_receipt_size')
    _current_schema(payload,config)
    return {**state_report(payload),'receipt_sha256':save_snapshot(path,receipt)}


def public_state_from_bytes(raw,config,settings,now=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT:raise ProbeError('public_state_receipt_size')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        receipt=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        signatures.verify(receipt,settings.public_path,settings.public_sha256,settings.openssl_path,domain=DOMAIN)
    except (ValueError,TypeError,RecursionError):raise ProbeError('public_state_signature_denied') from None
    return _current_schema(receipt['payload'],config,now)


def load_public_state(config,settings,path):
    try:raw=signatures._read(path,LIMIT)
    except signatures.ReceiptSignatureError:raise ProbeError('public_state_receipt_unavailable') from None
    return public_state_from_bytes(raw,config,settings)
