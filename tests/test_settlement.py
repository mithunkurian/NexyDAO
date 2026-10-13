import json
import unittest
from unittest.mock import patch

from test_ibkr import Socket,frame
import test_reconciliation as fixtures
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.settlement import collect_settlement,save_settlement


class SettlementTests(unittest.TestCase):
    setUp=fixtures.ReconciliationTests.setUp

    def session(self,rows=None,end=True,account='DU123'):
        rows=frame(63,1,9103,account,'SettledCash','1000000','SEK') if rows is None else rows
        return Socket(frame(178,'time')+frame(15,1,account)+rows+(frame(64,1,9103) if end else b''))

    def collect(self,**kwargs):
        return collect_settlement(self.config,lambda *a,**k:self.session(**kwargs),lambda:self.now)

    def test_fixed_query_cancel_and_native_aggregate_scope(self):
        sock=self.session()
        payload=collect_settlement(self.config,lambda *a,**k:sock,lambda:self.now)
        self.assertEqual(sock.sent[3],frame(62,1,9103,'All','SettledCash'))
        self.assertEqual(sock.sent[4],frame(63,1,9103))
        self.assertEqual(payload['scope'],'account_summary_aggregate')
        self.assertFalse(payload['per_currency_spendable_cash_verified'])
        self.assertTrue(sock.closed)

    def test_even_usd_label_cannot_certify_currency_ledger(self):
        payload=self.collect(rows=frame(63,1,9103,'DU123','SettledCash','1000000','USD'))
        self.assertFalse(payload['per_currency_spendable_cash_verified'])
        with patch('nexydao.settlement.collect_settlement',return_value=payload):
            report=save_settlement(self.config,self.key,self.path)
        self.assertFalse(report['funding_authorized'])
        self.assertNotIn('1000000',json.dumps(report))
        self.assertNotIn('DU123',json.dumps(report))

    def test_pin_layout_request_tag_and_value_fail(self):
        with patch('socket.create_connection') as connect:
            with self.assertRaises(ProbeError):collect_settlement(BrokerConfig(),connect)
            connect.assert_not_called()
        for fields in ((63,1,9103,'DU999','SettledCash','1','USD'),
                       (63,1,9104,'DU123','SettledCash','1','USD'),
                       (63,1,9103,'DU123','BuyingPower','1','USD'),
                       (63,1,9103,'DU123','SettledCash','NaN','USD')):
            with self.assertRaises(ProbeError):self.collect(rows=frame(*fields))

    def test_end_duplicates_empty_and_account_change_fail(self):
        row=frame(63,1,9103,'DU123','SettledCash','1','USD')
        for kwargs in ({'end':False},{'rows':b''},{'rows':row*2},
                       {'rows':row+frame(15,1,'DU999')},{'rows':frame(64,1,9104)}):
            with self.assertRaises(ProbeError):self.collect(**kwargs)

    def test_failed_collection_preserves_existing_evidence(self):
        self.path.write_text('existing')
        with patch('nexydao.settlement.collect_settlement',side_effect=ProbeError('broker_disconnected')):
            with self.assertRaises(ProbeError):save_settlement(self.config,self.key,self.path)
        self.assertEqual(self.path.read_text(),'existing')
