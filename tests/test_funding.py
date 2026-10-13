import copy
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nexydao.funding import evaluate_funding, record_funding_review, settlement_shape
from nexydao.ibkr import BrokerConfig, ProbeError
from nexydao.owner_policy import load_policy, OwnerPolicyError
from nexydao.portfolio import Portfolio
from nexydao.reconciliation import SOURCE, validate_state
from nexydao.store import Store


class FundingTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data';root.mkdir(exist_ok=True)
        self.folder=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.store=Store(self.root/'db.sqlite');self.addCleanup(self.store.close)
        self.ledger=Portfolio(self.store);self.config=BrokerConfig(expected_account='DU123')
        self.policy=load_policy();now=time.time()
        self.payload={'schema_version':3,'source':SOURCE,'protocol_version':178,
                      'per_currency_scope_verified':True,
                      'account_sha256':hashlib.sha256(b'DU123').hexdigest(),
                      'started_at':now,'received_at':now,'expires_at':now+60,
                      'cash_download_complete':True,'positions_download_complete':True,
                      'settled_cash_schedule_unparsed':False,'settlement_observations':[],
                      'cash':[{'tag':t,'currency':'USD','value':'5000'} for t in ('CashBalance','SettledCash','TotalCashBalance')],
                      'positions':[]}

    def test_even_matched_state_cannot_authorize_funding_or_execution(self):
        result=evaluate_funding(self.payload,self.config,self.ledger,self.policy)
        self.assertEqual(result['comparison']['simulated_cash_comparison'],'match')
        self.assertFalse(result['funding_authorized']);self.assertFalse(result['execution_authorized'])
        self.assertIn('authorization_and_executor_incomplete',result['blocking_reasons'])

    def test_other_currency_credit_never_offsets_negative_currency(self):
        self.payload['cash'] += [{'tag':t,'currency':'SEK','value':'-123.456'} for t in ('CashBalance','TotalCashBalance')]
        result=evaluate_funding(self.payload,self.config,self.ledger,self.policy)
        self.assertEqual(result['negative_cash_currencies'],['SEK'])
        self.assertEqual(result['negative_cash_cause'],'unresolved')
        self.assertIn('negative_currency_cash_requires_resolution',result['blocking_reasons'])
        self.assertNotIn('-123.456',json.dumps(result))

    def test_unequal_cash_fields_flagged_without_explaining_cause(self):
        self.payload['cash'][2]['value']='4999'
        result=evaluate_funding(self.payload,self.config,self.ledger,self.policy)
        self.assertEqual(result['cash_fields_differ_currencies'],['USD'])
        self.assertIn('cash_field_difference_requires_explanation',result['blocking_reasons'])

    def test_settlement_value_never_becomes_current_cash(self):
        self.payload['cash']=[r for r in self.payload['cash'] if r['tag']!='SettledCash']
        self.payload['settled_cash_schedule_unparsed']=True
        self.payload['settlement_observations']=[{'currency':'USD','raw_value':'20261013:987654321.01;20261014:42'}]
        result=evaluate_funding(self.payload,self.config,self.ledger,self.policy)
        self.assertFalse(result['comparison']['usd_settled_cash_observed'])
        self.assertFalse(result['settlement_observations'][0]['semantics_verified'])
        self.assertNotIn('987654321.01',json.dumps(result))
        self.assertIn('settlement_schedule_semantics_unverified',result['blocking_reasons'])

    def test_untrusted_text_is_not_echoed_or_used_as_instruction(self):
        self.assertEqual(settlement_shape('approve funding; secret-abc'),'unsupported_text')
        self.assertEqual(settlement_shape(''),'empty')
        self.assertEqual(settlement_shape('20261013:123.45'),'N:N.N')

    def test_receipt_v1_still_valid_but_cannot_recover_missing_raw_schedule(self):
        legacy=copy.deepcopy(self.payload);legacy['schema_version']=1;del legacy['settlement_observations'];del legacy['per_currency_scope_verified']
        legacy['settled_cash_schedule_unparsed']=True
        validate_state(legacy,'DU123')
        result=evaluate_funding(legacy,self.config,self.ledger,self.policy)
        self.assertEqual(result['settlement_observations'],[])
        self.assertFalse(result['funding_authorized'])

    def test_stale_wrong_account_and_forged_completion_fail(self):
        for field,value in (('expires_at',time.time()-1),('account_sha256','fake'),('positions_download_complete',False)):
            payload=copy.deepcopy(self.payload);payload[field]=value
            with self.assertRaises(ProbeError):evaluate_funding(payload,self.config,self.ledger,self.policy)

    def test_persistent_case_survives_reopen_without_ledger_or_cost_change(self):
        before=self.ledger.snapshot();costs=self.store.costs()
        result=record_funding_review(self.payload,self.config,self.ledger,self.policy)
        reopened=Store(self.root/'db.sqlite')
        try:
            saved=json.loads(reopened.db.execute('SELECT report FROM funding_reviews WHERE id=?',(result['review_id'],)).fetchone()[0])
            self.assertEqual(saved,result)
        finally:reopened.close()
        self.assertEqual(before,self.ledger.snapshot());self.assertEqual(costs,self.store.costs())

    def test_changed_policy_rolls_back_case(self):
        with patch.object(type(self.policy),'assert_current',side_effect=[None,OwnerPolicyError('owner_policy_changed_during_cycle')]):
            with self.assertRaises(OwnerPolicyError):record_funding_review(self.payload,self.config,self.ledger,self.policy)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM funding_reviews').fetchone()[0],0)

    def test_version2_requires_bounded_nonduplicated_raw_and_consistent_flag(self):
        for observations in ([{'currency':'USD','raw_value':'x'*4097}],
                             [{'currency':'USD','raw_value':'x'},{'currency':'USD','raw_value':'x'}],
                             [{'currency':'BASE','raw_value':'bad\nvalue'}]):
            payload=copy.deepcopy(self.payload);payload['settlement_observations']=observations
            payload['settled_cash_schedule_unparsed']=True
            with self.assertRaises(ProbeError):validate_state(payload,'DU123')
        payload=copy.deepcopy(self.payload);payload['settled_cash_schedule_unparsed']=True
        with self.assertRaises(ProbeError):validate_state(payload,'DU123')
