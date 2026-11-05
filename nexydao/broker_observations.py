"""Partial cross-observation diagnostics; never account reconstruction or a permit.

Callers must authenticate every payload with its dedicated public receipt loader.
This module rechecks identity/scope/freshness after all receipts have been read.
It does not sum fills, infer opening balances, import money or release reservations.
"""
import hashlib
import os
from pathlib import Path
import time

from .ibkr import ProbeError
from .market import canonical
from .reconciliation import validate_state,number
from .orders import validate_orders
from .executions import validate_executions,execution_report,ExecutionReceiptConfig,load_executions
from .order_visibility import typed_order_report,OrderReceiptConfig,load_typed_orders
from .state_receipts import state_report,StateReceiptConfig,load_public_state


def cross_check_observations(state,orders,executions,config,now=None):
    now=time.time() if now is None else now
    validate_state(state,config.expected_account,now)
    validate_orders(orders,config.expected_account,now)
    validate_executions(executions,config.expected_account,now)
    if state['schema_version']!=3 or orders['schema_version']!=2:raise ProbeError('public_observation_schemas_required')
    contracts={}
    for row in (*state['positions'],*orders['order_cores'],*executions['executions']):
        contracts.setdefault(row['contract_id'],set()).add((row['symbol'],row['security_type'],row['currency']))
    contract_conflicts=sum(len(identities)>1 for identities in contracts.values())
    by_identity={};by_permanent={}
    for row in orders['order_cores']:
        identity=(row['client_id'],row['order_id'],row['permanent_id'])
        if row['permanent_id']>0:
            by_identity.setdefault(identity,[]).append(row)
            by_permanent.setdefault(row['permanent_id'],set()).add(identity)
    linked=unlinked=identity_conflicts=side_conflicts=order_contract_conflicts=quantity_excess=0
    for row in executions['executions']:
        identity=(row['client_id'],row['order_id'],row['permanent_id'])
        matches=by_identity.get(identity,[]) if row['permanent_id']>0 else []
        if not matches:
            unlinked+=1
            if row['permanent_id']>0 and row['permanent_id'] in by_permanent:identity_conflicts+=1
            continue
        linked+=1
        for key in ('contract_id','symbol','security_type','currency'):
            if any(order[key]!=row[key] for order in matches):order_contract_conflicts+=1;break
        side='BUY' if row['side']=='BOT' else 'SELL'
        if any(order['side']!=side for order in matches):side_conflicts+=1
        if any(number(row['cumulative_quantity'])>number(order['total_quantity']) for order in matches):quantity_excess+=1
    currencies={row['currency'] for row in state['cash']}
    unobserved_fee_currency=sum(row['commission_currency'] not in currencies for row in executions['executions'])
    diagnostics={'contract_metadata_conflict_count':contract_conflicts,
        'linked_execution_observation_count':linked,'unlinked_execution_observation_count':unlinked,
        'order_execution_identity_conflict_count':identity_conflicts,
        'order_execution_contract_conflict_count':order_contract_conflicts,
        'order_execution_side_conflict_count':side_conflicts,
        'execution_cumulative_quantity_above_observed_order_count':quantity_excess,
        'fee_currency_not_observed_in_cash_count':unobserved_fee_currency}
    conflicts=any((contract_conflicts,identity_conflicts,order_contract_conflicts,side_conflicts,quantity_excess))
    views={'state':state,'orders':orders,'executions':executions}
    windows_overlap=max(view['started_at'] for view in views.values())<=min(view['received_at'] for view in views.values())
    missing=['complete_order_and_manual_coverage','opening_balances_fills_fees_and_transfers',
             'actual_monetary_reservations','stable_atomic_account_observation','funding_and_authorizer_acceptance']
    state_summary=state_report(state);order_summary=typed_order_report(orders);fill_summary=execution_report(executions)
    if not state_summary['per_currency_cash_pairs_complete']:missing.append('per_currency_settled_cash_evidence_incomplete')
    if state_summary['negative_currency_cash_observed']:missing.append('negative_currency_cash_requires_resolution')
    if state_summary['settled_cash_schedule_unparsed']:missing.append('settlement_schedule_semantics_unverified')
    if state_summary['short_position_observed']:missing.append('short_position_requires_review')
    if state_summary['unsupported_instrument_observed']:missing.append('instrument_eligibility_unverified')
    if not order_summary['status_links_complete']:missing.append('order_status_identity_links_incomplete')
    if order_summary['quantity_disagreement_observed']:missing.append('order_quantity_disagreement')
    if order_summary['order_versions_changed_observed']:missing.append('order_changed_during_query')
    if fill_summary['correction_observed']:missing.append('execution_corrections_require_lifecycle_reconciliation')
    if fill_summary['pending_price_revision_observed']:missing.append('execution_prices_pending_revision')
    if fill_summary['fee_currency_mismatch_observed']:missing.append('commission_currency_accounting_unverified')
    if conflicts:missing.append('cross_observation_conflicts_require_review')
    if unobserved_fee_currency:missing.append('fee_currency_cash_evidence_missing')
    return {'status':'partial_broker_observation_cross_check','state':state_summary,
        'orders':order_summary,'executions':fill_summary,**diagnostics,
        'cross_observation_conflicts_observed':conflicts,'observation_windows_overlap':windows_overlap,
        'receipt_payloads_sha256':{key:hashlib.sha256(canonical(view)).hexdigest() for key,view in views.items()},
        'evaluated_at':now,'evidence_expires_at':min(view['expires_at'] for view in views.values()),
        'missing_checks':missing,'broker_reconciliation':False,'broker_funding_verified':False,
        'account_observation_atomic':False,'reservation_amounts_verified':False,'ledger_imported':False,
        'funding_authorized':False,'execution_authorized':False}


def load_observation_report(config):
    paths={name:os.environ.get(variable,'') for name,variable in (
        ('state','NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT'),('orders','NEXYDAO_TYPED_ORDERS_SNAPSHOT'),
        ('executions','NEXYDAO_EXECUTIONS_SNAPSHOT'))}
    if any(not value for value in paths.values()):raise ProbeError('three_explicit_public_observation_paths_required')
    state=load_public_state(config,StateReceiptConfig.from_env(),Path(paths['state']))
    orders=load_typed_orders(config,OrderReceiptConfig.from_env(),Path(paths['orders']))
    executions=load_executions(config,ExecutionReceiptConfig.from_env(),Path(paths['executions']))
    return cross_check_observations(state,orders,executions,config)
