import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import test_funding as fixtures
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
