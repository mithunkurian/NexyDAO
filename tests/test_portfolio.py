import copy
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from nexydao.cli import DemoProvider
from nexydao.ibkr import BrokerConfig
from nexydao.market import MarketConfig, SOURCE, canonical, load_market_evidence
from nexydao.owner_policy import load_policy, OwnerPolicyError
from nexydao.portfolio import Portfolio, PortfolioError, allocation_reasons
from nexydao.portfolio_manager import PLAN
from nexydao.store import Store
from nexydao.workflow import run_cycle


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data'
        root.mkdir(exist_ok=True)
        self.folder=tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.path=self.root/'ledger.sqlite3'
        self.store=Store(self.path)
        self.addCleanup(self.store.close)
        self.ledger=Portfolio(self.store)
        self.policy=load_policy()
        self.key=self.root/'key'
        self.key.write_bytes(b'x'*32)
        self.key.chmod(0o600)
        self.market=MarketConfig(BrokerConfig(expected_account='DU123'),self.key,'TEST',self.root/'quote.json')

    def fill(self, identifier='buy1', **changes):
        data={'id':identifier,'side':'buy','symbol':'TEST','quantity':'2','price':'100','fee':'1','currency':'USD','asset_type':'STK'}
        data.update(changes)
        return data

    def mark(self, bid='100', event=None, conid=123, symbol='TEST'):
        now=int(time.time()) if event is None else event
        payload={'schema_version':1,'source':SOURCE,'protocol_version':178,
            'account_sha256':hashlib.sha256(b'DU123').hexdigest(),
            'contract':{'con_id':conid,'symbol':symbol,'security_type':'STK','currency':'USD','exchange':'SMART','primary_exchange':'ARCA'},
            'quote':{'bid':bid,'ask':str(Decimal(bid)+1),'bid_size':'1','ask_size':'1','event_time':now,'flags':0},
            'received_at':now,'expires_at':now+60,'raw_sha256':'a'*64}
        self.market.snapshot.write_text(json.dumps({'payload':payload,
            'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}))
        return self.ledger.mark(self.market.snapshot,self.market)

    def test_initial_capital_is_seeded_once_across_connections(self):
        other=Store(self.path)
        self.addCleanup(other.close)
        Portfolio(other)
        snapshot=self.ledger.snapshot()
        self.assertEqual(snapshot['settled_cash_usd'],'5000')
        self.assertEqual(snapshot['net_equity_estimate_usd'],'5000')
        self.assertEqual(snapshot['positions'],[])
        self.assertTrue(snapshot['simulation_internal_reconciliation'])
        self.assertFalse(snapshot['broker_reconciliation'])

    def test_buy_partial_sales_fees_settlement_and_net_pnl_reconcile(self):
        self.ledger.fill(self.fill(),self.policy)
        self.ledger.fill(self.fill('sell1',side='sell',quantity='1',price='110'),self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['settled_cash_usd']),Decimal('4799'))
        self.assertEqual(Decimal(snapshot['unsettled_cash_usd']),Decimal('109'))
        self.assertEqual(Decimal(snapshot['positions'][0]['cost_basis_usd']),Decimal('100.5'))
        self.assertEqual(Decimal(snapshot['realized_pnl_usd']),Decimal('8.5'))
        self.ledger.fill(self.fill('sell2',side='sell',quantity='1',price='120'),self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(snapshot['positions'],[])
        self.assertEqual(Decimal(snapshot['net_equity_estimate_usd']),Decimal('5027'))
        self.assertEqual(Decimal(snapshot['simulation_fees_usd']),Decimal('3'))
        self.ledger.settle('sell1')
        self.ledger.settle('sell2')
        self.ledger.settle('sell2')
        self.assertEqual(Decimal(self.ledger.snapshot()['settled_cash_usd']),Decimal('5027'))
        self.assertEqual(self.ledger.snapshot()['unsettled_cash_usd'],'0E-8')

    def test_duplicate_fill_is_idempotent_conflict_is_rejected(self):
        fill=self.fill()
        self.ledger.fill(fill)
        revision=self.ledger.revision()
        self.assertEqual(self.ledger.fill(fill)['status'],'already_recorded')
        self.assertEqual(self.ledger.revision(),revision)
        with self.assertRaises(PortfolioError): self.ledger.fill({**fill,'price':'101'})

    def test_short_leveraged_foreign_and_invalid_fills_do_not_change_cash(self):
        for changes in ({'side':'sell'}, {'asset_type':'CFD'}, {'currency':'SEK'},
                        {'quantity':'-1'}, {'price':'NaN'}, {'fee':True}, {'quantity':'6'}):
            with self.assertRaises((PortfolioError,OwnerPolicyError)):
                self.ledger.fill(self.fill(**changes))
        self.assertEqual(self.ledger.snapshot()['settled_cash_usd'],'5000')
        self.assertEqual(self.ledger.revision(),0)

    def test_marks_require_signed_fresh_receipt_and_matching_contract(self):
        self.ledger.fill(self.fill())
        self.assertFalse(self.ledger.snapshot()['valuation_complete'])
        self.assertIsNone(self.ledger.snapshot()['net_equity_estimate_usd'])
        self.mark('110')
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['positions'][0]['market_value_usd']),Decimal('220'))
        self.assertEqual(Decimal(snapshot['net_equity_estimate_usd']),Decimal('5019'))
        expiry=snapshot['positions'][0]['mark_expires_at']
        self.assertFalse(self.ledger.snapshot(now=expiry)['valuation_complete'])
        with self.assertRaises(PortfolioError): self.mark('110',conid=999)

    def test_expired_mark_prevents_buy_but_owned_sale_can_reduce_risk(self):
        self.ledger.fill(self.fill())
        with self.assertRaisesRegex(PortfolioError,'fresh_portfolio_valuation_required'):
            self.ledger.fill(self.fill('new',symbol='OTHER',quantity='1',price='50'))
        self.ledger.fill(self.fill('reduce',side='sell',quantity='1',price='80'))
        self.assertEqual(self.ledger.snapshot()['positions'][0]['quantity'],'1')

    def test_aggregate_limits_include_existing_position_and_api_expenses(self):
        self.ledger.fill(self.fill())
        self.mark()
        with self.assertRaisesRegex(PortfolioError,'aggregate_position_limit_exceeded'):
            self.ledger.fill(self.fill('more',quantity='3',price='100'))
        ticket=self.store.reserve('test','role','test',Decimal('10'),Decimal('20'))
        snapshot=self.ledger.snapshot()
        self.assertEqual(snapshot['api_expense_estimate_or_reserved_usd'],'10')
        self.assertEqual(Decimal(snapshot['net_equity_estimate_usd']),Decimal('4989'))
        reasons=allocation_reasons(snapshot,[{'symbol':'OTHER','allocation_usd':'800'}],self.policy)
        self.assertIn('aggregate_cash_reserve_breached',reasons)
        self.assertIn('aggregate_exposure_limit_exceeded',reasons)

    def test_drawdown_blocks_new_risk_without_generating_a_sell(self):
        self.ledger.fill(self.fill())
        self.mark('500')
        self.mark('20')
        snapshot=self.ledger.snapshot()
        self.assertGreater(Decimal(snapshot['drawdown_fraction']),Decimal('.1'))
        self.assertIn('drawdown_limit_exceeded',allocation_reasons(snapshot,[{'symbol':'OTHER','allocation_usd':'10'}],self.policy))
        self.assertEqual(len(snapshot['positions']),1)

    def test_sell_proceeds_are_not_available_until_explicit_settlement(self):
        self.ledger.fill(self.fill(quantity='5',price='100',fee='0'))
        self.ledger.fill(self.fill('sell',side='sell',quantity='5',price='100',fee='0'))
        self.assertEqual(self.ledger.snapshot()['available_cash_after_api_estimate_usd'],'4500.00000000')
        self.ledger.settle('sell')
        self.assertEqual(Decimal(self.ledger.snapshot()['settled_cash_usd']),Decimal('5000'))

    def test_reconciliation_detects_changed_cash_and_position_state(self):
        with self.store.db:
            self.store.db.execute("UPDATE portfolio_state SET cash='6000'")
        with self.assertRaisesRegex(PortfolioError,'reconciliation_failed'): self.ledger.snapshot()

    def test_state_revision_prevents_model_cycle_using_changed_portfolio(self):
        outer=self
        class Change(DemoProvider):
            def decide(self,*args):
                outer.ledger.fill(outer.fill())
                return super().decide(*args)
        with self.assertRaisesRegex(PortfolioError,'portfolio_changed_during_cycle'):
            run_cycle(self.store,Change(),[])

    def test_concurrent_connections_cannot_exceed_aggregate_position_limit(self):
        self.ledger.fill(self.fill(quantity='3',fee='0'))
        self.mark('100')
        def attempt(identifier):
            store=Store(self.path)
            ledger=Portfolio(store)
            try:
                ledger.fill(self.fill(identifier,quantity='1.5',fee='0'))
                return True
            except PortfolioError:
                return False
            finally: store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,['concurrent1','concurrent2']))
        self.assertEqual(sum(results),1)
        self.assertEqual(Decimal(self.ledger.snapshot()['positions'][0]['cost_basis_usd']),Decimal('450'))

    def test_seven_call_manager_cycle_is_advisory_and_does_not_fill(self):
        calls=[]
        class Manager(DemoProvider):
            mode='ai'
            def decide(self,run,role,instructions,context,schema):
                calls.append(role)
                if 'allocations' in schema['properties']:
                    return {'allocations':[],'cash_target_usd':5000,'alternatives':'Wait for evidence',
                            'portfolio_risks':'No verified quote','abstain_reason':'Insufficient evidence'}
                return super().decide(run,role,instructions,context,schema)
        result=run_cycle(self.store,Manager(),[],portfolio=True)
        self.assertEqual(calls[0],'portfolio_manager')
        self.assertEqual(len(calls),7)
        self.assertFalse(result['policy']['execution_authorized'])
        self.assertEqual(self.ledger.revision(),0)
        self.assertEqual(self.ledger.snapshot()['positions'],[])
        self.assertEqual(result['portfolio_plan']['allocations'],[])

    def test_quote_supported_manager_plan_does_not_mutate_positions(self):
        self.ledger.fill(self.fill())
        self.mark()
        evidence=load_market_evidence(self.market.snapshot,self.market)
        revision=self.ledger.revision()
        class Manager(DemoProvider):
            def decide(self,run,role,instructions,context,schema):
                if 'allocations' in schema['properties']:
                    return {'allocations':[{'symbol':'TEST','allocation_usd':100,'rationale':'Fixture reasoning',
                            'evidence_ids':[evidence[0]['id']]}],'cash_target_usd':4699,
                            'alternatives':'Remain in cash','portfolio_risks':'Missing thesis','abstain_reason':''}
                return super().decide(run,role,instructions,context,schema)
        result=run_cycle(self.store,Manager(),evidence,portfolio=True)
        self.assertFalse(result['policy']['execution_authorized'])
        self.assertEqual(self.ledger.revision(),revision)
        self.assertEqual(self.ledger.snapshot()['positions'][0]['quantity'],'2')

    def test_manager_cannot_use_unrelated_manual_citation_for_quote_allocation(self):
        self.ledger.fill(self.fill())
        self.mark()
        evidence=load_market_evidence(self.market.snapshot,self.market)
        evidence.append({'id':'manual','verification':'unverified'})
        class Manager(DemoProvider):
            def decide(self,run,role,instructions,context,schema):
                return {'allocations':[{'symbol':'TEST','allocation_usd':100,'rationale':'Fixture',
                        'evidence_ids':['manual']}],'cash_target_usd':4699,'alternatives':'Cash',
                        'portfolio_risks':'Unsupported','abstain_reason':''}
        with self.assertRaisesRegex(PortfolioError,'quote_supported_allocation'):
            run_cycle(self.store,Manager(),evidence,portfolio=True)

    def test_attribution_reconciles_partial_sale_fees_and_api_cost_settlement(self):
        self.ledger.fill(self.fill())
        self.ledger.fill(self.fill('sell', side='sell', quantity='1', price='110'))
        self.mark('120')
        ticket = self.store.reserve('fixture', 'risk', 'test', Decimal('10'), Decimal('20'))
        before = self.ledger.snapshot()['performance_attribution']
        self.assertEqual(Decimal(before['net_pnl_after_recorded_costs_usd']), Decimal('18'))
        self.store.settle(ticket, Decimal('0.5'), {'input_tokens': 1, 'output_tokens': 1}, 'fixture')
        report = self.ledger.snapshot()['performance_attribution']
        self.assertEqual(Decimal(report['price_pnl_before_recorded_fees_usd']), Decimal('30'))
        self.assertEqual(Decimal(report['recorded_trading_fees_usd']), Decimal('2'))
        self.assertEqual(Decimal(report['net_pnl_after_recorded_costs_usd']), Decimal('27.5'))
        self.assertTrue(report['equity_change_reconciled'])
        self.ledger.settle('sell')
        self.assertEqual(self.ledger.snapshot()['performance_attribution'], report)

    def test_portfolio_stress_combines_positions_and_deducts_api_costs_once(self):
        self.ledger.fill(self.fill())
        self.mark('110')
        self.ledger.fill(self.fill('other', symbol='OTHER', quantity='1', price='200', fee='2'))
        self.market = replace(self.market, symbol='OTHER')
        self.mark('180', symbol='OTHER', conid=456)
        self.store.reserve('fixture', 'risk', 'test', Decimal('10'), Decimal('20'))
        before = self.store.db.total_changes
        report = self.ledger.snapshot()
        scenario = report['portfolio_stress']['scenarios'][1]
        self.assertEqual(Decimal(report['portfolio_stress']['holdings_market_value_usd']), Decimal('400'))
        self.assertEqual(Decimal(scenario['loss_usd']), Decimal('120'))
        self.assertEqual(Decimal(scenario['net_equity_estimate_usd']), Decimal('4867'))
        self.assertEqual(self.store.db.total_changes, before)
        self.assertFalse(report['portfolio_stress']['execution_authorized'])

    def test_stress_includes_holds_without_spending_or_double_deducting_them(self):
        from nexydao.reservations import Reservations
        from nexydao.allocation import AllocationConfig
        book = Reservations(self.ledger)
        book.reserve({'id': 'risk-hold', 'proposal_sha256': 'a'*64, 'symbol': 'TEST',
                      'notional_usd': '100', 'fee_usd': '2', 'fee_currency': 'USD'},
                     self.policy, AllocationConfig())
        revision = self.ledger.revision()
        report = self.ledger.snapshot()
        stress = report['portfolio_stress']
        self.assertEqual(Decimal(report['net_equity_estimate_usd']), Decimal('5000'))
        self.assertEqual(Decimal(stress['planning_holds_at_risk_usd']), Decimal('102'))
        self.assertEqual(Decimal(stress['deployment_fee_assumption_usd']), Decimal('2'))
        self.assertEqual(Decimal(stress['scenarios'][2]['net_equity_estimate_usd']), Decimal('4948'))
        self.assertEqual(self.ledger.revision(), revision)
        book.release('risk-hold', self.policy)
        after = self.ledger.snapshot()['portfolio_stress']
        self.assertTrue(all(Decimal(s['loss_usd']) == 0 for s in after['scenarios']))
        self.assertTrue(self.ledger.snapshot()['performance_attribution']['equity_change_reconciled'])

    def test_expired_marks_make_performance_and_stress_unknown(self):
        self.ledger.fill(self.fill())
        self.mark('110')
        snapshot = self.ledger.snapshot()
        expired = self.ledger.snapshot(now=snapshot['positions'][0]['mark_expires_at'])
        self.assertEqual(expired['portfolio_stress']['status'], 'fresh_marks_required')
        for scenario in expired['portfolio_stress']['scenarios']:
            self.assertIsNone(scenario['loss_usd'])
            self.assertIsNone(scenario['drawdown_limit_reached'])
        performance = expired['performance_attribution']
        self.assertIsNone(performance['net_pnl_after_recorded_costs_usd'])
        self.assertIsNone(performance['price_pnl_before_recorded_fees_usd'])
        self.assertFalse(performance['equity_change_reconciled'])
        self.assertEqual(Decimal(performance['recorded_trading_fees_usd']), Decimal('1'))

    def test_stress_breach_is_diagnostic_and_does_not_change_positions(self):
        self.ledger.fill(self.fill())
        self.mark('1000')
        revision = self.ledger.revision()
        report = self.ledger.snapshot()
        self.assertTrue(report['portfolio_stress']['scenarios'][2]['drawdown_limit_reached'])
        self.assertFalse(report['portfolio_stress']['changes_funding_limits'])
        self.assertEqual(report['positions'][0]['quantity'], '2')
        self.assertEqual(self.ledger.revision(), revision)

    def test_cash_only_stress_and_attribution_include_api_reservations(self):
        self.store.reserve('fixture', 'risk', 'test', Decimal('3'), Decimal('20'))
        report = self.ledger.snapshot()
        self.assertEqual(Decimal(report['performance_attribution']['net_pnl_after_recorded_costs_usd']), Decimal('-3'))
        for scenario in report['portfolio_stress']['scenarios']:
            self.assertEqual(Decimal(scenario['loss_usd']), Decimal('0'))
            self.assertEqual(Decimal(scenario['net_equity_estimate_usd']), Decimal('4997'))


if __name__=='__main__': unittest.main()
