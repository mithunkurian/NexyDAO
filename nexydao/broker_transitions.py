"""Fresh paired observations and visible-fill delta diagnostics; never funding.

Callers authenticate all four payloads. No historical TTL bypass, execution-time
inference, rolling-query completeness claim, settlement model or ledger mutation.
"""
from decimal import Decimal,localcontext
import hashlib
import os
from pathlib import Path
import time

from .ibkr import ProbeError
from .market import canonical
from .reconciliation import validate_state,number
from .executions import validate_executions,ExecutionReceiptConfig,load_executions
from .state_receipts import StateReceiptConfig,load_public_state,state_report


def transition_report(before_state,after_state,before_executions,after_executions,config,now=None):
    now=time.time() if now is None else now
    states=(before_state,after_state);queries=(before_executions,after_executions)
    for payload in states:
        validate_state(payload,config.expected_account,now)
        if payload['schema_version']!=3:raise ProbeError('transition_state_schema3_required')
    for payload in queries:validate_executions(payload,config.expected_account,now)
    # Equal instants do not establish a new observation. Each pair must advance
    # without overlapping its predecessor; state and fill queries remain separate.
    for before,after in (states,queries):
        if not before['received_at']<=after['started_at'] or not before['started_at']<after['started_at']:
            raise ProbeError('transition_observations_not_ordered')
    if max(before_state['received_at'],before_executions['received_at'])>min(after_state['started_at'],after_executions['started_at']):
        raise ProbeError('transition_pairs_overlap')
    opening={r['execution_sha256']:r for r in before_executions['executions']}
    closing={r['execution_sha256']:r for r in after_executions['executions']}
    vanished=set(opening)-set(closing)
    changed={key for key in opening.keys()&closing.keys() if canonical(opening[key])!=canonical(closing[key])}
    new=[closing[key] for key in sorted(closing.keys()-opening.keys())]
    identities={}
    for row in (*before_state['positions'],*after_state['positions'],*opening.values(),*closing.values()):
        identities.setdefault(row['contract_id'],set()).add((row['symbol'],row['security_type'],row['currency']))
    conflicts=sum(len(values)>1 for values in identities.values())
    reasons=[]
    if vanished:reasons.append('prior_execution_disappeared_from_query')
    if changed:reasons.append('prior_execution_content_changed')
    if conflicts:reasons.append('contract_metadata_changed')
    if any(q['correction_observed'] for q in queries):reasons.append('execution_correction_requires_review')
    if any(q['pending_price_revision_observed'] for q in queries):reasons.append('execution_price_revision_pending')
    if any(r['security_type']!='STK' for s in states for r in s['positions']):reasons.append('unsupported_position_instrument')
    arithmetic_available=not reasons
    cash=[{r['currency']:number(r['value']) for r in s['cash'] if r['tag']=='CashBalance'} for s in states]
    all_cash_currencies={r['currency'] for s in states for r in s['cash']}
    fill_currencies={r[key] for r in new for key in ('currency','commission_currency')}
    cash_scope=all(s['per_currency_scope_verified'] for s in states)
    required=all_cash_currencies|fill_currencies
    comparable=cash[0].keys()&cash[1].keys() if cash_scope else set()
    missing_cash=required-set(comparable)
    if not cash_scope:reasons.append('per_currency_cash_scope_unverified')
    if missing_cash:reasons.append('cash_currency_observation_missing')
    # 50 fills * two 28-digit operands plus sums/residuals fit exactly here.
    # Do not let the process Decimal context round tiny unexplained changes away.
    with localcontext() as context:
        context.prec=100
        holdings=[{r['contract_id']:number(r['quantity']) for r in s['positions']} for s in states]
        contracts=set(holdings[0])|set(holdings[1])|{r['contract_id'] for r in new}
        quantity={key:Decimal(0) for key in contracts};money={key:Decimal(0) for key in required}
        if arithmetic_available:
            for row in new:
                signed=number(row['quantity'])*(1 if row['side']=='BOT' else -1)
                quantity[row['contract_id']]+=signed
                money[row['currency']]-=signed*number(row['price'])
                money[row['commission_currency']]-=number(row['commission'])
        position_changes=sum(holdings[1].get(k,0)!=holdings[0].get(k,0) for k in contracts)
        cash_changes=sum(cash[1][k]!=cash[0][k] for k in comparable)
        position_residuals=(sum(holdings[1].get(k,0)-holdings[0].get(k,0)!=quantity[k] for k in contracts)
                            if arithmetic_available else None)
        cash_residuals=(sum(cash[1][k]-cash[0][k]!=money[k] for k in comparable)
                        if arithmetic_available and cash_scope else None)
    if position_residuals:reasons.append('position_delta_not_matched_by_new_visible_fills')
    if cash_residuals:reasons.append('cash_delta_not_matched_by_new_visible_fills_and_fees')
    summaries=[state_report(s) for s in states]
    if any(s['negative_currency_cash_observed'] for s in summaries):reasons.append('negative_currency_cash_requires_resolution')
    if any(s['short_position_observed'] for s in summaries):reasons.append('short_position_requires_review')
    if any(s['settled_cash_schedule_unparsed'] for s in summaries):reasons.append('settlement_schedule_semantics_unverified')
    if any(not s['per_currency_cash_pairs_complete'] for s in summaries):reasons.append('per_currency_settled_cash_evidence_incomplete')
    matches=(arithmetic_available and cash_scope and not missing_cash
             and position_residuals==0 and cash_residuals==0)
    # A newly visible fill may predate the opening state. Broker wall-clock text
    # and query arrival times do not prove attribution to the state interval.
    reasons.extend(('execution_interval_attribution_unverified','manual_and_transfer_coverage_unverified',
                    'settlement_and_corporate_actions_unverified','stable_atomic_account_observation',
                    'actual_monetary_reservations','funding_and_authorizer_acceptance'))
    payloads=dict(zip(('before_state','after_state','before_executions','after_executions'),(*states,*queries)))
    return {'status':'partial_broker_transition_diagnostics','before_state':summaries[0],'after_state':summaries[1],
        'new_visible_execution_count':len(new),
        'retained_execution_count':len(opening.keys()&closing.keys()),
        'disappeared_execution_count':len(vanished),'changed_execution_count':len(changed),
        'contract_metadata_conflict_count':conflicts,'visible_fill_arithmetic_available':arithmetic_available,
        'position_change_count':position_changes,'position_residual_count':position_residuals,
        'comparable_cash_currency_count':len(comparable),'missing_cash_currency_count':len(missing_cash),
        'cash_change_currency_count':cash_changes,'cash_residual_currency_count':cash_residuals,
        'visible_deltas_match':matches,'missing_checks':reasons,
        'receipt_payloads_sha256':{k:hashlib.sha256(canonical(v)).hexdigest() for k,v in payloads.items()},
        'evaluated_at':now,'evidence_expires_at':min(v['expires_at'] for v in payloads.values()),
        'execution_interval_attribution_verified':False,'settled_cash_reconciled':False,
        'account_observation_atomic':False,'broker_reconciliation':False,'broker_funding_verified':False,
        'reservation_amounts_verified':False,'ledger_imported':False,'funding_authorized':False,'execution_authorized':False}


def load_transition_report(config,before_state_path,before_executions_path):
    current_state=os.environ.get('NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT','')
    current_executions=os.environ.get('NEXYDAO_EXECUTIONS_SNAPSHOT','')
    if not before_state_path or not before_executions_path or not current_state or not current_executions:
        raise ProbeError('four_explicit_transition_receipt_paths_required')
    settings=StateReceiptConfig.from_env();fills=ExecutionReceiptConfig.from_env()
    before_state=load_public_state(config,settings,Path(before_state_path))
    before_executions=load_executions(config,fills,Path(before_executions_path))
    after_state=load_public_state(config,settings,Path(current_state))
    after_executions=load_executions(config,fills,Path(current_executions))
    # All four are revalidated at a common time after the last signature check.
    return transition_report(before_state,after_state,before_executions,after_executions,config)
