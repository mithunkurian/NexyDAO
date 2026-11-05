from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json
from threading import Barrier
import unittest

import test_reservations as fixtures
from nexydao.allocation import AllocationConfig
from nexydao.owner_policy import load_policy
from nexydao.portfolio import Portfolio,PortfolioError,allocation_reasons
from nexydao.portfolio_risk import projected_stress_reasons
from nexydao.reservations import Reservations
from nexydao.store import Store
from nexydao.market import canonical


class CommitmentRiskTests(unittest.TestCase):
    setUp=fixtures.ReservationTests.setUp
    request=fixtures.ReservationTests.request
    reserve=fixtures.ReservationTests.reserve
    held_fill=fixtures.ReservationTests.held_fill
    mark=fixtures.ReservationTests.mark

    def test_stress_guard_blocks_new_risk_before_current_drawdown_reaches_limit(self):
        fill=self.held_fill(quantity='5',fee='0')['fill']
        self.ledger.fill(fill,self.policy);self.mark()
        # Signed bid observation for the fixture is changed through the existing
        # test quote signer, never by editing portfolio accounting rows.
        import test_portfolio as quote_fixtures
        quote_fixtures.PortfolioTests.mark(self,bid='20',symbol='SPY')
        before=self.ledger.snapshot()
        self.assertEqual(Decimal(before['drawdown_fraction']),Decimal('.08'))
        self.assertIn('projected_stress_drawdown_limit_exceeded',
                      allocation_reasons(before,[{'symbol':'OTHER','allocation_usd':'100'}],self.policy))
        with self.assertRaisesRegex(PortfolioError,'projected_stress'):
            self.reserve(self.request('new','OTHER','100','0'))
        unreserved={**fill,'id':'new-buy','symbol':'OTHER','quantity':'1'}
        with self.assertRaisesRegex(PortfolioError,'projected_stress'):self.ledger.fill(unreserved,self.policy)
        self.assertEqual(self.ledger.snapshot(),before)

    def test_stress_uses_full_fee_and_api_cost_once_with_upward_rounding(self):
        snapshot=self.ledger.snapshot()
        self.assertEqual(projected_stress_reasons(snapshot,Decimal('900'),Decimal('50')),[])
        self.assertTrue(projected_stress_reasons(snapshot,Decimal('950'),Decimal('50')))
        snapshot['net_equity_estimate_usd']='4600'
        snapshot['positions']=[{'market_value_usd':'100'}]
        self.assertTrue(projected_stress_reasons(snapshot,Decimal('99.99999999')))
        self.assertEqual(projected_stress_reasons(snapshot,Decimal('99.99999998')),[])
        snapshot['risk_limits']['max_drawdown_fraction']='1'
        self.assertTrue(projected_stress_reasons(snapshot,Decimal('100')))  # Fixed guard cannot be relaxed by a report field.

    def test_recorded_fee_buffer_survives_restart_and_api_cost_blocks_deployment(self):
        self.reserve(self.request('plan','SPY','475','0'))
        self.reserve(self.request('other','MSFT','475','0'))
        self.store.reserve('fixture','api','test',Decimal('.01'),Decimal('1000'))
        before=self.ledger.snapshot()
        reopened=Store(self.root/'db.sqlite')
        try:
            book=Reservations(Portfolio(reopened))
            with self.assertRaisesRegex(PortfolioError,'cash_reserve_breached'):
                book.fill(self.held_fill(quantity='1',fee='0'),self.policy)
            self.assertEqual(Portfolio(reopened).snapshot(),before)
        finally:reopened.close()
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM simulation_fills').fetchone()[0],0)

    def test_active_cap_cannot_be_relaxed_by_another_reservation_or_unreserved_buy(self):
        self.book.reserve(self.request(notional='300',fee='0'),self.policy,AllocationConfig('400','50'))
        before=self.ledger.snapshot()
        with self.assertRaisesRegex(PortfolioError,'allocation_cap'):
            self.book.reserve(self.request('larger','MSFT','100','0'),self.policy,AllocationConfig())
        fill={**self.held_fill()['fill'],'id':'unreserved','symbol':'MSFT','quantity':'1','price':'100','fee':'0'}
        with self.assertRaisesRegex(PortfolioError,'allocation_cap'):self.ledger.fill(fill,self.policy)
        self.assertEqual(self.ledger.snapshot(),before)

    def test_fill_rechecks_original_allocation_cap_after_api_cost_change(self):
        self.book.reserve(self.request(notional='300',fee='0'),self.policy,AllocationConfig('400','50'))
        self.store.reserve('fixture','api','test',Decimal('51'),Decimal('1000'))
        before=self.ledger.snapshot()
        with self.assertRaisesRegex(PortfolioError,'allocation_cap'):
            self.book.fill(self.held_fill(quantity='1',fee='0'),self.policy)
        self.assertEqual(self.ledger.snapshot(),before)

    def test_idempotent_active_request_does_not_silently_replace_limits(self):
        self.reserve();before=self.ledger.snapshot()
        with self.assertRaisesRegex(PortfolioError,'limits_changed'):
            self.book.reserve(self.request(),self.policy,AllocationConfig('1000','50'))
        self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(self.reserve()['status'],'already_active')

    def test_reserved_fill_moves_budget_into_position_without_double_stress_counting(self):
        self.reserve(self.request(notional='400',fee='2'))
        self.book.fill(self.held_fill(),self.policy)
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['simulation_planning_notional_usd']),Decimal('200'))
        self.assertEqual(Decimal(snapshot['simulation_planning_fee_usd']),Decimal('1'))
        self.mark();self.book.fill(self.held_fill('second'),self.policy)
        self.assertEqual(self.reserve()['status'],'already_consumed')
        self.assertEqual(Decimal(self.ledger.snapshot()['simulation_planning_reserved_usd']),Decimal(0))

    def test_legacy_limits_are_not_invented_or_released_during_upgrade(self):
        self.reserve();self.store.db.execute('DROP TABLE simulation_reservation_limits');self.store.db.commit()
        book=Reservations(self.ledger);snapshot=self.ledger.snapshot()
        self.assertFalse(snapshot['simulation_commitment_limits_complete'])
        self.assertEqual(Decimal(snapshot['simulation_planning_reserved_usd']),Decimal('402'))
        for operation in (lambda:book.fill(self.held_fill(),self.policy),
                          lambda:book.reserve(self.request('new','MSFT','10','0'),self.policy,self.settings)):
            with self.assertRaisesRegex(PortfolioError,'limits_missing'):operation()
        book.release('plan',self.policy)
        self.assertEqual(Decimal(self.ledger.snapshot()['simulation_planning_reserved_usd']),Decimal(0))
        self.assertEqual(self.ledger.snapshot()['settled_cash_usd'],'5000')

    def test_corrupt_or_orphan_limit_context_stops_replay(self):
        self.reserve()
        original=self.store.db.execute('SELECT payload,digest FROM simulation_reservation_limits').fetchone()
        self.store.db.execute("UPDATE simulation_reservation_limits SET payload='{}'");self.store.db.commit()
        with self.assertRaisesRegex(PortfolioError,'limits_corrupt'):self.ledger.snapshot()
        self.store.db.execute('UPDATE simulation_reservation_limits SET payload=?,digest=?',original)
        orphan=json.loads(original[0]);orphan['reservation_id']='orphan'
        self.store.db.execute('INSERT INTO simulation_reservation_limits VALUES(?,?,?)',
                              ('orphan',json.dumps(orphan),hashlib.sha256(canonical(orphan)).hexdigest()))
        self.store.db.commit()
        with self.assertRaisesRegex(PortfolioError,'limits_corrupt'):self.ledger.snapshot()

    def test_missing_main_hold_table_cannot_hide_surviving_audit_context(self):
        self.reserve()
        self.store.db.execute('DROP TABLE simulation_reservations');self.store.db.commit()
        with self.assertRaisesRegex(PortfolioError,'audit_mismatch'):self.ledger.snapshot()

    def test_strictest_active_envelope_is_combined_without_excess_cross_pair_tightening(self):
        self.book.reserve(self.request('a','AAA','100','0'),self.policy,AllocationConfig('400','10'))
        self.book.reserve(self.request('b','BBB','100','0'),self.policy,AllocationConfig('500','100'))
        snapshot=self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot['simulation_commitment_net_cap_usd']),Decimal('390'))
        self.assertEqual(Decimal(snapshot['simulation_commitment_fee_buffer_usd']),Decimal('100'))
        self.book.reserve(self.request('c','CCC','190','0'),self.policy,AllocationConfig())
        with self.assertRaisesRegex(PortfolioError,'allocation_cap'):
            self.book.reserve(self.request('d','DDD','1','0'),self.policy,AllocationConfig())

    def test_concurrent_different_defaults_cannot_escape_existing_cap(self):
        self.book.reserve(self.request('existing','SPY','100','0'),self.policy,AllocationConfig('400','50'))
        barrier=Barrier(2)
        def worker(symbol):
            store=Store(self.root/'db.sqlite')
            try:
                book=Reservations(Portfolio(store));barrier.wait(timeout=5)
                try:book.reserve(self.request(symbol,symbol,'200','0'),load_policy(),AllocationConfig());return True
                except PortfolioError:return False
            finally:store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,('AAA','BBB')))
        self.assertEqual(sum(results),1)
        self.assertEqual(Decimal(self.ledger.snapshot()['simulation_planning_reserved_usd']),Decimal('300'))

    def test_reducing_positions_remains_available_after_new_risk_stress_block(self):
        self.ledger.fill(self.held_fill(quantity='5',fee='0')['fill'],self.policy)
        self.mark()
        import test_portfolio as quote_fixtures
        quote_fixtures.PortfolioTests.mark(self,bid='20',symbol='SPY')
        sell={**self.held_fill()['fill'],'id':'reduce','side':'sell','quantity':'1','price':'20','fee':'0'}
        self.ledger.fill(sell,self.policy)
        self.assertEqual(self.ledger.snapshot()['positions'][0]['quantity'],'4')
        self.assertEqual(Decimal(self.ledger.snapshot()['unsettled_cash_usd']),Decimal('20'))
