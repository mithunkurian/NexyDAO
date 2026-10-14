"""Atomic USD simulation planning holds. Never a broker reservation or permit."""
import hashlib
import json
import re
import time
from decimal import Decimal

from .market import canonical
from .owner_policy import amount
from .portfolio import PortfolioError, allocation_reasons

FIELDS={'id','proposal_sha256','symbol','notional_usd','fee_usd','fee_currency'}


def validate_request(data):
    if not isinstance(data,dict) or set(data)!=FIELDS: raise PortfolioError('invalid_simulation_reservation')
    if (not isinstance(data['id'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',data['id'])
            or not isinstance(data['proposal_sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',data['proposal_sha256'])
            or not isinstance(data['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}',data['symbol'])):
        raise PortfolioError('invalid_simulation_reservation_identity')
    if data['fee_currency']!='USD': raise PortfolioError('foreign_fee_funding_unverified')
    notional,fee=amount(data['notional_usd']),amount(data['fee_usd'])
    if notional<=0: raise PortfolioError('positive_reservation_notional_required')
    return notional+fee


def active_holds(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='simulation_reservations'").fetchone():
        return []
    rows=db.execute('SELECT id,CASE WHEN length(payload)<=4000 THEN payload END,digest,status FROM simulation_reservations LIMIT 1001').fetchall()
    events=db.execute('SELECT reservation_id,action FROM simulation_reservation_events ORDER BY sequence LIMIT 2001').fetchall()
    if len(rows)>1000 or len(events)>2000: raise PortfolioError('simulation_reservation_history_limit')
    replay={}
    for identifier,action in events:
        if action=='reserve' and identifier not in replay: replay[identifier]='active'
        elif action=='release' and replay.get(identifier)=='active': replay[identifier]='released'
        else: raise PortfolioError('simulation_reservation_audit_mismatch')
    if set(replay)!={r[0] for r in rows}: raise PortfolioError('simulation_reservation_audit_mismatch')
    held=[]
    for identifier,payload,digest,status in rows:
        try:data=json.loads(payload)
        except (ValueError,TypeError):raise PortfolioError('simulation_reservation_audit_mismatch') from None
        total=validate_request(data)
        if data['id']!=identifier or hashlib.sha256(canonical(data)).hexdigest()!=digest or replay[identifier]!=status:
            raise PortfolioError('simulation_reservation_audit_mismatch')
        if status=='active':held.append({'id':identifier,'symbol':data['symbol'],'total_usd':str(total)})
    return held


class Reservations:
    def __init__(self,ledger):
        self.ledger,self.db=ledger,ledger.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS simulation_reservations (
            id TEXT PRIMARY KEY,payload TEXT NOT NULL,digest TEXT NOT NULL,status TEXT NOT NULL,
            policy_digest TEXT NOT NULL,ledger_revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS simulation_reservation_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,reservation_id TEXT NOT NULL,
            action TEXT NOT NULL,created REAL NOT NULL);
        ''')

    def reserve(self,data,policy,allocation):
        total=validate_request(data);settings=allocation.document()
        digest=hashlib.sha256(canonical(data)).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            policy.assert_current();active_holds(self.db)
            old=self.db.execute('SELECT digest,status,policy_digest FROM simulation_reservations WHERE id=?',(data['id'],)).fetchone()
            if old:
                if old[0]!=digest:raise PortfolioError('conflicting_reservation_id')
                if old[1]=='active' and old[2]!=policy.digest:raise PortfolioError('active_reservation_policy_changed')
                self.db.rollback()
                return {'status':'already_'+old[1],'id':data['id'],'execution_authorized':False,'broker_funds_reserved':False}
            if self.db.execute('SELECT 1 FROM simulation_reservations WHERE status=? AND policy_digest!=?',('active',policy.digest)).fetchone():
                raise PortfolioError('active_reservation_policy_changed')
            snapshot=self.ledger.snapshot()
            reasons=allocation_reasons(snapshot,[{'symbol':data['symbol'],'allocation_usd':str(total)}],policy)
            if reasons:raise PortfolioError(reasons[0])
            committed=Decimal(snapshot['simulation_planning_reserved_usd'])
            costs=Decimal(snapshot['api_expense_estimate_or_reserved_usd'])
            cap,buffer=Decimal(settings['capital_usd']),Decimal(settings['fee_reserve_usd'])
            gross=Decimal(snapshot['gross_risk_exposure_usd'])
            if gross+committed+total+costs+buffer>cap:
                raise PortfolioError('simulation_allocation_cap_exceeded')
            if Decimal(snapshot['available_cash_after_api_estimate_usd'])-total-buffer<amount(policy.document()['min_cash_reserve_usd']):
                raise PortfolioError('simulation_fee_buffer_or_cash_reserve_breached')
            self.db.execute('INSERT INTO simulation_reservations VALUES(?,?,?,?,?,?)',
                            (data['id'],json.dumps(data,sort_keys=True),digest,'active',policy.digest,snapshot['revision']))
            self.db.execute('INSERT INTO simulation_reservation_events(reservation_id,action,created) VALUES(?,?,?)',
                            (data['id'],'reserve',time.time()))
            policy.assert_current();self.ledger.assert_revision(snapshot['revision'])
            self.db.execute('UPDATE portfolio_state SET revision=revision+1 WHERE id=1')
            active_holds(self.db);self.db.commit()
            return {'status':'simulation_planning_reserved','id':data['id'],'execution_authorized':False,
                    'broker_funds_reserved':False,'ledger_revision':snapshot['revision']+1}
        except Exception:self.db.rollback();raise

    def release(self,identifier,policy):
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',identifier):
            raise PortfolioError('invalid_reservation_id')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            policy.assert_current();active_holds(self.db)
            row=self.db.execute('SELECT status FROM simulation_reservations WHERE id=?',(identifier,)).fetchone()
            if not row:raise PortfolioError('unknown_simulation_reservation')
            if row[0]=='active':
                self.db.execute('UPDATE simulation_reservations SET status=? WHERE id=?',('released',identifier))
                self.db.execute('INSERT INTO simulation_reservation_events(reservation_id,action,created) VALUES(?,?,?)',
                                (identifier,'release',time.time()))
                self.db.execute('UPDATE portfolio_state SET revision=revision+1 WHERE id=1')
            policy.assert_current();active_holds(self.db);self.db.commit()
            return {'status':'simulation_planning_released','id':identifier,'execution_authorized':False,'broker_funds_reserved':False}
        except Exception:self.db.rollback();raise

    def reserve_broker(self,*args,**kwargs):
        raise PermissionError('Broker reservations and execution are unavailable')
