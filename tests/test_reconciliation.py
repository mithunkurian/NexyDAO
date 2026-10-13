import copy
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_ibkr import Socket, frame
from nexydao.ibkr import BrokerConfig, ProbeError
from nexydao.market import canonical
from nexydao.portfolio import Portfolio
from nexydao.store import Store
from nexydao.reconciliation import (SOURCE, collect_state, validate_state, state_message,
                                    save_state, load_state, reconcile_state)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'data'
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.key = self.root / 'key'
        self.key.write_bytes(b'x' * 32); self.key.chmod(0o600)
        self.path = self.root / 'state.json'
        self.config = BrokerConfig(expected_account='DU123')
        self.now = time.time()
        self.store = Store(self.root/'state.sqlite')
        self.addCleanup(self.store.close)
        self.ledger = Portfolio(self.store)

    def cash(self, tag='CashBalance', value='5000', currency='USD', account='DU123'):
        return frame(6,2,tag,value,currency,account)

    def holding(self, quantity='1', account='DU123', conid=123, kind='STK'):
        return frame(61,3,account,conid,'SPY',kind,'',0,'','','SMART','USD','SPY','SPY',quantity,'100')

    def session(self, account='DU123', cash=None, positions=b'', cash_end=True, position_end=True, late=b''):
        cash = self.cash('$LEDGER-CashBalance')+self.cash('$LEDGER-SettledCash') if cash is None else cash
        return Socket(frame(178,'time')+frame(15,1,account)+cash+
                      (frame(54,1,account) if cash_end else b'')+late+positions+
                      (frame(62,1) if position_end else b''))

    def payload(self, **kwargs):
        sock = self.session(**kwargs)
        return collect_state(self.config, lambda *a,**k:sock, lambda:self.now)

    def receipt(self, payload):
        self.path.write_text(json.dumps({'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}))

    def test_fixed_readonly_wire_and_cancellation(self):
        sock = self.session(positions=self.holding())
        result = collect_state(self.config,lambda *a,**k:sock,lambda:self.now)
        self.assertTrue(sock.closed)
        self.assertEqual(result['positions'][0]['contract_id'],123)
        self.assertEqual([s[4:].split(b'\0')[0] for s in sock.sent[1:]], [b'71',b'17',b'6',b'6',b'61',b'64'])
        self.assertEqual(sock.sent[3],frame(6,2,1,'DU123'))
        self.assertEqual(sock.sent[4],frame(6,2,0,'DU123'))
        for command in ('placeOrder','cancelOrder','global_cancel'):
            with self.assertRaises(PermissionError): state_message(command,self.config)

    def test_gateway_ledger_prefix_and_unparsed_settlement_schedule(self):
        payload=self.payload(cash=self.cash('$LEDGER-CashBalance')+self.cash('$LEDGER-TotalCashBalance')+
                             self.cash('SettledCashByDate','unsupported schedule'))
        self.assertEqual({r['tag'] for r in payload['cash']},{'CashBalance','TotalCashBalance'})
        result=reconcile_state(payload,self.config,self.ledger,self.now)
        self.assertTrue(result['settled_cash_schedule_unparsed'])
        self.assertFalse(result['usd_settled_cash_observed'])
        self.assertIn('per_currency_settled_cash',result['missing_checks'])
        self.assertEqual(payload['settlement_observations'],[{'currency':'USD','raw_value':'unsupported schedule'}])

    def test_duplicate_oversized_or_changed_schedule_fails(self):
        cash=self.cash()+self.cash('SettledCashByDate','schedule')
        for kwargs in ({'cash':cash+self.cash('SettledCashByDate','schedule')},
                       {'cash':self.cash()+self.cash('SettledCashByDate','x'*4097)},
                       {'cash':cash,'late':self.cash('SettledCashByDate','changed')}):
            with self.assertRaises(ProbeError):self.payload(**kwargs)

    def test_own_cancellation_notice_only_in_completed_unsubscribed_phase(self):
        notice=frame(4,2,-1,2100,'Account subscription cancelled')
        self.assertEqual(self.payload(late=notice)['positions'],[])
        self.assertEqual(self.payload(late=frame(4,2,-1,2100,'Account subscription cancelled',''))['positions'],[])
        for kwargs in ({'cash':notice+self.cash()},{'late':notice+notice},
                       {'late':frame(4,2,123,2100,'unrelated')},
                       {'late':frame(4,2,-1,2100,'Account subscription cancelled','nonempty rejection')}):
            with self.assertRaises(ProbeError): self.payload(**kwargs)

    def test_account_not_ready_fails_in_both_phases(self):
        not_ready=self.cash('AccountReady','false','')
        for kwargs in ({'cash':not_ready+self.cash()},{'late':not_ready}):
            with self.assertRaises(ProbeError): self.payload(**kwargs)

    def test_exact_pin_required_before_network(self):
        with patch('socket.create_connection') as connect:
            with self.assertRaises(ProbeError): collect_state(BrokerConfig(),connect)
            connect.assert_not_called()
        for account in ('U123','DU999','DU123,DU456'):
            sock=self.session(account=account)
            with self.assertRaises(ProbeError): collect_state(self.config,lambda *a,**k:sock)
            self.assertEqual(len(sock.sent),3)

    def test_account_changes_and_wrong_end_markers_fail(self):
        for cash in (self.cash(account='DU999'),frame(15,1,'U123'),self.cash()+frame(54,1,'DU999')):
            with self.assertRaises(ProbeError): self.payload(cash=cash)
        with self.assertRaises(ProbeError): self.payload(positions=self.holding(account='DU999'))

    def test_both_download_ends_required_even_when_positions_empty(self):
        for kwargs in ({'cash_end':False},{'position_end':False}):
            with self.assertRaises(ProbeError): self.payload(**kwargs)
        self.assertEqual(self.payload()['positions'],[])

    def test_duplicates_and_racing_cash_fail(self):
        for kwargs in ({'cash':self.cash()+self.cash()}, {'positions':self.holding()+self.holding()},
                       {'late':self.cash(value='4999')}):
            with self.assertRaises(ProbeError): self.payload(**kwargs)

    def test_base_aggregate_never_substitutes_for_usd(self):
        payload=self.payload(cash=self.cash(currency='BASE')+self.cash(currency='SEK')+self.cash('SettledCash',currency='SEK'))
        self.assertTrue(all(r['currency']!='BASE' for r in payload['cash']))
        result=reconcile_state(payload,self.config,self.ledger,self.now)
        self.assertFalse(result['usd_settled_cash_observed'])
        self.assertEqual(result['simulated_cash_comparison'],'USD_not_observed')

    def test_missing_settled_currency_not_synthesized(self):
        result=reconcile_state(self.payload(cash=self.cash()),self.config,self.ledger,self.now)
        self.assertFalse(result['per_currency_cash_pairs_complete'])
        self.assertFalse(result['broker_funding_verified'])

    def test_negative_cash_and_short_or_unsupported_position_reported(self):
        result=reconcile_state(self.payload(cash=self.cash(value='-1'),positions=self.holding(quantity='-1',kind='CFD')),
                               self.config,self.ledger,self.now)
        self.assertTrue(result['negative_currency_cash_observed'])
        self.assertTrue(result['short_position_observed'])
        self.assertTrue(result['unsupported_instrument_observed'])
        self.assertFalse(result['execution_authorized'])

    def test_no_import_even_if_cash_and_positions_match(self):
        before=self.ledger.snapshot()
        result=reconcile_state(self.payload(),self.config,self.ledger,self.now)
        self.assertTrue(result['positions_match_simulation'])
        self.assertEqual(result['simulated_cash_comparison'],'match')
        self.assertFalse(result['broker_reconciliation'])
        self.assertFalse(result['broker_balances_imported'])
        self.assertFalse(result['broker_funding_verified'])
        self.assertEqual(self.ledger.snapshot(),before)

    def test_unknown_contract_cannot_match_by_symbol(self):
        self.ledger.fill({'id':'fixture','side':'buy','symbol':'SPY','quantity':'1','price':'100','fee':'0','currency':'USD','asset_type':'STK'})
        result=reconcile_state(self.payload(positions=self.holding()),self.config,self.ledger,self.now)
        self.assertFalse(result['simulated_contract_identity_complete'])
        self.assertFalse(result['positions_match_simulation'])
        self.store.db.execute('UPDATE simulated_positions SET con_id=123'); self.store.db.commit()
        self.assertTrue(reconcile_state(self.payload(positions=self.holding()),self.config,self.ledger,self.now)['positions_match_simulation'])

    def test_bare_currency_label_is_not_verified_ledger_cash(self):
        payload=self.payload(cash=self.cash()+self.cash('SettledCash'))
        self.assertFalse(payload['per_currency_scope_verified'])
        result=reconcile_state(payload,self.config,self.ledger,self.now)
        self.assertFalse(result['usd_settled_cash_observed'])
        self.assertIn('per_currency_cash_scope',result['missing_checks'])

    def test_legacy_receipts_remain_readable_but_cannot_prove_scope(self):
        for version in (1,2):
            payload=self.payload();payload['schema_version']=version
            del payload['per_currency_scope_verified']
            if version==1:del payload['settlement_observations']
            validate_state(payload,'DU123',self.now)
            self.assertFalse(reconcile_state(payload,self.config,self.ledger,self.now)['usd_settled_cash_observed'])

    def test_aggregate_appearing_late_invalidates_ledger_scope(self):
        with self.assertRaises(ProbeError):self.payload(late=self.cash())

    def test_scope_flag_requires_boolean(self):
        payload=self.payload();payload['per_currency_scope_verified']=1
        with self.assertRaises(ProbeError):validate_state(payload,'DU123',self.now)

    def test_wrong_quantity_and_extra_positions_mismatch(self):
        result=reconcile_state(self.payload(positions=self.holding(quantity='2')),self.config,self.ledger,self.now)
        self.assertFalse(result['positions_match_simulation'])

    def test_malformed_and_nonfinite_values_fail(self):
        for value in ('NaN','Infinity','1e99','1'*100):
            with self.assertRaises(ProbeError): self.payload(cash=self.cash(value=value))
            with self.assertRaises(ProbeError): self.payload(positions=self.holding(quantity=value))

    def test_receipt_roundtrip_tamper_wrong_pin_and_size(self):
        payload=self.payload();self.receipt(payload)
        self.assertEqual(load_state(self.config,self.key,self.path),payload)
        with self.assertRaises(ProbeError): load_state(BrokerConfig(expected_account='DU999'),self.key,self.path)
        payload['cash'][0]['value']='9999'
        receipt=json.loads(self.path.read_text());receipt['payload']=payload;self.path.write_text(json.dumps(receipt))
        with self.assertRaises(ProbeError): load_state(self.config,self.key,self.path)
        self.path.write_bytes(b'x'*131073)
        with self.assertRaises(ProbeError): load_state(self.config,self.key,self.path)

    def test_time_and_completion_claims_fail_closed(self):
        for field,value in (('started_at',True),('received_at',float('nan')),('cash_download_complete',1),
                            ('positions_download_complete',False),('expires_at',self.now+61)):
            payload=self.payload();payload[field]=value
            with self.assertRaises(ProbeError): validate_state(payload,'DU123',self.now)
        with self.assertRaises(ProbeError): validate_state(self.payload(),'DU123',self.now+60)
        with self.assertRaises(ProbeError): validate_state(self.payload(),'DU123',self.now-1)

    def test_conflicting_and_duplicate_json_and_rows_rejected(self):
        payload=self.payload();payload['cash'].append(copy.deepcopy(payload['cash'][0]))
        with self.assertRaises(ProbeError): validate_state(payload,'DU123',self.now)
        self.path.write_text('{"payload":{},"payload":{},"signature":"x"}')
        with self.assertRaises(ProbeError): load_state(self.config,self.key,self.path)

    def test_failed_collection_preserves_last_receipt(self):
        self.path.write_text('previous')
        with patch('nexydao.reconciliation.collect_state',side_effect=ProbeError('broker_timeout')):
            with self.assertRaises(ProbeError): save_state(self.config,self.key,self.path)
        self.assertEqual(self.path.read_text(),'previous')

    def test_oversized_signed_schedule_receipt_preserves_last_file(self):
        payload=self.payload()
        payload['settled_cash_schedule_unparsed']=True
        payload['settlement_observations']=[{'currency':f'A{chr(65+i//26)}{chr(65+i%26)}','raw_value':'x'*4096}
                                             for i in range(40)]
        validate_state(payload,'DU123',self.now)
        self.path.write_text('previous')
        with patch('nexydao.reconciliation.collect_state',return_value=payload):
            with self.assertRaises(ProbeError):save_state(self.config,self.key,self.path)
        self.assertEqual(self.path.read_text(),'previous')
