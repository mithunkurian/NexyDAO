import copy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_ibkr import Socket,frame
import test_allocation as allocation_fixtures
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.orders import collect_orders,validate_orders
from nexydao.market import canonical
from nexydao.order_visibility import (DOMAIN,DETAIL_FIELDS,OrderReceiptConfig,open_order_core,order_status,
    typed_order_report,save_typed_orders,load_typed_orders,typed_orders_from_bytes)
from nexydao import research_signatures as signatures
from nexydao.allocation import AllocationConfig,evaluate_allocation,record_allocation_review
from nexydao.reconciliation import reconcile_state


def core(account='DU123',**changes):
    # Only the documented stable prefix is decoded. Synthetic advanced fields
    # deliberately demonstrate that no full openOrder layout is claimed.
    fields=['5','10','123','TEST','STK','','0','','','SMART','USD','TEST','TEST',
            'BUY','2','LMT','100','','DAY','',account,'O','0','private order reference','91','20',
            'opaque advanced field','opaque vendor text']
    for index,value in changes.items():fields[int(index)]=str(value)
    return fields


def status(**changes):
    fields=['3','10','Submitted','0','2','0','20','0','0','91','private held reason','0']
    for index,value in changes.items():fields[int(index)]=str(value)
    return fields


def collect(events=None,now=None):
    now=time.time() if now is None else now
    if events is None:events=frame(*core())+frame(*status())
    sock=Socket(frame(178,'time')+frame(15,1,'DU123')+events+frame(53,1))
    return collect_orders(BrokerConfig(expected_account='DU123'),lambda *a,**k:sock,lambda:now,typed=True)


class TypedOrderTests(unittest.TestCase):
    def test_stable_prefix_and_status_link_without_full_layout_or_reservation_claims(self):
        payload=collect();validate_orders(payload,'DU123')
        self.assertEqual(payload['schema_version'],2)
        self.assertTrue(payload['status_links_complete'])
        self.assertEqual(payload['order_cores'][0]['contract_id'],123)
        self.assertEqual(payload['order_cores'][0]['limit_price'],'100')
        self.assertIsNone(payload['order_cores'][0]['auxiliary_price'])
        self.assertEqual(payload['order_statuses'][0]['remaining_quantity'],'2')
        self.assertFalse(payload['complete_order_layout_verified'])
        self.assertFalse(payload['reservation_amounts_verified'])
        self.assertNotIn('private',json.dumps(payload));self.assertNotIn('opaque',json.dumps(payload))
        self.assertNotIn('DU123',json.dumps(payload))

    def test_reordered_and_duplicate_callbacks_do_not_become_multiple_orders(self):
        payload=collect(frame(*status())+frame(*core())+frame(*status())+frame(*core()))
        report=typed_order_report(payload)
        self.assertTrue(report['status_links_complete'])
        self.assertEqual(report['open_order_callback_count'],2)
        self.assertEqual(report['status_callback_count'],2)
        self.assertEqual(report['distinct_observed_order_identity_count'],1)
        self.assertFalse(report['order_versions_changed_observed'])

    def test_same_order_id_across_clients_uses_exact_client_and_positive_permanent_id(self):
        payload=collect(frame(*core())+frame(*core(**{'24':'92','25':'21'}))+
                        frame(*status())+frame(*status(**{'9':'92','6':'21'})))
        self.assertTrue(payload['status_links_complete']);self.assertFalse(payload['ambiguous_order_identity_observed'])
        self.assertEqual(typed_order_report(payload)['distinct_observed_order_identity_count'],2)

    def test_status_only_unmatched_zero_or_conflicting_identity_never_implies_account_match(self):
        for events in (frame(*status()),frame(*core())+frame(*status(**{'9':'92'})),
                       frame(*core(**{'25':'0'}))+frame(*status(**{'6':'0'})),
                       frame(*core())+frame(*status(**{'6':'21'}))):
            with self.subTest(events=events[:15]):
                payload=collect(events)
                self.assertFalse(payload['status_links_complete']);self.assertEqual(payload['unmatched_status_count'],1)
        self.assertFalse(collect(frame(*core()))['status_links_complete'])

    def test_versions_quantity_disagreement_and_identity_aliases_are_flagged(self):
        changed=collect(frame(*core())+frame(*core(**{'14':'3'}))+frame(*status()))
        self.assertTrue(changed['order_versions_changed_observed']);self.assertTrue(changed['quantity_disagreement_observed'])
        for extra in (core(**{'25':'21'}),core(**{'24':'92'})):
            self.assertTrue(collect(frame(*core())+frame(*extra)+frame(*status()))['ambiguous_order_identity_observed'])

    def test_account_layout_stock_metadata_and_numeric_restrictions(self):
        for fields in (core(account='DU999'),core(account='U123'),core()[:26],core()+['']*1000):
            with self.assertRaises(ProbeError):open_order_core(fields,'DU123',0)
        for index,value in ((2,'0'),(4,'OPT'),(6,'10'),(13,'SSHORT'),(14,'0'),(16,'NaN'),(24,'-1')):
            with self.subTest(index=index),self.assertRaises(ProbeError):open_order_core(core(**{str(index):value}),'DU123',0)
        for fields in (status()[:-1],status(**{'3':'-1'}),status(**{'4':'NaN'})):
            with self.assertRaises(ProbeError):order_status(fields,0)
        self.assertIsNone(open_order_core(core(**{'16':'1.7976931348623157e+308'}),'DU123',0)['limit_price'])

    def test_every_activity_digest_is_bound_to_one_typed_row(self):
        original=collect()
        changes=[]
        missing=copy.deepcopy(original);missing['order_statuses']=[];changes.append(missing)
        duplicate=copy.deepcopy(original);duplicate['order_statuses'][0]['activity_index']=0;changes.append(duplicate)
        changed=copy.deepcopy(original);changed['order_cores'][0]['raw_frame_sha256']='a'*64;changes.append(changed)
        invalid=copy.deepcopy(original);invalid['order_cores'][0]['contract_id']=True;changes.append(invalid)
        for payload in changes:
            with self.assertRaises(ProbeError):validate_orders(payload,'DU123')

    def test_derived_link_flags_scope_and_expiry_cannot_be_relaxed(self):
        original=collect()
        for field,value in (('complete_order_layout_verified',True),('status_links_complete',False),
                            ('unmatched_status_count',True),('quantity_disagreement_observed',True),
                            ('manual_order_coverage_verified',True),('typed_scope','full_account_orders')):
            with self.subTest(field=field),self.assertRaises(ProbeError):validate_orders({**original,field:value},'DU123')
        with self.assertRaises(ProbeError):validate_orders(original,'DU123',original['expires_at'])

    def test_empty_query_and_legacy_opaque_mode_keep_their_limited_scope(self):
        payload=collect(b'')
        self.assertTrue(payload['status_links_complete']);self.assertFalse(payload['manual_order_coverage_verified'])
        sock=Socket(frame(178,'time')+frame(15,1,'DU123')+frame(5,'opaque')+frame(53,1))
        legacy=collect_orders(BrokerConfig(expected_account='DU123'),lambda *a,**k:sock)
        self.assertEqual(legacy['schema_version'],1)
        with self.assertRaises(ProbeError):collect(frame(5,'opaque'))

    def test_typed_row_bounds_and_existing_nonbinding_wire_request(self):
        with self.assertRaises(ProbeError):collect(frame(*status())*101)
        sock=Socket(frame(178,'time')+frame(15,1,'DU123')+frame(53,1))
        collect_orders(BrokerConfig(expected_account='DU123'),lambda *a,**k:sock,typed=True)
        self.assertEqual(len(sock.sent),4);self.assertEqual(sock.sent[3],frame(16,1));self.assertTrue(sock.closed)


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class TypedOrderReceiptTests(unittest.TestCase):
    def setUp(self):
        data=Path(__file__).resolve().parents[1]/'data';data.mkdir(exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=data);self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.private=self.root/'fixture.pem';self.public=self.root/'fixture.der';self.path=self.root/'orders.json'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644);self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.settings=OrderReceiptConfig(self.public,self.pin,self.private);self.config=BrokerConfig(expected_account='DU123')

    def signed(self,payload=None,domain=DOMAIN):
        return json.dumps(signatures.sign(payload or collect(),self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=domain)).encode()

    def test_public_only_verification_and_cross_domain_no_hmac_or_legacy_fallback(self):
        from nexydao.executions import DOMAIN as EXECUTION_DOMAIN
        from nexydao.paper_permits import DOMAIN as SHADOW_DOMAIN
        raw=self.signed();wrong=[self.signed(domain=domain) for domain in (signatures.DOMAIN,EXECUTION_DOMAIN,SHADOW_DOMAIN)]
        legacy=collect();legacy={key:value for key,value in legacy.items() if key not in DETAIL_FIELDS}
        legacy['schema_version']=1;legacy_raw=self.signed(legacy)
        self.private.unlink();consumer=replace(self.settings,signing_path=None)
        self.assertTrue(typed_orders_from_bytes(raw,self.config,consumer)['status_links_complete'])
        for body in (*wrong,legacy_raw,b'{"payload":{},"signature":"hmac"}'):
            with self.assertRaises(ProbeError):typed_orders_from_bytes(body,self.config,consumer)

    def test_invalid_signature_duplicate_json_bounds_account_and_expiry(self):
        raw=self.signed();receipt=json.loads(raw)
        for changed in ({**receipt,'signature':'00'*64},{**receipt,'key_sha256':'a'*64},
                        {**receipt,'algorithm':'hmac-sha256'}):
            with self.assertRaises(ProbeError):typed_orders_from_bytes(json.dumps(changed).encode(),self.config,self.settings)
        for body in (raw.replace(b'"schema_version": 2',b'"schema_version": 2,"schema_version": 2'),b'x'*65537,b'NaN'):
            with self.assertRaises(ProbeError):typed_orders_from_bytes(body,self.config,self.settings)
        with self.assertRaises(ProbeError):typed_orders_from_bytes(raw,BrokerConfig(expected_account='DU999'),self.settings)
        with self.assertRaises(ProbeError):typed_orders_from_bytes(raw,self.config,self.settings,json.loads(raw)['payload']['expires_at'])

    def test_save_load_and_signer_or_collection_failure_preserve_prior_receipt(self):
        payload=collect()
        with patch('nexydao.order_visibility.collect_orders',return_value=payload) as collector:
            save_typed_orders(self.config,self.settings,self.path)
            collector.assert_called_once_with(self.config,typed=True)
        self.assertEqual(load_typed_orders(self.config,replace(self.settings,signing_path=None),self.path),payload)
        previous=self.path.read_bytes()
        with patch('nexydao.order_visibility.collect_orders') as collector:
            with self.assertRaises(ProbeError):save_typed_orders(self.config,replace(self.settings,signing_path=None),self.path)
            collector.assert_not_called()
        with patch('nexydao.order_visibility.collect_orders',side_effect=ProbeError('fixture_failure')):
            with self.assertRaises(ProbeError):save_typed_orders(self.config,self.settings,self.path)
        with patch('nexydao.order_visibility.collect_orders',return_value=payload), \
                patch.object(signatures,'sign',side_effect=signatures.ReceiptSignatureError('fixture_failure')):
            with self.assertRaises(ProbeError):save_typed_orders(self.config,self.settings,self.path)
        self.assertEqual(self.path.read_bytes(),previous)

    def test_cli_public_report_has_no_provider_db_broker_or_hmac_key_access(self):
        from nexydao.cli import main
        self.path.write_bytes(self.signed());self.path.chmod(0o600)
        output=io.StringIO()
        with patch('sys.argv',['nexydao','broker-orders-report']), \
                patch.dict('os.environ',{'NEXYDAO_TYPED_ORDERS_SNAPSHOT':str(self.path)}), \
                patch.object(OrderReceiptConfig,'from_env',return_value=replace(self.settings,signing_path=None)), \
                patch.object(BrokerConfig,'from_env',return_value=self.config), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('socket.create_connection') as connect,patch('nexydao.market.read_key') as key,patch('sys.stdout',output):
            main()
        for operation in (store,provider,connect,key):operation.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['execution_authorized'])

    def test_cli_collection_fails_before_query_when_host_guard_unverified(self):
        from nexydao.cli import main
        with patch('sys.argv',['nexydao','broker-orders-typed']), \
                patch.object(OrderReceiptConfig,'from_env',return_value=self.settings), \
                patch('nexydao.access.run_access_check',return_value={'non_loopback_tcp_ingress_denied':False}), \
                patch('nexydao.order_visibility.save_typed_orders') as save,patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        save.assert_not_called()


class TypedAllocationTests(unittest.TestCase):
    setUp=allocation_fixtures.AllocationTests.setUp

    def test_typed_activity_stays_zero_and_diagnostic_links_are_persisted(self):
        orders=collect(now=self.orders['started_at'])
        result=record_allocation_review(self.payload,self.config,self.ledger,self.policy,AllocationConfig(),orders=orders)
        self.assertEqual(result['planning_ceiling_after_reserves_usd'],'0')
        self.assertTrue(result['typed_order_prefix_observed']);self.assertTrue(result['order_status_links_complete'])
        self.assertFalse(result['funding_authorized']);self.assertFalse(result['reservation_amounts_verified'])
        report=json.loads(self.store.db.execute('SELECT report FROM allocation_reviews').fetchone()[0])
        self.assertEqual(report['orders_payload_sha256'],hashlib.sha256(canonical(orders)).hexdigest())

    def test_unmatched_conflicting_quantities_and_changed_orders_add_blockers(self):
        for events,reason in ((frame(*status()),'order_status_identity_links_incomplete'),
                              (frame(*core())+frame(*status(**{'6':'21'})),'order_identity_ambiguity'),
                              (frame(*core())+frame(*status(**{'4':'3'})),'order_quantity_disagreement'),
                              (frame(*core())+frame(*core(**{'16':'101'}))+frame(*status()),'order_changed_during_query')):
            with self.subTest(reason=reason):
                result=evaluate_allocation(self.payload,self.config,self.ledger,self.policy,AllocationConfig(),
                                           orders=collect(events,self.orders['started_at']))
                self.assertIn(reason,result['blocking_reasons']);self.assertEqual(result['planning_ceiling_after_reserves_usd'],'0')

    def test_empty_typed_receipt_retains_manual_scope_funding_and_reservation_blocks(self):
        result=evaluate_allocation(self.payload,self.config,self.ledger,self.policy,AllocationConfig(),
                                   orders=collect(b'',self.orders['started_at']))
        self.assertFalse(result['manual_order_coverage_verified']);self.assertFalse(result['funding_authorized'])
        self.assertFalse(result['complete_order_layout_verified'])
        self.assertIn('manual_order_visibility_and_reservations_unverified',result['blocking_reasons'])

    def test_invalid_configured_typed_receipt_does_not_fall_back_to_legacy(self):
        from nexydao.cli import main
        with patch('sys.argv',['nexydao','allocation-check']), \
                patch.dict('os.environ',{'NEXYDAO_EVIDENCE_KEY_FILE':'unused','NEXYDAO_TYPED_ORDERS_SNAPSHOT':'missing',
                                         'NEXYDAO_ORDERS_SNAPSHOT':'legacy'}), \
                patch('nexydao.reconciliation.load_state',return_value=self.payload), \
                patch.object(OrderReceiptConfig,'from_env',return_value=object()), \
                patch('nexydao.order_visibility.load_typed_orders',side_effect=ProbeError('fixture_bad_receipt')), \
                patch('nexydao.orders.load_orders') as legacy,patch('nexydao.cli.Store'),patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        legacy.assert_not_called()

    def test_reconciliation_binds_fresh_typed_receipt_without_clearing_missing_gates(self):
        orders=collect(frame(*status()),self.orders['started_at'])
        result=reconcile_state(self.payload,self.config,self.ledger,orders=orders)
        self.assertTrue(result['typed_order_prefix_observed']);self.assertFalse(result['order_status_links_complete'])
        self.assertEqual(result['unmatched_order_status_count'],1)
        self.assertEqual(result['orders_payload_sha256'],hashlib.sha256(canonical(orders)).hexdigest())
        self.assertIn('open_orders_and_reservations',result['missing_checks'])
        for key in ('broker_reconciliation','broker_funding_verified','broker_balances_imported','observation_atomic','execution_authorized'):
            self.assertFalse(result[key])
        future=orders['expires_at'];fresh_state=copy.deepcopy(self.payload)
        fresh_state.update(started_at=future-1,received_at=future-1,expires_at=future+59)
        with self.assertRaisesRegex(ProbeError,'orders_expired'):
            reconcile_state(fresh_state,self.config,self.ledger,future,orders=orders)
