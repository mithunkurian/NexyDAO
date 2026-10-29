"""Transactional USD simulation accounting. No broker or agent mutation tools."""
import hashlib
import json
import re
import time
from decimal import Decimal, localcontext, ROUND_UP, ROUND_DOWN

from .owner_policy import amount, from_env
from .market import load_market_evidence

INITIAL = Decimal('5000')
MAX_GROSS = Decimal('1000')
MAX_DRAWDOWN = Decimal('0.10')
QUANTUM = Decimal('0.00000001')


class PortfolioError(RuntimeError):
    pass


class Portfolio:
    def __init__(self, store):
        self.store, self.db = store, store.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id INTEGER PRIMARY KEY CHECK(id=1), cash TEXT NOT NULL, unsettled TEXT NOT NULL,
            realized TEXT NOT NULL, fees TEXT NOT NULL, peak TEXT NOT NULL, revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS simulation_fills (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, settled INTEGER NOT NULL DEFAULT 0, proceeds TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS simulated_positions (
            symbol TEXT PRIMARY KEY, quantity TEXT NOT NULL, basis TEXT NOT NULL, con_id INTEGER);
        CREATE TABLE IF NOT EXISTS portfolio_marks (
            symbol TEXT PRIMARY KEY, con_id INTEGER NOT NULL, bid TEXT NOT NULL,
            expires_at INTEGER NOT NULL, digest TEXT NOT NULL);
        ''')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO portfolio_state VALUES(1,'5000','0','0','0','5000',0)")

    def revision(self):
        return self.db.execute('SELECT revision FROM portfolio_state WHERE id=1').fetchone()[0]

    def assert_revision(self, expected):
        if self.revision() != expected:
            raise PortfolioError('portfolio_changed_during_cycle')

    def snapshot(self, now=None):
        with localcontext() as context:
            context.prec=50
            return self._read(self._snapshot,now)

    def _read(self, function, *args):
        if self.db.in_transaction: return function(*args)
        self.db.execute('BEGIN')
        try:
            value=function(*args)
            self.db.commit()
            return value
        except Exception:
            self.db.rollback()
            raise

    def _snapshot(self, now=None):
        self._reconcile()
        state = self.db.execute('SELECT cash,unsettled,realized,fees,peak,revision FROM portfolio_state WHERE id=1').fetchone()
        cash, unsettled, realized, fees, peak = map(Decimal, state[:5])
        rows = self.db.execute('SELECT p.symbol,p.quantity,p.basis,p.con_id,m.bid,m.expires_at,m.digest,m.con_id '
                               'FROM simulated_positions p LEFT JOIN portfolio_marks m ON p.symbol=m.symbol ORDER BY p.symbol').fetchall()
        if rows and now is None:
            now = time.time()
        positions, value, gross, complete = [], Decimal(0), Decimal(0), True
        for symbol, quantity, basis, conid, bid, expiry, digest, mark_conid in rows:
            qty, cost = Decimal(quantity), Decimal(basis)
            fresh = bid is not None and conid is not None and conid==mark_conid and now < expiry
            market_value = qty*Decimal(bid) if fresh else None
            if market_value is None:
                complete = False
            else:
                value += market_value
            gross += max(cost, market_value or Decimal(0))
            positions.append({'symbol': symbol, 'quantity': str(qty), 'cost_basis_usd': str(cost),
                              'contract_id': conid, 'market_value_usd': str(market_value) if fresh else None,
                              'mark_status': 'fresh_verified_bid' if fresh else 'missing_or_expired',
                              'mark_expires_at': expiry, 'mark_digest': digest})
        api = Decimal(self.store.costs()['estimated_or_reserved_usd'])
        from .reservations import active_holds
        holds=active_holds(self.db)
        reserved=sum((Decimal(h['total_usd']) for h in holds),Decimal(0))
        by_symbol={}
        for hold in holds:by_symbol[hold['symbol']]=str(Decimal(by_symbol.get(hold['symbol'],'0'))+Decimal(hold['total_usd']))
        equity = cash+unsettled+value-api if complete else None
        drawdown = max(Decimal(0), (peak-equity)/peak) if equity is not None else None
        result = {'simulated_capital_usd': 5000, 'currency': 'USD', 'settled_cash_usd': str(cash),
                'unsettled_cash_usd': str(unsettled), 'available_cash_after_api_estimate_usd': str(max(Decimal(0),cash-api-reserved)),
                'simulation_planning_reserved_usd':str(reserved),'simulation_planning_reserved_by_symbol':by_symbol,
                'simulation_planning_notional_usd':str(sum((Decimal(h['notional_usd']) for h in holds),Decimal(0))),
                'simulation_planning_fee_usd':str(sum((Decimal(h['fee_usd']) for h in holds),Decimal(0))),
                'positions': positions, 'realized_pnl_usd': str(realized), 'simulation_fees_usd': str(fees),
                'api_expense_estimate_or_reserved_usd': str(api), 'valuation_complete': complete,
                'net_equity_estimate_usd': str(equity) if equity is not None else None,
                'net_return_estimate_pct': str((equity/INITIAL-1)*100) if equity is not None else None,
                'gross_risk_exposure_usd': str(gross), 'peak_observed_net_equity_usd': str(peak),
                'drawdown_fraction': str(drawdown) if drawdown is not None else None, 'revision': state[5],
                'annual_net_target': 0.15, 'annual_net_return_established': False,
                'risk_limits':{'max_gross_usd':str(MAX_GROSS),'max_drawdown_fraction':str(MAX_DRAWDOWN)},
                'tax_and_fx_model_complete': False, 'execution_enabled': False,
                'simulation_internal_reconciliation':True, 'broker_reconciliation':False,
                'accounting_mode': 'USD_simulation_only'}
        from .portfolio_risk import reports
        attribution, stress = reports(result)
        if complete and not attribution['equity_change_reconciled']:
            raise PortfolioError('performance_attribution_not_reconciled')
        result['performance_attribution'] = attribution
        result['portfolio_stress'] = stress
        return result

    def reconcile(self):
        return self._read(self._reconcile)

    def _reconcile(self):
        rows=self.db.execute('SELECT id,payload,settled,proceeds FROM simulation_fills ORDER BY rowid').fetchall()
        if len(rows)>10000: raise PortfolioError('simulation_history_limit')
        cash,pending,realized,fees=INITIAL,Decimal(0),Decimal(0),Decimal(0)
        positions={}
        with localcontext() as context:
            context.prec=50
            for identifier,payload,settled,stored_proceeds in rows:
                data=json.loads(payload)
                if (set(data)!={'id','side','symbol','quantity','price','fee','currency','asset_type'}
                        or data['id']!=identifier or data['currency']!='USD' or data['asset_type']!='STK'
                        or settled not in (0,1) or data['side'] not in {'buy','sell'}):
                    raise PortfolioError('simulation_reconciliation_failed')
                qty,price,fee=map(amount,(data['quantity'],data['price'],data['fee']))
                held,basis=positions.get(data['symbol'],(Decimal(0),Decimal(0)))
                notional=(qty*price).quantize(QUANTUM,rounding=ROUND_UP if data['side']=='buy' else ROUND_DOWN)
                if qty<=0 or price<=0: raise PortfolioError('simulation_reconciliation_failed')
                if data['side']=='buy':
                    if settled!=1 or Decimal(stored_proceeds)!=0: raise PortfolioError('simulation_reconciliation_failed')
                    cash-=notional+fee
                    held+=qty
                    basis+=notional+fee
                else:
                    if qty>held or notional<fee or Decimal(stored_proceeds)!=notional-fee:
                        raise PortfolioError('simulation_reconciliation_failed')
                    removed=basis if qty==held else (basis*qty/held).quantize(QUANTUM,rounding=ROUND_DOWN)
                    held-=qty
                    basis-=removed
                    realized+=notional-fee-removed
                    if settled: cash+=notional-fee
                    else: pending+=notional-fee
                fees+=fee
                if held: positions[data['symbol']]=(held,basis)
                else: positions.pop(data['symbol'],None)
        recorded=self.db.execute('SELECT cash,unsettled,realized,fees FROM portfolio_state WHERE id=1').fetchone()
        actual={s:(Decimal(q),Decimal(b)) for s,q,b in self.db.execute('SELECT symbol,quantity,basis FROM simulated_positions')}
        if tuple(map(Decimal,recorded))!=(cash,pending,realized,fees) or actual!=positions or cash<0 or pending<0:
            raise PortfolioError('simulation_reconciliation_failed')
        return True

    def fill(self, data, policy=None):
        policy = policy or from_env()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = self._record_fill(data, policy)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def _record_fill(self, data, policy, reservation_credit=None):
        """Record within the caller's transaction; credit only a validated own hold."""
        if not self.db.in_transaction:
            raise PortfolioError('simulation_fill_transaction_required')
        policy = policy or from_env()
        policy.assert_current()
        keys = {'id','side','symbol','quantity','price','fee','currency','asset_type'}
        if not isinstance(data, dict) or set(data) != keys:
            raise PortfolioError('invalid_simulation_fill_schema')
        if (not isinstance(data['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',data['id'])
                or data['side'] not in {'buy','sell'} or not isinstance(data['symbol'],str)
                or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',data['symbol'])
                or data['currency'] != 'USD' or data['asset_type'] != 'STK'):
            raise PortfolioError('USD_long_stock_simulation_required')
        qty, price, fee = map(amount,(data['quantity'],data['price'],data['fee']))
        if qty<=0 or price<=0:
            raise PortfolioError('positive_simulated_quantity_and_price_required')
        serialized = json.dumps(data,sort_keys=True,separators=(',',':'))
        old = self.db.execute('SELECT payload FROM simulation_fills WHERE id=?',(data['id'],)).fetchone()
        if old:
            if old[0]!=serialized: raise PortfolioError('conflicting_simulated_fill_id')
            return {'status':'already_recorded','id':data['id'],'execution_authorized':False}
        snapshot = self.snapshot()
        if reservation_credit is not None:
            # The outer reservation transaction checks identity and remaining
            # budgets. Replace only this fill's debit with the resulting holding;
            # all other holds and the unspent remainder continue to count.
            credit = reservation_credit
            snapshot['available_cash_after_api_estimate_usd'] = str(
                max(Decimal(0),Decimal(snapshot['settled_cash_usd'])
                    -Decimal(snapshot['api_expense_estimate_or_reserved_usd'])
                    -Decimal(snapshot['simulation_planning_reserved_usd'])+credit))
            snapshot['simulation_planning_reserved_usd'] = str(
                Decimal(snapshot['simulation_planning_reserved_usd'])-credit)
            by_symbol = dict(snapshot['simulation_planning_reserved_by_symbol'])
            by_symbol[data['symbol']] = str(Decimal(by_symbol[data['symbol']])-credit)
            snapshot['simulation_planning_reserved_by_symbol'] = by_symbol
        cash, pending = Decimal(snapshot['settled_cash_usd']), Decimal(snapshot['unsettled_cash_usd'])
        realized, fees = Decimal(snapshot['realized_pnl_usd']), Decimal(snapshot['simulation_fees_usd'])
        row = self.db.execute('SELECT quantity,basis FROM simulated_positions WHERE symbol=?',(data['symbol'],)).fetchone()
        held, basis = map(Decimal,row) if row else (Decimal(0),Decimal(0))
        with localcontext() as context:
            context.prec=50
            notional=qty*price
            if notional>Decimal('1000000000000'): raise PortfolioError('bounded_simulated_notional_required')
            notional=notional.quantize(QUANTUM,rounding=ROUND_UP if data['side']=='buy' else ROUND_DOWN)
            if data['side']=='buy':
                reasons=allocation_reasons(snapshot,[{'symbol':data['symbol'],'allocation_usd':format(notional+fee,'f')}],policy)
                if reasons: raise PortfolioError(reasons[0])
                cash-=notional+fee
                held+=qty
                basis+=notional+fee
            else:
                if qty>held: raise PortfolioError('owner_no_short_selling')
                if fee>Decimal(snapshot['available_cash_after_api_estimate_usd']):
                    raise PortfolioError('owner_cash_funding_required')
                if notional<fee: raise PortfolioError('sale_fees_exceed_proceeds')
                removed = basis if qty==held else (basis*qty/held).quantize(QUANTUM,rounding=ROUND_DOWN)
                held-=qty
                basis-=removed
                realized+=notional-fee-removed
                pending+=notional-fee
        fees+=fee
        if held==0:
            self.db.execute('DELETE FROM simulated_positions WHERE symbol=?',(data['symbol'],))
        else:
            self.db.execute('INSERT INTO simulated_positions(symbol,quantity,basis) VALUES(?,?,?) '
                            'ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity,basis=excluded.basis',
                            (data['symbol'],str(held),str(basis)))
        self.db.execute('UPDATE portfolio_state SET cash=?,unsettled=?,realized=?,fees=?,revision=revision+1 WHERE id=1',
                        (str(cash),str(pending),str(realized),str(fees)))
        self.db.execute('INSERT INTO simulation_fills(id,payload,settled,proceeds) VALUES(?,?,?,?)',
                        (data['id'],serialized,int(data['side']=='buy'),str(notional-fee) if data['side']=='sell' else '0'))
        policy.assert_current()
        return {'status':'simulated_fixture_recorded','id':data['id'],'execution_authorized':False}

    def settle(self, fill_id):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.reconcile()
            row=self.db.execute('SELECT payload,settled,proceeds FROM simulation_fills WHERE id=?',(fill_id,)).fetchone()
            if not row: raise PortfolioError('unknown_simulated_settlement')
            fill=json.loads(row[0])
            if fill['side']!='sell': raise PortfolioError('only_sale_proceeds_require_settlement')
            if not row[1]:
                proceeds=Decimal(row[2])
                cash,pending=self.db.execute('SELECT cash,unsettled FROM portfolio_state WHERE id=1').fetchone()
                if proceeds>Decimal(pending): raise PortfolioError('settlement_reconciliation_failed')
                self.db.execute('UPDATE portfolio_state SET cash=?,unsettled=?,revision=revision+1 WHERE id=1',
                                (str(Decimal(cash)+proceeds),str(Decimal(pending)-proceeds)))
                self.db.execute('UPDATE simulation_fills SET settled=1 WHERE id=?',(fill_id,))
            self.db.commit()
            return {'status':'simulation_settled','id':fill_id,'execution_authorized':False}
        except Exception:
            self.db.rollback()
            raise

    def mark(self, path, config):
        evidence=load_market_evidence(path,config)
        item=evidence[0]
        summary=json.loads(item['summary'])
        contract, quote = summary['contract'],summary['quote']
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.reconcile()
            row=self.db.execute('SELECT con_id FROM simulated_positions WHERE symbol=?',(contract['symbol'],)).fetchone()
            if not row: raise PortfolioError('mark_requires_existing_simulated_position')
            if row[0] is not None and row[0]!=contract['con_id']: raise PortfolioError('position_contract_mismatch')
            self.db.execute('UPDATE simulated_positions SET con_id=? WHERE symbol=?',(contract['con_id'],contract['symbol']))
            # Fingerprint already derived from the authenticated payload. Do not
            # reread an untrusted file after validation or hash an unbounded body.
            digest=item['id'].removeprefix('quote-')
            self.db.execute('INSERT OR REPLACE INTO portfolio_marks VALUES(?,?,?,?,?)',
                            (contract['symbol'],contract['con_id'],quote['bid'],item['expires_at'],digest))
            self.db.execute('UPDATE portfolio_state SET revision=revision+1 WHERE id=1')
            snapshot=self.snapshot()
            if snapshot['valuation_complete']:
                peak=max(Decimal(snapshot['peak_observed_net_equity_usd']),Decimal(snapshot['net_equity_estimate_usd']))
                self.db.execute('UPDATE portfolio_state SET peak=? WHERE id=1',(str(peak),))
            self.db.commit()
            return {'status':'simulated_position_marked','execution_authorized':False}
        except Exception:
            self.db.rollback()
            raise


def allocation_reasons(snapshot, allocations, policy):
    document=policy.document()
    reasons=[]
    total=Decimal(0)
    gross=Decimal(snapshot['gross_risk_exposure_usd'])+Decimal(snapshot.get('simulation_planning_reserved_usd','0'))
    held={p['symbol']:max(Decimal(p['cost_basis_usd']),Decimal(p['market_value_usd'] or '0')) for p in snapshot['positions']}
    for symbol,value in snapshot.get('simulation_planning_reserved_by_symbol',{}).items():
        held[symbol]=held.get(symbol,Decimal(0))+Decimal(value)
    seen=set()
    for allocation in allocations:
        symbol=allocation['symbol']
        dollars=amount(str(allocation['allocation_usd']))
        if symbol in seen: reasons.append('duplicate_allocation_symbol')
        seen.add(symbol)
        total+=dollars
        if symbol in document['blocked_symbols']: reasons.append('owner_blocked_symbol')
        if held.get(symbol,Decimal(0))+dollars>amount(document['max_position_usd']): reasons.append('aggregate_position_limit_exceeded')
    if allocations and total>Decimal(snapshot['available_cash_after_api_estimate_usd']): reasons.append('owner_cash_funding_required')
    if allocations and Decimal(snapshot['available_cash_after_api_estimate_usd'])-total<amount(document['min_cash_reserve_usd']): reasons.append('aggregate_cash_reserve_breached')
    if allocations and gross+total>MAX_GROSS: reasons.append('aggregate_exposure_limit_exceeded')
    if allocations and document['additional_rules']: reasons.append('additional_owner_rule_enforcement_pending')
    if allocations and snapshot['positions'] and not snapshot['valuation_complete']: reasons.append('fresh_portfolio_valuation_required')
    if allocations and snapshot['drawdown_fraction'] is not None and Decimal(snapshot['drawdown_fraction'])>=MAX_DRAWDOWN:
        reasons.append('drawdown_limit_exceeded')
    return sorted(set(reasons))
