import copy
import json
import os
import subprocess
import sys
import unittest
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import test_funding as fixtures
import test_portfolio as portfolio_fixtures
from nexydao.ibkr import BrokerConfig
from nexydao.market import MarketConfig
from nexydao.allocation import AllocationConfig
from nexydao.owner_policy import load_policy,OwnerPolicyError
from nexydao.portfolio import Portfolio,PortfolioError
from nexydao.reservations import Reservations
from nexydao.store import Store


class ReservationTests(unittest.TestCase):
    def setUp(self):
        fixtures.FundingTests.setUp(self)
        self.book=Reservations(self.ledger)
        self.settings=AllocationConfig()

    def request(self,identifier='plan',symbol='SPY',notional='400',fee='2'):
        return {'id':identifier,'proposal_sha256':'a'*64,'symbol':symbol,'notional_usd':notional,'fee_usd':fee,'fee_currency':'USD'}

    def reserve(self,data=None):return self.book.reserve(data or self.request(),self.policy,self.settings)

    def held_fill(self,identifier='fill1',quantity='2',price='100',fee='1'):
        return {'reservation_id':'plan','proposal_sha256':'a'*64,
                'fill':{'id':identifier,'side':'buy','symbol':'SPY','quantity':quantity,'price':price,
                        'fee':fee,'currency':'USD','asset_type':'STK'}}

    def mark(self):
        self.key=self.root/'key'
        self.key.write_bytes(b'x'*32);self.key.chmod(0o600)
        self.market=MarketConfig(BrokerConfig(expected_account='DU123'),self.key,'SPY',self.root/'quote.json')
        portfolio_fixtures.PortfolioTests.mark(self,symbol='SPY')

    def test_persistent_hold_reduces_capacity_without_spending_capital(self):
        before=self.ledger.snapshot();costs=self.store.costs();result=self.reserve()
        now=self.ledger.snapshot()
        self.assertEqual(now['settled_cash_usd'],before['settled_cash_usd'])
        self.assertEqual(now['simulation_planning_reserved_usd'],'402')
        self.assertEqual(now['available_cash_after_api_estimate_usd'],'4598')
        self.assertEqual(now['revision'],before['revision']+1)
        self.assertEqual(now['net_equity_estimate_usd'],before['net_equity_estimate_usd'])
        self.assertFalse(result['execution_authorized']);self.assertFalse(result['broker_funds_reserved'])
        self.assertEqual(costs,self.store.costs())
        reopened=Store(self.root/'db.sqlite')
        try:self.assertEqual(Portfolio(reopened).snapshot()['simulation_planning_reserved_usd'],'402')
        finally:reopened.close()

    def test_same_id_is_idempotent_and_conflicts_fail(self):
        self.reserve();revision=self.ledger.revision()
        self.assertEqual(self.reserve()['status'],'already_active')
        self.assertEqual(self.ledger.revision(),revision)
        with self.assertRaises(PortfolioError):self.reserve(self.request(notional='399'))

    def test_release_is_explicit_idempotent_and_never_auto_expired(self):
        self.reserve()
        self.book.release('plan',self.policy)
        revision=self.ledger.revision()
        self.book.release('plan',self.policy)
        self.assertEqual(self.ledger.revision(),revision)
        self.assertEqual(self.ledger.snapshot()['simulation_planning_reserved_usd'],'0')
        self.assertEqual(self.reserve()['status'],'already_released')
        with self.assertRaises(PortfolioError):self.book.release('unknown',self.policy)

    def test_fee_currency_and_position_limit_fail(self):
        data=self.request();data['fee_currency']='SEK'
        with self.assertRaises(PortfolioError):self.reserve(data)
        with self.assertRaises(PortfolioError):self.reserve(self.request(notional='499',fee='2'))
        self.reserve()
        with self.assertRaises(PortfolioError):self.reserve(self.request('second',notional='100',fee='0'))

    def test_other_symbols_cannot_exhaust_cash_buffer(self):
        self.reserve(self.request(notional='500',fee='0'))
        with self.assertRaises(PortfolioError):self.reserve(self.request('second','MSFT','500','0'))

    def test_concurrent_connections_cannot_double_reserve_capacity(self):
        barrier=Barrier(2)
        def worker(identifier):
            store=Store(self.root/'db.sqlite')
            try:
                book=Reservations(Portfolio(store));barrier.wait(timeout=5)
                try:book.reserve(self.request(identifier,identifier,'500','0'),load_policy(),self.settings);return True
                except PortfolioError:return False
            finally:store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(worker,('AAA','BBB')))
        self.assertEqual(results.count(True),1)
        self.assertEqual(self.ledger.snapshot()['simulation_planning_reserved_usd'],'500')

    def test_policy_change_before_commit_rolls_back_hold_and_revision(self):
        before=self.ledger.revision()
        with patch.object(type(self.policy),'assert_current',side_effect=[None,OwnerPolicyError('changed')]):
            with self.assertRaises(OwnerPolicyError):self.reserve()
        self.assertEqual(self.ledger.snapshot()['simulation_planning_reserved_usd'],'0')
        self.assertEqual(self.ledger.revision(),before)

    def test_audit_corruption_cannot_release_money_silently(self):
        self.reserve()
        self.store.db.execute("UPDATE simulation_reservations SET status='released'");self.store.db.commit()
        with self.assertRaises(PortfolioError):self.ledger.snapshot()

    def test_simulated_fill_cannot_spend_or_ignore_existing_holds(self):
        self.reserve()
        fill={'id':'fixture','side':'buy','symbol':'SPY','quantity':'2','price':'100','fee':'0','currency':'USD','asset_type':'STK'}
        with self.assertRaises(PortfolioError):self.ledger.fill(fill,self.policy)
        self.assertEqual(self.ledger.snapshot()['settled_cash_usd'],'5000')

    def test_broker_reservation_is_always_disabled(self):
        with self.assertRaises(PermissionError):self.book.reserve_broker(self.request())

    def test_partial_fills_atomically_consume_separate_budgets_and_survive_restart(self):
        self.reserve()
        self.book.fill(self.held_fill(),self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['settled_cash_usd']),Decimal('4799'))
        self.assertEqual(Decimal(snapshot['simulation_planning_reserved_usd']),Decimal('201'))
        self.assertEqual(Decimal(snapshot['available_cash_after_api_estimate_usd']),Decimal('4598'))
        with self.assertRaisesRegex(PortfolioError,'fresh_portfolio_valuation_required'):
            self.book.fill(self.held_fill('fill2'),self.policy)
        self.assertEqual(self.ledger.snapshot(),snapshot)
        self.mark()
        self.book.fill(self.held_fill('fill2'),self.policy)
        self.assertEqual(self.reserve()['status'],'already_consumed')
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['settled_cash_usd']),Decimal('4598'))
        self.assertEqual(Decimal(snapshot['simulation_planning_reserved_usd']),Decimal(0))
        self.assertEqual(snapshot['positions'][0]['quantity'],'4')
        self.assertTrue(snapshot['performance_attribution']['equity_change_reconciled'])
        reopened=Store(self.root/'db.sqlite')
        try:
            ledger=Portfolio(reopened)
            self.assertEqual(ledger.snapshot(),snapshot)
        finally:reopened.close()

    def test_retry_after_consumption_is_idempotent_and_conflicts_fail(self):
        self.reserve(self.request(notional='200',fee='1'))
        data=self.held_fill()
        self.book.fill(data,self.policy)
        revision=self.ledger.revision()
        self.assertEqual(self.book.fill(data,self.policy)['status'],'already_recorded')
        self.assertEqual(self.ledger.revision(),revision)
        changed=copy.deepcopy(data);changed['fill']['price']='99'
        with self.assertRaises(PortfolioError):self.book.fill(changed,self.policy)
        self.assertEqual(self.ledger.revision(),revision)

    def test_fee_overrun_cannot_spend_unused_notional(self):
        self.reserve()
        with self.assertRaisesRegex(PortfolioError,'reserved_fill_budget_exceeded'):
            self.book.fill(self.held_fill(quantity='1',fee='3'),self.policy)
        with self.assertRaisesRegex(PortfolioError,'reserved_fill_budget_exceeded'):
            self.book.fill(self.held_fill(quantity='5',fee='0'),self.policy)
        self.assertEqual(self.ledger.snapshot()['settled_cash_usd'],'5000')
        self.assertEqual(self.store.db.execute('select count(*) from simulation_fills').fetchone()[0],0)

    def test_binding_wrong_side_and_released_hold_are_rejected(self):
        self.reserve()
        for mutation in ('proposal','symbol','side','currency','reservation'):
            data=self.held_fill()
            if mutation=='proposal':data['proposal_sha256']='b'*64
            if mutation=='symbol':data['fill']['symbol']='OTHER'
            if mutation=='side':data['fill']['side']='sell'
            if mutation=='currency':data['fill']['currency']='SEK'
            if mutation=='reservation':data['reservation_id']='missing'
            with self.subTest(mutation=mutation),self.assertRaises(PortfolioError):self.book.fill(data,self.policy)
        self.book.release('plan',self.policy)
        with self.assertRaisesRegex(PortfolioError,'not_active'):self.book.fill(self.held_fill(),self.policy)

    def test_partial_release_frees_only_remainder_and_preserves_fill(self):
        self.reserve()
        self.book.fill(self.held_fill(),self.policy)
        self.book.release('plan',self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['settled_cash_usd']),Decimal('4799'))
        self.assertEqual(Decimal(snapshot['simulation_planning_reserved_usd']),Decimal(0))
        self.assertEqual(snapshot['positions'][0]['quantity'],'2')
        self.assertEqual(self.book.fill(self.held_fill(),self.policy)['status'],'already_recorded')

    def test_failure_before_commit_rolls_back_fill_hold_and_revision(self):
        self.reserve()
        before=self.ledger.snapshot()
        with patch.object(type(self.policy),'assert_current',side_effect=[None,None,None,OwnerPolicyError('changed')]):
            with self.assertRaises(OwnerPolicyError):self.book.fill(self.held_fill(),self.policy)
        self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(self.store.db.execute('select count(*) from simulation_reservation_fills').fetchone()[0],0)

    def test_concurrent_consumption_cannot_spend_same_hold_twice(self):
        self.reserve(self.request(notional='200',fee='1'))
        barrier=Barrier(2)
        def worker(identifier):
            store=Store(self.root/'db.sqlite')
            try:
                book=Reservations(Portfolio(store));barrier.wait(timeout=5)
                try:book.fill(self.held_fill(identifier),self.policy);return True
                except PortfolioError:return False
            finally:store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,('one','two')))
        self.assertEqual(results.count(True),1)
        self.assertEqual(Decimal(self.ledger.snapshot()['settled_cash_usd']),Decimal('4799'))

    def test_corrupt_or_missing_consumption_evidence_fails_replay(self):
        self.reserve()
        self.book.fill(self.held_fill(),self.policy)
        self.store.db.execute('delete from simulation_reservation_fills');self.store.db.commit()
        with self.assertRaisesRegex(PortfolioError,'audit_mismatch'):self.ledger.snapshot()

    def test_existing_unlinked_fill_cannot_be_relabelled_as_reserved(self):
        data=self.held_fill(quantity='1',fee='0')
        self.ledger.fill(data['fill'],self.policy)
        self.mark()
        self.reserve(self.request(notional='100',fee='1'))
        with self.assertRaisesRegex(PortfolioError,'conflicting_reserved_fill_id'):
            self.book.fill(data,self.policy)

    def test_current_api_costs_can_block_consumption_without_releasing_hold(self):
        self.reserve()
        self.store.reserve('fixture','cost','test',Decimal('600'),Decimal('1000'))
        before=self.ledger.snapshot()
        with self.assertRaisesRegex(PortfolioError,'cash_reserve_breached'):
            self.book.fill(self.held_fill(),self.policy)
        self.assertEqual(self.ledger.snapshot(),before)

    def test_concurrent_same_fill_retry_is_recorded_once(self):
        self.reserve(self.request(notional='200',fee='1'))
        barrier=Barrier(2)
        def worker(_):
            store=Store(self.root/'db.sqlite')
            try:
                book=Reservations(Portfolio(store));barrier.wait(timeout=5)
                return book.fill(self.held_fill(),self.policy)['status']
            finally:store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,range(2)))
        self.assertCountEqual(results,['simulated_fixture_recorded','already_recorded'])
        self.assertEqual(self.store.db.execute('select count(*) from simulation_fills').fetchone()[0],1)

    def test_cli_held_fixture_and_duplicate_keys_fail_safely(self):
        self.reserve(self.request(notional='200',fee='1'))
        path=self.root/'held-fill.json'
        path.write_text(json.dumps(self.held_fill()))
        env={**os.environ,'NEXYDAO_DB':str(self.root/'db.sqlite')}
        command=[sys.executable,'-m','nexydao','sim-fill','--held-fill',str(path)]
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['execution_authorized'])
        revision=self.ledger.revision()
        path.write_text('{"reservation_id":"plan",'+json.dumps(self.held_fill())[1:])
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.ledger.revision(),revision)

    def test_rounding_and_unused_fee_budget_remain_accounted(self):
        self.reserve(self.request(notional='0.00000001',fee='1'))
        self.book.fill(self.held_fill(quantity='0.00000001',price='0.1',fee='0'),self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['settled_cash_usd']),Decimal('4999.99999999'))
        self.assertEqual(Decimal(snapshot['simulation_planning_notional_usd']),Decimal(0))
        self.assertEqual(Decimal(snapshot['simulation_planning_fee_usd']),Decimal(1))
        with self.assertRaisesRegex(PortfolioError,'reserved_fill_budget_exceeded'):
            self.book.fill(self.held_fill('second',quantity='0.00000001',price='0.1',fee='0'),self.policy)
        self.book.release('plan',self.policy)
        self.assertEqual(Decimal(self.ledger.snapshot()['simulation_planning_reserved_usd']),Decimal(0))

    def test_legacy_hold_database_upgrades_without_releasing_capital(self):
        self.reserve(self.request(notional='200',fee='1'))
        self.store.db.execute('drop table simulation_reservation_fills');self.store.db.commit()
        before=self.ledger.snapshot()
        book=Reservations(self.ledger)
        self.assertEqual(self.ledger.snapshot(),before)
        book.fill(self.held_fill(),self.policy)
        self.assertEqual(self.reserve(self.request(notional='200',fee='1'))['status'],'already_consumed')
