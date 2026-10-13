"""Current-state allocation diagnostics. No broker reservation or funding permit."""
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal

from .funding import evaluate_funding
from .market import canonical
from .portfolio import INITIAL
from .reconciliation import number, validate_state
from .orders import validate_orders


@dataclass(frozen=True)
class AllocationConfig:
    capital_usd: str = '5000'
    fee_reserve_usd: str = '50'

    def document(self):
        capital, reserve = number(self.capital_usd), number(self.fee_reserve_usd)
        if not Decimal('0') < capital <= INITIAL or not Decimal('0') < reserve < capital:
            raise ValueError('Invalid allocation cap or fee reserve')
        return {'capital_usd': str(capital), 'fee_reserve_usd': str(reserve)}

    @classmethod
    def from_env(cls):
        value = cls(os.environ.get('NEXYDAO_ALLOCATION_USD', '5000'),
                    os.environ.get('NEXYDAO_FEE_RESERVE_USD', '50'))
        value.document()
        return value


def evaluate_allocation(payload, broker, ledger, policy, allocation, now=None, orders=None):
    """Compare a bounded allocation with explicit USD cash; never infer FX cash."""
    now = time.time() if now is None else now
    settings = allocation.document()
    diagnostic = evaluate_funding(payload, broker, ledger, policy, now)
    if orders is not None: validate_orders(orders,broker.expected_account,now)
    snapshot = ledger.snapshot(now)
    capital, reserve = map(Decimal, (settings['capital_usd'], settings['fee_reserve_usd']))
    costs = Decimal(snapshot['api_expense_estimate_or_reserved_usd'])
    cash = {r['tag']: number(r['value']) for r in payload['cash'] if r['currency'] == 'USD'}
    complete = set(cash) == {'CashBalance', 'TotalCashBalance', 'SettledCash'}
    reasons = set(diagnostic['blocking_reasons'])
    # Whole-account equality is inappropriate for a separately capped allocation.
    # This diagnostic does not remove that block from the existing funding review.
    reasons.discard('simulation_cash_not_reconciled')
    reasons.update({'broker_allocation_not_reserved', 'fee_currency_and_schedule_unverified'})
    reasons.add('manual_order_visibility_and_reservations_unverified')
    if orders is None: reasons.add('api_open_order_observation_missing')
    elif orders['activity_frame_digests']: reasons.add('api_order_activity_requires_reconciliation')
    if not complete:
        reasons.add('explicit_usd_cash_fields_incomplete')
    if snapshot['positions'] or Decimal(snapshot['unsettled_cash_usd']) != 0:
        reasons.add('existing_simulation_allocation_accounting_pending')
    usd_capacity = None
    covered = False
    simulation_cash = Decimal(snapshot['settled_cash_usd'])
    if complete:
        usd_capacity = max(Decimal(0), min(cash.values()))
        covered = usd_capacity >= capital
        if not covered: reasons.add('usd_cash_below_allocation')
    if costs + reserve >= capital: reasons.add('costs_and_reserve_exhaust_allocation')
    # Report an allocation-side planning ceiling only, never a spendable broker balance.
    ceiling = max(Decimal(0), min(capital, simulation_cash) - costs - reserve)
    if (not covered or diagnostic['negative_cash_currencies']
            or diagnostic['cash_fields_differ_currencies']
            or not diagnostic['comparison']['positions_match_simulation']
            or policy.document()['additional_rules']
            or orders is None or orders['activity_frame_digests']
            or snapshot['positions'] or Decimal(snapshot['unsettled_cash_usd']) != 0):
        ceiling = Decimal(0)
    return {'status': 'allocation_diagnostic_only', 'funding_authorized': False,
            'execution_authorized': False, 'broker_allocation_reserved': False,
            'broker_balances_imported': False, 'allocation': settings,
            'allocation_config_sha256': hashlib.sha256(canonical(settings)).hexdigest(),
            'receipt_payload_sha256': diagnostic['receipt_payload_sha256'],
            'owner_policy_sha256': policy.digest, 'ledger_revision': snapshot['revision'],
            'observed_at': payload['received_at'], 'evidence_expires_at': payload['expires_at'],
            'evaluated_at': now, 'explicit_usd_cash_complete': complete,
            'usd_cash_covers_allocation': covered,
            'api_expense_estimate_or_reserved_usd': str(costs),
            'planning_ceiling_after_reserves_usd': str(ceiling),
            'planning_ceiling_is_execution_permission': False,
            'negative_cash_currencies': diagnostic['negative_cash_currencies'],
            'blocking_reasons': sorted(reasons), 'historical_transaction_review_required': False,
            'api_order_query_complete': orders is not None,
            'api_order_activity_observed': bool(orders['activity_frame_digests']) if orders is not None else None,
            'orders_payload_sha256': hashlib.sha256(canonical(orders)).hexdigest() if orders is not None else None,
            'orders_evidence_expires_at': orders['expires_at'] if orders is not None else None,
            'manual_order_coverage_verified':False, 'reservation_amounts_verified':False,
            'account_observation_atomic':False}


def record_allocation_review(payload, broker, ledger, policy, allocation, orders=None):
    db = ledger.db
    db.execute('CREATE TABLE IF NOT EXISTS allocation_reviews '
               '(id TEXT PRIMARY KEY, created REAL NOT NULL, report TEXT NOT NULL)')
    db.commit()
    db.execute('BEGIN IMMEDIATE')
    try:
        result = evaluate_allocation(payload, broker, ledger, policy, allocation, orders=orders)
        validate_state(payload, broker.expected_account)
        if orders is not None: validate_orders(orders,broker.expected_account)
        policy.assert_current()
        ledger.assert_revision(result['ledger_revision'])
        identifier = str(uuid.uuid4())
        result['review_id'] = identifier
        db.execute('INSERT INTO allocation_reviews VALUES(?,?,?)',
                   (identifier, time.time(), json.dumps(result, allow_nan=False)))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
