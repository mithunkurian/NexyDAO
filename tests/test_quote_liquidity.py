import copy
import hashlib
import hmac
import io
import json
import time
import unittest
from unittest.mock import patch

import test_market as fixtures
import test_portfolio as portfolio_fixtures
from nexydao.cli import DemoProvider,main
from nexydao.ibkr import ProbeError
from nexydao.market import canonical,load_market_evidence
from nexydao.portfolio import PortfolioError
from nexydao.quote_liquidity import QuoteLiquidity
from nexydao.safety import evaluate
from nexydao.store import Store
from nexydao.workflow import run_cycle


class QuoteLiquidityTests(unittest.TestCase):
    setUp=fixtures.MarketTests.setUp
    payload=fixtures.MarketTests.payload
    contract=fixtures.MarketTests.contract
    session=fixtures.MarketTests.session
    receipt=fixtures.MarketTests.receipt

    def evidence(self,bid='100',ask='101',conid=123):
        payload=self.payload();payload['quote'].update(bid=bid,ask=ask)
        payload['contract']['con_id']=conid
        self.receipt(payload)
        return load_market_evidence(self.config.snapshot,self.config,self.now)

    def allocation(self,evidence):
        return {'symbol':'SPY','allocation_usd':100,'evidence_ids':[evidence[0]['id']]}

    def test_exact_boundary_and_one_tick_wider_are_checked_without_float_rounding(self):
        for ask,passes in (('101',True),('101.000000000001',False)):
            evidence=self.evidence(ask=ask);book=QuoteLiquidity(evidence,self.now)
            self.assertEqual(not book.reasons([self.allocation(evidence)]),passes)
            self.assertEqual(book.report()['quotes'][0]['spread_within_limit'],passes)

    def test_locked_quote_and_unknown_size_units_never_claim_executable_capacity(self):
        report=QuoteLiquidity(self.evidence(ask='100'),self.now).report()
        self.assertEqual(report['quotes'][0]['spread_fraction'],'0E-8')
        for key in ('size_units_verified','executable_depth_verified','portfolio_exit_capacity_verified',
                    'market_liquidity_verified','execution_authorized'):
            self.assertFalse(report[key])

    def test_missing_manual_or_unrelated_quote_reference_does_not_support_new_risk(self):
        evidence=self.evidence();book=QuoteLiquidity(evidence,self.now)
        with self.assertRaises(AttributeError):book.payload=b'{}'
        for allocations in ([{'symbol':'OTHER','evidence_ids':[evidence[0]['id']]}],
                            [{'symbol':'SPY','evidence_ids':['manual']}], [{'symbol':'SPY','evidence_ids':[]}]):
            self.assertIn('fresh_quote_liquidity_evidence_required',book.reasons(allocations))
        self.assertEqual(book.reasons([]),[])
        self.assertTrue(QuoteLiquidity([{'verification':'unverified','summary':'no trust'}]).reasons([self.allocation(evidence)]))

    def test_all_matching_quotes_apply_and_contract_ambiguity_cannot_be_cherry_picked(self):
        tight=self.evidence();wide=self.evidence(ask='102')
        book=QuoteLiquidity(tight+wide,self.now)
        self.assertIn('quote_spread_limit_exceeded',book.reasons([self.allocation(tight)]))
        other_contract=self.evidence(conid=124)
        self.assertIn('liquidity_quote_contract_ambiguous',QuoteLiquidity(tight+other_contract,self.now).reasons([self.allocation(tight)]))

    def test_position_contract_must_match_independently_checked_quote(self):
        evidence=self.evidence();book=QuoteLiquidity(evidence,self.now)
        snapshot={'positions':[{'symbol':'SPY','contract_id':124}]}
        self.assertIn('liquidity_position_contract_mismatch',book.reasons([self.allocation(evidence)],snapshot))

    def test_snapshot_detects_mutations_removal_added_trust_or_swapped_expiry(self):
        evidence=self.evidence();book=QuoteLiquidity(evidence,self.now)
        for mutation in ('price','remove','expiry','label','observed_at'):
            changed=copy.deepcopy(evidence)
            if mutation=='price':
                summary=json.loads(changed[0]['summary']);summary['quote']['ask']='100.5';changed[0]['summary']=json.dumps(summary)
            elif mutation=='remove':changed=[]
            elif mutation=='expiry':changed[0]['expires_at']+=1
            elif mutation=='label':changed[0]['verification']='unverified'
            else:changed[0]['observed_at']='unverified-time'
            with self.subTest(mutation=mutation),self.assertRaises(ProbeError):book.assert_current(changed)
        with self.assertRaises(ProbeError):QuoteLiquidity(evidence+evidence,self.now)

    def test_freshness_checked_again_after_snapshot_creation(self):
        evidence=self.evidence();book=QuoteLiquidity(evidence,self.now)
        with patch('nexydao.quote_liquidity.time.time',return_value=self.now+60):
            with self.assertRaises(ProbeError):book.reasons([self.allocation(evidence)])

    def test_market_and_sanitized_summary_duplicate_fields_fail(self):
        evidence=self.evidence()
        raw=self.config.snapshot.read_text().replace('"schema_version": 1','"schema_version": 1,"schema_version": 1')
        self.config.snapshot.write_text(raw)
        with self.assertRaises(ProbeError):load_market_evidence(self.config.snapshot,self.config,self.now)
        changed=copy.deepcopy(evidence)
        changed[0]['summary']=changed[0]['summary'].replace('"received_at":','"received_at": 1,"received_at":',1)
        with self.assertRaises(ProbeError):QuoteLiquidity(changed,self.now)

    def test_final_ceo_proposal_gets_spread_block_even_with_positive_reviews(self):
        from nexydao.owner_policy import load_policy
        evidence=self.evidence(ask='102')
        proposal={'action':'propose_investment','symbol':'SPY','allocation_usd':100,'evidence_ids':[evidence[0]['id']]}
        result=evaluate(proposal,[{'verdict':'pass'}]*2,[{'vote':'approve'}]*3,load_policy(),
                        quote_liquidity=QuoteLiquidity(evidence,self.now))
        self.assertIn('quote_spread_limit_exceeded',result['reasons']);self.assertFalse(result['execution_authorized'])

    def test_quote_report_cli_authenticates_without_provider_socket_or_database(self):
        self.evidence();output=io.StringIO()
        with patch('sys.argv',['nexydao','quote-liquidity-report','--market-evidence',str(self.config.snapshot)]), \
                patch('nexydao.market.MarketConfig.from_env',return_value=self.config), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('socket.create_connection') as connect,patch('sys.stdout',output):main()
        for operation in (store,provider,connect):operation.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['market_liquidity_verified'])


class LiquidityWorkflowTests(unittest.TestCase):
    setUp=portfolio_fixtures.PortfolioTests.setUp

    def evidence(self,ask='102'):
        from nexydao.market import SOURCE
        now=int(time.time())
        payload={'schema_version':1,'source':SOURCE,'protocol_version':178,
            'account_sha256':hashlib.sha256(b'DU123').hexdigest(),
            'contract':{'con_id':123,'symbol':'TEST','security_type':'STK','currency':'USD',
                        'exchange':'SMART','primary_exchange':'ARCA'},
            'quote':{'bid':'100','ask':ask,'bid_size':'10','ask_size':'10','event_time':now,'flags':0},
            'received_at':now,'expires_at':now+60,'raw_sha256':'a'*64}
        raw={'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}
        self.market.snapshot.write_text(json.dumps(raw))
        return load_market_evidence(self.market.snapshot,self.market)

    def manager(self,evidence,mutate=False):
        class Provider(DemoProvider):
            def decide(self,run,role,instructions,context,schema):
                if role=='portfolio_manager':
                    if mutate:
                        view=json.loads(evidence[0]['summary']);view['quote']['ask']='100.5';evidence[0]['summary']=json.dumps(view)
                    return {'allocations':[{'symbol':'TEST','allocation_usd':100,'rationale':'Synthetic fixture',
                        'evidence_ids':[evidence[0]['id']]}],'cash_target_usd':4900,'alternatives':'Hold',
                        'portfolio_risks':'Liquidity unknown','abstain_reason':''}
                return super().decide(run,role,instructions,context,schema)
        return Provider()

    def test_manager_wide_spread_aborts_before_ceo_without_mutating_ledger(self):
        evidence=self.evidence();provider=self.manager(evidence);before=self.ledger.snapshot()
        with patch.object(provider,'decide',wraps=provider.decide) as decide:
            with self.assertRaisesRegex(PortfolioError,'quote_spread_limit'):run_cycle(self.store,provider,evidence,portfolio=True)
        self.assertEqual(decide.call_count,1);self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(self.store.costs()['calls'],0)

    def test_manager_cannot_relax_quote_evidence_in_place(self):
        evidence=self.evidence();provider=self.manager(evidence,mutate=True)
        with self.assertRaisesRegex(ProbeError,'quote_changed'):run_cycle(self.store,provider,evidence,portfolio=True)
        self.assertEqual(self.ledger.revision(),0)

    def test_narrow_spread_cycle_records_partial_scope_without_authority(self):
        evidence=self.evidence(ask='101');result=run_cycle(self.store,self.manager(evidence),evidence,portfolio=True)
        self.assertTrue(result['quote_liquidity']['quotes'][0]['spread_within_limit'])
        self.assertFalse(result['quote_liquidity']['market_liquidity_verified'])
        self.assertFalse(result['policy']['execution_authorized']);self.assertEqual(self.ledger.revision(),0)

    def test_all_risk_and_committee_calls_cannot_override_ceo_spread_gate(self):
        evidence=self.evidence()
        class Provider(DemoProvider):
            def decide(self,run,role,instructions,context,schema):
                if role=='ceo':return {'action':'propose_investment','symbol':'TEST','allocation_usd':100,
                    'rationale':'Synthetic fixture','risks':'Liquidity','evidence_ids':[evidence[0]['id']],
                    'invalidation_conditions':'Spread widens'}
                if role.startswith('risk_'):return {'verdict':'pass','rationale':'Fixture','evidence_ids':[]}
                return {'vote':'approve','rationale':'Fixture','evidence_ids':[]}
        result=run_cycle(self.store,Provider(),evidence)
        self.assertIn('quote_spread_limit_exceeded',result['policy']['reasons'])
        self.assertFalse(result['policy']['execution_authorized']);self.assertEqual(self.ledger.revision(),0)

    def test_expiry_after_last_vote_prevents_completed_policy_record(self):
        evidence=self.evidence(ask='101');expiry=json.loads(evidence[0]['summary'])['expires_at']
        clock=[expiry-60];calls=[]
        class Provider(DemoProvider):
            def decide(self,run,role,*args):
                calls.append(role);result=super().decide(run,role,*args)
                if role=='committee_audit':clock[0]=expiry
                return result
        with patch('nexydao.quote_liquidity.time.time',side_effect=lambda:clock[0]):
            with self.assertRaises(ProbeError):run_cycle(self.store,Provider(),evidence)
        self.assertEqual(len(calls),6);self.assertEqual(self.ledger.revision(),0)
