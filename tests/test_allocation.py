import copy
import json
import os
import time
import unittest
from unittest.mock import patch

from nexydao.allocation import AllocationConfig, evaluate_allocation, record_allocation_review
from nexydao.ibkr import ProbeError
from nexydao.owner_policy import OwnerPolicyError
from nexydao.store import Store
import test_funding as funding_fixtures


class AllocationTests(unittest.TestCase):
    setUp = funding_fixtures.FundingTests.setUp

    def evaluate(self, payload=None, settings=None):
        return evaluate_allocation(payload or self.payload, self.config, self.ledger,
                                   self.policy, settings or AllocationConfig())

    def test_larger_broker_balance_does_not_enlarge_allocation_or_authorize(self):
        for row in self.payload['cash']: row['value'] = '1000000'
        result = self.evaluate()
        self.assertTrue(result['usd_cash_covers_allocation'])
        self.assertEqual(result['planning_ceiling_after_reserves_usd'], '4950')
        self.assertFalse(result['funding_authorized'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['broker_allocation_reserved'])
        self.assertNotIn('1000000', json.dumps(result))

    def test_missing_settlement_cannot_use_cash_or_schedule(self):
        self.payload['cash'] = [r for r in self.payload['cash'] if r['tag'] != 'SettledCash']
        self.payload['settled_cash_schedule_unparsed'] = True
        self.payload['settlement_observations'] = [{'currency':'USD','raw_value':'0:999999'}]
        result = self.evaluate()
        self.assertFalse(result['usd_cash_covers_allocation'])
        self.assertEqual(result['planning_ceiling_after_reserves_usd'], '0')

    def test_foreign_credit_or_base_aggregate_does_not_supply_usd(self):
        self.payload['cash'] = [{'tag':r['tag'],'currency':'EUR','value':'999999'} for r in self.payload['cash']]
        self.assertFalse(self.evaluate()['usd_cash_covers_allocation'])

    def test_foreign_debit_blocks_despite_large_usd_credit_and_owner_history(self):
        self.payload['cash'].append({'tag':'CashBalance','currency':'SEK','value':'-1'})
        result = self.evaluate()
        self.assertEqual(result['planning_ceiling_after_reserves_usd'], '0')
        self.assertIn('negative_currency_cash_requires_resolution', result['blocking_reasons'])
        self.assertFalse(result['historical_transaction_review_required'])

    def test_lowest_explicit_cash_field_limits_coverage(self):
        self.payload['cash'][0]['value'] = '4999'
        result = self.evaluate()
        self.assertFalse(result['usd_cash_covers_allocation'])
        self.assertIn('usd_cash_below_allocation', result['blocking_reasons'])

    def test_api_costs_and_reserves_are_inside_allocation(self):
        with patch.object(self.store, 'costs', return_value={'estimated_or_reserved_usd':'12.50'}):
            self.assertEqual(self.evaluate()['planning_ceiling_after_reserves_usd'], '4937.50')
        with patch.object(self.store, 'costs', return_value={'estimated_or_reserved_usd':'5000'}):
            result = self.evaluate()
            self.assertEqual(result['planning_ceiling_after_reserves_usd'], '0')
            self.assertIn('costs_and_reserve_exhaust_allocation', result['blocking_reasons'])

    def test_invalid_cap_reserve_and_environment_fail(self):
        for cap, reserve in [('5001','50'),('0','50'),('NaN','50'),('5000','0'),('5000','5000'),('5000','-1')]:
            with self.assertRaises((ValueError, ProbeError)):
                self.evaluate(settings=AllocationConfig(cap,reserve))
        with patch.dict(os.environ, {'NEXYDAO_ALLOCATION_USD':'1000000'}):
            with self.assertRaises(ValueError): AllocationConfig.from_env()

    def test_reduced_allocation_remains_capped_and_denied(self):
        result = self.evaluate(settings=AllocationConfig('1000','20'))
        self.assertEqual(result['planning_ceiling_after_reserves_usd'], '980')
        self.assertFalse(result['execution_authorized'])

    def test_stale_wrong_pin_and_forged_completion_rejected(self):
        for field, value in [('expires_at',time.time()-1),('account_sha256','fake'),('cash_download_complete',False)]:
            payload = copy.deepcopy(self.payload); payload[field] = value
            with self.assertRaises(ProbeError): self.evaluate(payload)

    def test_persisted_review_does_not_change_ledger_costs_or_agent_memory(self):
        before, costs, memory = self.ledger.snapshot(), self.store.costs(), self.store.memory()
        result = record_allocation_review(self.payload,self.config,self.ledger,self.policy,AllocationConfig())
        reopened = Store(self.root/'db.sqlite')
        try:
            saved = json.loads(reopened.db.execute('SELECT report FROM allocation_reviews WHERE id=?', (result['review_id'],)).fetchone()[0])
            self.assertEqual(result,saved)
        finally: reopened.close()
        self.assertEqual(before,self.ledger.snapshot())
        self.assertEqual(costs,self.store.costs())
        self.assertEqual(memory,self.store.memory())

    def test_policy_change_and_expiry_before_commit_roll_back(self):
        with patch.object(type(self.policy),'assert_current',side_effect=[None,OwnerPolicyError('changed')]):
            with self.assertRaises(OwnerPolicyError):
                record_allocation_review(self.payload,self.config,self.ledger,self.policy,AllocationConfig())
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM allocation_reviews').fetchone()[0],0)
        with patch('nexydao.allocation.validate_state',side_effect=ProbeError('expired')):
            with self.assertRaises(ProbeError):
                record_allocation_review(self.payload,self.config,self.ledger,self.policy,AllocationConfig())
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM allocation_reviews').fetchone()[0],0)
