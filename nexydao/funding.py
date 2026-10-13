"""Independent, persistent funding denial diagnostics. Never an execution permit."""
import hashlib
import json
import re
import time
import uuid

from .market import canonical
from .reconciliation import number, validate_state, reconcile_state


def settlement_shape(raw):
    """Redact amounts. Recognition of syntax never establishes settlement semantics."""
    # Only publish character classes and punctuation from this closed grammar.
    # Untrusted values/text never appear in stdout, model memory or case records.
    if not raw: return 'empty'
    if not re.fullmatch(r'[0-9.,:;=|/ +\-TtZz\[\]{}]+',raw): return 'unsupported_text'
    shape=re.sub(r'[0-9]+','N',raw)
    return shape[:160] if len(shape)<=160 else 'bounded_long_structure'


def evaluate_funding(payload, config, ledger, policy, now=None):
    now=time.time() if now is None else now
    validate_state(payload,config.expected_account,now)
    policy.assert_current()
    comparison=reconcile_state(payload,config,ledger,now)
    rows=payload['cash']
    cash_currencies=sorted({r['currency'] for r in rows})
    negative=sorted({r['currency'] for r in rows if number(r['value'])<0})
    disagree=[]
    for c in cash_currencies:
        cash={r['tag']:number(r['value']) for r in rows if r['currency']==c}
        if 'CashBalance' in cash and 'TotalCashBalance' in cash and cash['CashBalance']!=cash['TotalCashBalance']:
            disagree.append(c)
    reasons=set(comparison['missing_checks'])
    reasons.update({'authorization_and_executor_incomplete','broker_capital_allocation_unverified'})
    if negative: reasons.add('negative_currency_cash_requires_resolution')
    if disagree: reasons.add('cash_field_difference_requires_explanation')
    if comparison['short_position_observed']: reasons.add('owner_no_short_selling')
    if comparison['unsupported_instrument_observed']: reasons.add('instrument_eligibility_unverified')
    if not comparison['positions_match_simulation']: reasons.add('positions_mismatch_or_unidentified')
    if comparison['simulated_cash_comparison']!='match': reasons.add('simulation_cash_not_reconciled')
    if payload['settled_cash_schedule_unparsed']: reasons.add('settlement_schedule_semantics_unverified')
    if policy.document()['additional_rules']: reasons.add('additional_owner_rule_enforcement_pending')
    schedules=[{'currency':r['currency'],'value_sha256':hashlib.sha256(r['raw_value'].encode()).hexdigest(),
                'redacted_shape':settlement_shape(r['raw_value']), 'semantics_verified':False}
               for r in payload.get('settlement_observations',[])]
    return {'status':'funding_denied','funding_authorized':False,'execution_authorized':False,
            'broker_funding_verified':False,'broker_reconciliation':False,
            'receipt_payload_sha256':hashlib.sha256(canonical(payload)).hexdigest(),
            'receipt_schema_version':payload['schema_version'],'observed_at':payload['received_at'],
            'evidence_expires_at':payload['expires_at'],'evaluated_at':now,
            'owner_policy_sha256':policy.digest,'ledger_revision':comparison['ledger_revision'],
            'negative_cash_currencies':negative,'cash_fields_differ_currencies':disagree,
            'negative_cash_cause':'unresolved' if negative else 'not_observed',
            'cause_evidence_required': ['broker_statement_of_funds','cash_report_settlement_balances'] if negative else [],
            'settlement_observations':schedules,'blocking_reasons':sorted(reasons),
            'balances_imported':False,'fx_conversion_performed':False,
            'comparison':comparison}


def record_funding_review(payload,config,ledger,policy):
    db=ledger.db
    db.execute('''CREATE TABLE IF NOT EXISTS funding_reviews (
        id TEXT PRIMARY KEY, created REAL NOT NULL, report TEXT NOT NULL)''')
    db.commit()
    db.execute('BEGIN IMMEDIATE')
    try:
        result=evaluate_funding(payload,config,ledger,policy)
        # Recheck before storing: a review cannot span an evidence/policy change.
        validate_state(payload,config.expected_account)
        policy.assert_current()
        ledger.assert_revision(result['ledger_revision'])
        identifier=str(uuid.uuid4())
        result['review_id']=identifier
        db.execute('INSERT INTO funding_reviews VALUES(?,?,?)',(identifier,time.time(),json.dumps(result,allow_nan=False)))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
