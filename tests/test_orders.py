import copy
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch

from test_ibkr import Socket, frame
import test_reconciliation as fixtures
from nexydao.ibkr import BrokerConfig, ProbeError
from nexydao.market import canonical
from nexydao.orders import collect_orders, validate_orders, query_message, save_orders, load_orders


class OrderTests(unittest.TestCase):
    setUp = fixtures.ReconciliationTests.setUp

    def session(self, account='DU123', events=b'', end=True):
        return Socket(frame(178,'time')+frame(15,1,account)+events+(frame(53,1) if end else b''))

    def payload(self, **kwargs):
        return collect_orders(self.config,lambda *a,**k:self.session(**kwargs),lambda:self.now)

    def write_receipt(self, payload):
        self.path.write_text(json.dumps({'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}))

    def test_one_nonbinding_request_and_empty_scope_is_not_full_reconciliation(self):
        sock=self.session()
        payload=collect_orders(self.config,lambda *a,**k:sock,lambda:self.now)
        self.assertEqual(sock.sent[3],frame(16,1))
        self.assertEqual(len(sock.sent),4)
        self.assertTrue(sock.closed)
        self.assertTrue(payload['query_complete'])
        self.assertFalse(payload['manual_order_coverage_verified'])
        self.assertFalse(payload['reservation_amounts_verified'])
        self.assertEqual(payload['activity_frame_digests'],[])
        for command in ('placeOrder','cancelOrder','reqOpenOrders','reqAutoOpenOrders','global_cancel'):
            with self.assertRaises(PermissionError):query_message(command)

    def test_no_query_before_exact_pin_and_no_client_zero(self):
        with patch('socket.create_connection') as connect:
            with self.assertRaises(ProbeError):collect_orders(BrokerConfig(),connect)
            connect.assert_not_called()
        for account in ('DU999','U123','DU123,DU999'):
            sock=self.session(account)
            with self.assertRaises(ProbeError):collect_orders(self.config,lambda *a,**k:sock)
            self.assertEqual(len(sock.sent),3)
        with self.assertRaises(ValueError):BrokerConfig(expected_account='DU123',client_id=0)

    def test_opaque_order_and_status_events_never_publish_vendor_text(self):
        payload=self.payload(events=frame(5,'secret vendor order')+frame(3,'secret status'))
        self.assertEqual(len(payload['activity_frame_digests']),2)
        self.assertNotIn('secret',json.dumps(payload))
        self.assertNotIn('order_count',payload)

    def test_missing_end_changed_account_and_binding_callback_fail(self):
        for kwargs in ({'end':False},{'events':frame(15,1,'DU999')},
                       {'events':frame(100,'binding')},{'events':frame(53,2)}):
            with self.assertRaises(ProbeError):self.payload(**kwargs)

    def test_end_before_identity_and_activity_bound_fail(self):
        sock=Socket(frame(178,'time')+frame(53,1)+frame(15,1,'DU123')+frame(53,1))
        with self.assertRaises(ProbeError):collect_orders(self.config,lambda *a,**k:sock)
        with self.assertRaises(ProbeError):self.payload(events=frame(5,'event')*201)

    def test_errors_fail_without_broker_text(self):
        with self.assertRaises(ProbeError) as error:self.payload(events=frame(4,2,-1,321,'secret'))
        self.assertNotIn('secret',str(error.exception))

    def test_wrong_scope_forged_completion_and_time_rejected(self):
        valid=self.payload()
        for field,value in (('query_complete',False),('manual_order_coverage_verified',True),
                            ('reservation_amounts_verified',True),('scope','all_account_orders'),
                            ('account_sha256','fake'),('started_at',float('nan')),('schema_version',True)):
            payload=copy.deepcopy(valid);payload[field]=value
            with self.assertRaises(ProbeError):validate_orders(payload,'DU123',self.now)
        with self.assertRaises(ProbeError):validate_orders(valid,'DU123',self.now+60)

    def test_signed_roundtrip_tamper_and_size_limit(self):
        self.write_receipt(self.payload())
        self.assertTrue(load_orders(self.config,self.key,self.path)['query_complete'])
        self.write_receipt(self.payload());receipt=json.loads(self.path.read_text())
        receipt['payload']['activity_frame_digests']=['a'*64]
        self.path.write_text(json.dumps(receipt))
        with self.assertRaises(ProbeError):load_orders(self.config,self.key,self.path)
        self.path.write_bytes(b'x'*65537)
        with self.assertRaises(ProbeError):load_orders(self.config,self.key,self.path)

    def test_duplicate_json_keys_are_rejected_even_with_signed_payload(self):
        self.write_receipt(self.payload())
        self.path.write_text(self.path.read_text().replace('"schema_version": 1','"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(ProbeError):load_orders(self.config,self.key,self.path)

    def test_failed_collection_preserves_receipt(self):
        self.path.write_text('existing')
        with patch('nexydao.orders.collect_orders',side_effect=ProbeError('failure')):
            with self.assertRaises(ProbeError):save_orders(self.config,self.key,self.path)
        self.assertEqual(self.path.read_text(),'existing')
