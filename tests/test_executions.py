import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_ibkr import Socket,frame
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.executions import (REQUEST_ID,DOMAIN,ExecutionReceiptConfig,collect_executions,
    request_message,validate_executions,execution_frame,commission_frame,save_executions,
    load_executions,executions_from_bytes,execution_report)
from nexydao import research_signatures as signatures


def execution(identifier='0001.abcd.01.01',account='DU123',**changes):
    fields=['11',str(REQUEST_ID),'10','123','TEST','STK','','0','','','SMART','USD','TEST','TEST',
            identifier,'20261105  10:00:00',account,'NYSE','BOT','2','100','20','91','0',
            '2','100','private order reference','','0','','1','0']
    for index,value in changes.items():fields[int(index)]=str(value)
    return fields


def commission(identifier='0001.abcd.01.01',value='1',currency='USD'):
    return ['59','1',identifier,value,currency,'1.7976931348623157e+308','1.7976931348623157e+308','0']


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.config=BrokerConfig(expected_account='DU123');self.now=time.time()

    def session(self,events=None,account='DU123',end=True):
        events=events if events is not None else frame(*execution())+frame(*commission())
        return Socket(frame(178,'time')+frame(15,1,account)+events+(frame(55,1,REQUEST_ID) if end else b''))

    def collect(self,events=None,**kwargs):
        return collect_executions(self.config,lambda *a,**k:self.session(events,**kwargs),lambda:self.now)

    def test_exact_read_only_request_after_pin_no_order_or_binding_messages(self):
        sock=self.session()
        result=collect_executions(self.config,lambda *a,**k:sock,lambda:self.now)
        self.assertEqual(sock.sent[3],frame(7,3,REQUEST_ID,0,'DU123','','','','',''))
        self.assertEqual(len(sock.sent),4);self.assertTrue(sock.closed)
        self.assertEqual(result['executions'][0]['commission'],'1')
        self.assertFalse(result['broker_reconciliation'])
        self.assertNotIn('private',json.dumps(result));self.assertNotIn('DU123',json.dumps(result))
        for command in ('placeOrder','cancelOrder','reqOpenOrders','reqAutoOpenOrders','global_cancel'):
            with self.assertRaises(PermissionError):request_message(self.config,command)

    def test_missing_pin_wrong_live_ambiguous_or_changed_account_fails(self):
        with patch('socket.create_connection') as connect:
            with self.assertRaises(ProbeError):collect_executions(BrokerConfig(),connect)
            connect.assert_not_called()
        for account in ('DU999','U123','DU123,DU999'):
            sock=self.session(account=account)
            with self.assertRaises(ProbeError):collect_executions(self.config,lambda *a,**k:sock)
            self.assertEqual(len(sock.sent),3)
        for events in (frame(*execution(account='DU999')),frame(15,1,'DU999')):
            with self.assertRaises(ProbeError):self.collect(events)

    def test_fee_before_fill_and_after_execution_end_are_linked(self):
        early=self.collect(frame(*commission())+frame(*execution()))
        late=self.collect(frame(*execution())+frame(55,1,REQUEST_ID)+frame(*commission()),end=False)
        self.assertEqual(early['executions'],late['executions'])

    def test_empty_query_is_not_manual_transfer_or_account_coverage(self):
        result=self.collect(b'');self.assertEqual(result['executions'],[])
        report=execution_report(result)
        for field in ('manual_order_coverage_verified','transfer_coverage_verified','broker_reconciliation','ledger_imported','execution_authorized'):
            self.assertFalse(report[field])

    def test_missing_or_unmatched_fee_duplicate_fill_or_fee_and_end_fail(self):
        ex=frame(*execution());fee=frame(*commission())
        for events in (ex,fee,ex+ex+fee,ex+fee+fee,ex+frame(*commission('other.id.01.01')),
                       frame(55,1,REQUEST_ID+1),frame(55,2,REQUEST_ID),
                       ex+frame(55,1,REQUEST_ID)+ex+fee):
            with self.subTest(events=events[:15]),self.assertRaises(ProbeError):self.collect(events)
        with self.assertRaises(ProbeError):self.collect(ex+fee,end=False)

    def test_corrections_pending_revision_and_fee_currency_mismatch_are_preserved(self):
        rows=(frame(*execution())+frame(*commission())+
              frame(*execution('0001.abcd.01.02',**{'31':'1'}))+frame(*commission('0001.abcd.01.02','2','SEK')))
        payload=self.collect(rows)
        self.assertEqual(len(payload['executions']),2)
        for field in ('correction_observed','pending_price_revision_observed','fee_currency_mismatch_observed'):
            self.assertTrue(payload[field])
        self.assertFalse(payload['broker_reconciliation'])

    def test_partial_fills_remain_distinct_and_negative_rebates_are_not_imported(self):
        rows=(frame(*execution())+frame(*commission(value='-0.5'))+
              frame(*execution('0001.abcd.02.01',**{'19':'1','24':'3'}))+frame(*commission('0001.abcd.02.01')))
        payload=self.collect(rows)
        self.assertFalse(payload['correction_observed']);self.assertEqual(len(payload['executions']),2)
        self.assertIn('-0.5',[row['commission'] for row in payload['executions']])

    def test_unsupported_contract_layout_metadata_and_numeric_values_fail(self):
        for index,value in ((1,'-1'),(3,'0'),(5,'OPT'),(7,'10'),(9,'100'),(18,'BUY'),(19,'0'),
                            (20,'NaN'),(24,'1'),(27,'rule'),(29,'model'),(31,'true'),(15,'invalid')):
            with self.subTest(index=index),self.assertRaises(ProbeError):
                execution_frame(execution(**{str(index):value}),'DU123')
        with self.assertRaises(ProbeError):execution_frame(execution()[:-1],'DU123')
        for fields in (commission(value='NaN'),commission(currency='BASE'),commission()[:-1]):
            with self.assertRaises(ProbeError):commission_frame(fields)

    def test_row_and_frame_bounds_and_vendor_errors_fail_without_text(self):
        with self.assertRaisesRegex(ProbeError,'excess_execution'):
            self.collect(b''.join(frame(*execution(f'0001.abcd.{i:02}.01')) for i in range(51)))
        with self.assertRaisesRegex(ProbeError,'excess_commission'):
            self.collect(b''.join(frame(*commission(f'0001.abcd.{i:02}.01')) for i in range(51)))
        with self.assertRaises(ProbeError):self.collect(frame(9,1,123)*2000)
        with self.assertRaises(ProbeError) as error:self.collect(frame(4,2,-1,321,'secret vendor text'))
        self.assertNotIn('secret',str(error.exception))
        with self.assertRaises(ProbeError):self.collect(frame(100,'binding'))

    def test_payload_tampering_scope_time_flags_and_integer_types_fail(self):
        valid=self.collect()
        for field,value in (('schema_version',True),('manual_order_coverage_verified',True),
                            ('transfer_coverage_verified',True),('broker_reconciliation',True),
                            ('commission_links_complete',False),('correction_observed',True),
                            ('started_at',float('nan')),('scope','all_account_history')):
            with self.subTest(field=field),self.assertRaises(ProbeError):
                validate_executions({**valid,field:value},'DU123',self.now)
        for field,value in (('contract_id',True),('client_id',1.0),('pending_price_revision',1),
                            ('quantity','-1'),('security_type','OPT'),('execution_exchange','bad\nvalue')):
            payload=copy.deepcopy(valid);payload['executions'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ProbeError):validate_executions(payload,'DU123',self.now)
        with self.assertRaises(ProbeError):validate_executions(valid,'DU123',self.now+60)


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class ExecutionReceiptTests(unittest.TestCase):
    collect=ExecutionTests.collect
    session=ExecutionTests.session

    def setUp(self):
        ExecutionTests.setUp(self)
        data=Path(__file__).resolve().parents[1]/'data';data.mkdir(exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=data);self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.private=self.root/'fixture.pem';self.public=self.root/'public.der';self.path=self.root/'receipt.json'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644);self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.settings=ExecutionReceiptConfig(self.public,self.pin,self.private)

    def signed(self,payload=None,domain=DOMAIN):
        receipt=signatures.sign(payload or self.collect(),self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=domain)
        return json.dumps(receipt).encode()

    def test_public_only_verification_after_private_key_removed_and_cross_domain_denial(self):
        raw=self.signed();sec=self.signed(domain=signatures.DOMAIN)
        self.private.unlink()
        consumer=replace(self.settings,signing_path=None)
        self.assertTrue(executions_from_bytes(raw,self.config,consumer,self.now)['commission_links_complete'])
        with self.assertRaises(ProbeError):executions_from_bytes(sec,self.config,consumer,self.now)

    def test_forgery_duplicate_json_oversize_expiry_and_wrong_account_are_rejected(self):
        raw=self.signed();receipt=json.loads(raw)
        for changed in ({**receipt,'signature':'00'*64},{**receipt,'algorithm':'hmac-sha256'},
                        {**receipt,'key_sha256':'a'*64}):
            with self.assertRaises(ProbeError):executions_from_bytes(json.dumps(changed).encode(),self.config,self.settings,self.now)
        for body in (raw.replace(b'"schema_version": 1',b'"schema_version": 1, "schema_version": 1'),b'x'*65537,b'NaN'):
            with self.assertRaises(ProbeError):executions_from_bytes(body,self.config,self.settings,self.now)
        with self.assertRaises(ProbeError):executions_from_bytes(raw,self.config,self.settings,self.now+60)
        with self.assertRaises(ProbeError):executions_from_bytes(raw,BrokerConfig(expected_account='DU999'),self.settings,self.now)

    def test_signer_failure_precedes_connection_and_failure_preserves_existing_receipt(self):
        self.path.write_text('existing')
        with patch('nexydao.executions.collect_executions') as collect:
            with self.assertRaises(ProbeError):save_executions(self.config,replace(self.settings,signing_path=None),self.path)
            collect.assert_not_called()
        with patch('nexydao.executions.collect_executions',side_effect=ProbeError('test_failure')):
            with self.assertRaises(ProbeError):save_executions(self.config,self.settings,self.path)
        with patch('nexydao.executions.collect_executions',return_value=self.collect()), \
                patch.object(signatures,'sign',side_effect=signatures.ReceiptSignatureError('test_failure')):
            with self.assertRaises(ProbeError):save_executions(self.config,self.settings,self.path)
        self.assertEqual(self.path.read_text(),'existing')

    def test_save_load_with_public_only_settings_does_not_import_any_ledger(self):
        payload=self.collect()
        with patch('nexydao.executions.collect_executions',return_value=payload):
            result=save_executions(self.config,self.settings,self.path)
        loaded=load_executions(self.config,replace(self.settings,signing_path=None),self.path)
        self.assertEqual(loaded,payload);self.assertFalse(result['ledger_imported'])

    def test_cli_report_requires_no_provider_database_or_broker_connection(self):
        from nexydao.cli import main
        payload=self.collect()
        with patch('sys.argv',['nexydao','broker-executions-report']), \
                patch.object(ExecutionReceiptConfig,'from_env',return_value=replace(self.settings,signing_path=None)), \
                patch('nexydao.executions.load_executions',return_value=payload),patch('nexydao.cli.Store') as store, \
                patch('nexydao.cli.OpenAIProvider') as provider,patch('socket.create_connection') as connect,patch('sys.stdout'):
            main()
        store.assert_not_called();provider.assert_not_called();connect.assert_not_called()

    def test_cli_collection_requires_host_guard_and_public_key_configuration(self):
        from nexydao.cli import main
        with patch.dict('os.environ',{},clear=True),self.assertRaises(ProbeError):ExecutionReceiptConfig.from_env()
        with patch('sys.argv',['nexydao','broker-executions']), \
                patch.object(ExecutionReceiptConfig,'from_env',return_value=self.settings), \
                patch('nexydao.access.run_access_check',return_value={'non_loopback_tcp_ingress_denied':False}), \
                patch('nexydao.executions.save_executions') as save,patch('sys.stderr'):
            with self.assertRaises(SystemExit) as stopped:main()
        self.assertEqual(stopped.exception.code,1);save.assert_not_called()
