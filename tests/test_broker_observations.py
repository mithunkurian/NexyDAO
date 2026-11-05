import copy
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_ibkr import Socket,frame
from test_executions import execution,commission
import test_order_visibility as order_fixtures
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.market import canonical
from nexydao.reconciliation import SOURCE as STATE_SOURCE
from nexydao.executions import collect_executions,ExecutionReceiptConfig,REQUEST_ID,DOMAIN as EXECUTION_DOMAIN
from nexydao.order_visibility import DOMAIN as ORDER_DOMAIN,OrderReceiptConfig
from nexydao.state_receipts import (DOMAIN as STATE_DOMAIN,StateReceiptConfig,save_public_state,
    public_state_from_bytes,load_public_state,state_report)
from nexydao.broker_observations import cross_check_observations,load_observation_report
from nexydao import research_signatures as signatures


def state(now):
    return {'schema_version':3,'source':STATE_SOURCE,'protocol_version':178,
        'account_sha256':hashlib.sha256(b'DU123').hexdigest(),'started_at':now,'received_at':now,'expires_at':now+60,
        'cash_download_complete':True,'positions_download_complete':True,'per_currency_scope_verified':True,
        'settled_cash_schedule_unparsed':False,'settlement_observations':[],
        'cash':[{'tag':tag,'currency':'USD','value':'5000'} for tag in ('CashBalance','SettledCash','TotalCashBalance')],
        'positions':[]}


def views(now):
    orders=order_fixtures.collect(now=now)
    sock=Socket(frame(178,'time')+frame(15,1,'DU123')+frame(*execution())+frame(*commission())+frame(55,1,REQUEST_ID))
    fills=collect_executions(BrokerConfig(expected_account='DU123'),lambda *a,**k:sock,lambda:now)
    return state(now),orders,fills


class CrossObservationTests(unittest.TestCase):
    def setUp(self):
        self.now=time.time();self.config=BrokerConfig(expected_account='DU123')
        self.state,self.orders,self.fills=views(self.now)

    def check(self,**kwargs):
        return cross_check_observations(kwargs.get('state',self.state),kwargs.get('orders',self.orders),
            kwargs.get('fills',self.fills),self.config,kwargs.get('now',self.now))

    def test_consistent_metadata_and_overlapping_windows_never_grant_authority(self):
        result=self.check()
        self.assertEqual(result['linked_execution_observation_count'],1)
        self.assertFalse(result['cross_observation_conflicts_observed'])
        self.assertTrue(result['observation_windows_overlap'])
        for key in ('broker_reconciliation','broker_funding_verified','account_observation_atomic',
                    'reservation_amounts_verified','ledger_imported','funding_authorized','execution_authorized'):
            self.assertFalse(result[key])
        self.assertIn('opening_balances_fills_fees_and_transfers',result['missing_checks'])
        self.assertEqual(result['receipt_payloads_sha256']['state'],hashlib.sha256(canonical(self.state)).hexdigest())

    def test_fully_filled_order_absent_from_open_query_is_unlinked_not_a_conflict(self):
        result=self.check(orders=order_fixtures.collect(b'',self.now))
        self.assertEqual(result['unlinked_execution_observation_count'],1)
        self.assertFalse(result['cross_observation_conflicts_observed']);self.assertFalse(result['broker_reconciliation'])

    def test_positive_permanent_id_requires_exact_client_and_order_identity(self):
        self.fills['executions'][0]['client_id']=92
        result=self.check()
        self.assertEqual(result['order_execution_identity_conflict_count'],1)
        self.assertEqual(result['linked_execution_observation_count'],0)
        self.fills['executions'][0]['permanent_id']=0
        result=self.check();self.assertEqual(result['order_execution_identity_conflict_count'],0)
        self.assertEqual(result['unlinked_execution_observation_count'],1)

    def test_contract_side_and_cumulative_quantity_conflicts_are_observations_not_netting(self):
        for field,value,diagnostic in (('symbol','OTHER','order_execution_contract_conflict_count'),
                ('contract_id',124,'order_execution_contract_conflict_count'),('side','SLD','order_execution_side_conflict_count'),
                ('cumulative_quantity','3','execution_cumulative_quantity_above_observed_order_count')):
            fills=copy.deepcopy(self.fills);fills['executions'][0][field]=value
            with self.subTest(field=field):
                result=self.check(fills=fills)
                self.assertEqual(result[diagnostic],1);self.assertTrue(result['cross_observation_conflicts_observed'])
                self.assertFalse(result['ledger_imported'])

    def test_position_contract_metadata_is_compared_without_inventing_opening_balances(self):
        self.state['positions']=[{'contract_id':123,'symbol':'OTHER','security_type':'STK','currency':'USD','quantity':'50','average_cost':'80'}]
        self.assertEqual(self.check()['contract_metadata_conflict_count'],1)
        self.state['positions'][0]['symbol']='TEST'
        result=self.check();self.assertEqual(result['contract_metadata_conflict_count'],0)
        self.assertFalse(result['broker_reconciliation'])  # Fifty shares need not equal this partial recent fill.

    def test_fee_currency_missing_from_cash_is_flagged_without_automatic_fx(self):
        self.fills['executions'][0]['commission_currency']='SEK'
        self.fills['fee_currency_mismatch_observed']=True
        result=self.check()
        self.assertEqual(result['fee_currency_not_observed_in_cash_count'],1)
        self.assertIn('fee_currency_cash_evidence_missing',result['missing_checks'])
        self.assertFalse(result['funding_authorized'])

    def test_each_view_rechecks_account_schema_scope_and_freshness(self):
        for index in range(3):
            changed=copy.deepcopy((self.state,self.orders,self.fills));changed[index]['account_sha256']='a'*64
            with self.subTest(index=index),self.assertRaises(ProbeError):
                cross_check_observations(*changed,self.config,self.now)
        with self.assertRaises(ProbeError):self.check(now=self.now+60)
        legacy=copy.deepcopy(self.state);legacy['schema_version']=2;del legacy['per_currency_scope_verified']
        with self.assertRaises(ProbeError):self.check(state=legacy)

    def test_window_separation_and_minimum_expiry_are_reported_without_atomicity(self):
        self.orders.update(started_at=self.now+1,received_at=self.now+1,expires_at=self.now+61)
        self.fills.update(started_at=self.now+2,received_at=self.now+2,expires_at=self.now+62)
        result=self.check(now=self.now+3)
        self.assertFalse(result['observation_windows_overlap']);self.assertFalse(result['account_observation_atomic'])
        self.assertEqual(result['evidence_expires_at'],self.now+60)

    def test_negative_cash_missing_scope_and_pending_execution_remain_explicit_blockers(self):
        self.state['cash'][0]['value']='-1';self.state['per_currency_scope_verified']=False
        self.fills['executions'][0]['pending_price_revision']=True
        self.fills['pending_price_revision_observed']=True
        result=self.check()
        for reason in ('negative_currency_cash_requires_resolution','per_currency_settled_cash_evidence_incomplete',
                       'execution_prices_pending_revision'):
            self.assertIn(reason,result['missing_checks'])
        self.assertFalse(result['funding_authorized'])


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class PublicStateReceiptTests(unittest.TestCase):
    def setUp(self):
        data=Path(__file__).resolve().parents[1]/'data';data.mkdir(exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=data);self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.private=self.root/'fixture.pem';self.public=self.root/'fixture.der';self.path=self.root/'state.json'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644);self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.settings=StateReceiptConfig(self.public,self.pin,self.private)
        self.config=BrokerConfig(expected_account='DU123');self.now=time.time()
        self.state,self.orders,self.fills=views(self.now)

    def signed(self,payload=None,domain=STATE_DOMAIN):
        return json.dumps(signatures.sign(payload or self.state,self.private,self.public,self.pin,
            signatures.DEFAULT_OPENSSL,domain=domain)).encode()

    def environment(self):
        result={'NEXYDAO_IBKR_EXPECTED_ACCOUNT':'DU123','NEXYDAO_DB':str(self.root/'audit.sqlite3'),
            'NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT':str(self.path),
            'NEXYDAO_TYPED_ORDERS_SNAPSHOT':str(self.root/'orders.json'),
            'NEXYDAO_EXECUTIONS_SNAPSHOT':str(self.root/'executions.json')}
        for prefix in ('STATE','ORDER','EXECUTION'):
            result['NEXYDAO_'+prefix+'_RECEIPT_PUBLIC_KEY_FILE']=str(self.public)
            result['NEXYDAO_'+prefix+'_RECEIPT_PUBLIC_KEY_SHA256']=self.pin
        return result

    def write_bundle(self):
        for path,payload,domain in ((self.path,self.state,STATE_DOMAIN),
                (self.root/'orders.json',self.orders,ORDER_DOMAIN),(self.root/'executions.json',self.fills,EXECUTION_DOMAIN)):
            path.write_bytes(self.signed(payload,domain));path.chmod(0o600)

    def test_public_only_state_read_after_private_key_removed_and_domain_separation(self):
        from nexydao.paper_permits import DOMAIN as SHADOW_DOMAIN
        raw=self.signed()
        wrong=[self.signed(domain=domain) for domain in (signatures.DOMAIN,ORDER_DOMAIN,EXECUTION_DOMAIN,SHADOW_DOMAIN)]
        self.private.unlink();consumer=replace(self.settings,signing_path=None)
        self.assertEqual(public_state_from_bytes(raw,self.config,consumer),self.state)
        self.assertEqual(public_state_from_bytes(raw,self.config,self.settings),self.state)  # Obsolete private path is ignored.
        for body in (*wrong,b'{"payload":{},"signature":"legacy-hmac"}'):
            with self.assertRaises(ProbeError):public_state_from_bytes(body,self.config,consumer)

    def test_bad_signature_pin_duplicate_size_schema_account_and_expiry_are_rejected(self):
        raw=self.signed();receipt=json.loads(raw)
        for change in ({'signature':'00'*64},{'key_sha256':'a'*64},{'algorithm':'hmac-sha256'}):
            with self.assertRaises(ProbeError):public_state_from_bytes(json.dumps({**receipt,**change}).encode(),self.config,self.settings)
        for body in (raw.replace(b'"schema_version": 3',b'"schema_version": 3,"schema_version": 3'),b'x'*65537,b'NaN'):
            with self.assertRaises(ProbeError):public_state_from_bytes(body,self.config,self.settings)
        legacy=copy.deepcopy(self.state);legacy['schema_version']=2;del legacy['per_currency_scope_verified']
        with self.assertRaises(ProbeError):public_state_from_bytes(self.signed(legacy),self.config,self.settings)
        with self.assertRaises(ProbeError):public_state_from_bytes(raw,BrokerConfig(expected_account='DU999'),self.settings)
        with self.assertRaises(ProbeError):public_state_from_bytes(raw,self.config,self.settings,self.now+60)

    def test_signer_before_query_and_collection_signing_failures_preserve_previous_file(self):
        self.path.write_text('previous')
        with patch('nexydao.state_receipts.collect_state') as collect:
            with self.assertRaises(ProbeError):save_public_state(self.config,replace(self.settings,signing_path=None),self.path)
            collect.assert_not_called()
        with patch('nexydao.state_receipts.collect_state',side_effect=ProbeError('fixture_failure')):
            with self.assertRaises(ProbeError):save_public_state(self.config,self.settings,self.path)
        with patch('nexydao.state_receipts.collect_state',return_value=self.state), \
                patch.object(signatures,'sign',side_effect=signatures.ReceiptSignatureError('fixture_failure')):
            with self.assertRaises(ProbeError):save_public_state(self.config,self.settings,self.path)
        self.assertEqual(self.path.read_text(),'previous')

    def test_save_load_keeps_negative_cash_and_unknown_scope_as_denial_diagnostics(self):
        self.state['cash'][0]['value']='-1';self.state['per_currency_scope_verified']=False
        with patch('nexydao.state_receipts.collect_state',return_value=self.state):
            result=save_public_state(self.config,self.settings,self.path)
        self.assertTrue(result['negative_currency_cash_observed']);self.assertFalse(result['broker_funding_verified'])
        loaded=load_public_state(self.config,replace(self.settings,signing_path=None),self.path)
        self.assertFalse(loaded['per_currency_scope_verified'])

    def test_actual_three_receipt_public_report_needs_no_signer_hmac_db_provider_or_socket(self):
        from nexydao.cli import main
        self.write_bundle();self.private.unlink();output=io.StringIO()
        with patch('sys.argv',['nexydao','broker-observations-report']),patch.dict(os.environ,self.environment(),clear=True), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('socket.create_connection') as connect,patch('nexydao.market.read_key') as hmac_key,patch('sys.stdout',output):
            main()
        for operation in (store,provider,connect,hmac_key):operation.assert_not_called()
        report=json.loads(output.getvalue());self.assertFalse(report['execution_authorized'])
        self.assertFalse(report['cross_observation_conflicts_observed']);self.assertNotIn('DU123',output.getvalue())
        self.assertFalse(list(self.root.glob('*.sqlite*')))

    def test_paths_are_explicit_and_missing_or_swapped_receipts_never_fall_back(self):
        self.write_bundle();environment=self.environment()
        with patch.dict(os.environ,{},clear=True),self.assertRaises(ProbeError):load_observation_report(self.config)
        self.path.write_bytes((self.root/'orders.json').read_bytes())
        with patch.dict(os.environ,environment,clear=True),self.assertRaises(ProbeError):load_observation_report(self.config)
        self.write_bundle();(self.root/'executions.json').unlink()
        with patch.dict(os.environ,environment,clear=True),self.assertRaises(ProbeError):load_observation_report(self.config)

    def test_bundle_rechecks_first_receipt_after_last_signature_verification(self):
        clock=[self.now]
        def last_verified(*arguments):
            clock[0]=self.now+60
            return self.fills
        with patch.dict(os.environ,self.environment(),clear=True), \
                patch('nexydao.broker_observations.load_public_state',return_value=self.state), \
                patch('nexydao.broker_observations.load_typed_orders',return_value=self.orders), \
                patch('nexydao.broker_observations.load_executions',side_effect=last_verified) as last, \
                patch('nexydao.broker_observations.time.time',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(ProbeError,'state_expired'):load_observation_report(self.config)
        last.assert_called_once()

    def test_public_state_is_preferred_without_legacy_fallback_and_failure_precedes_db(self):
        from nexydao.cli import main
        with patch('sys.argv',['nexydao','funding-check']),patch.dict(os.environ,self.environment(),clear=True), \
                patch('nexydao.state_receipts.load_public_state',side_effect=ProbeError('fixture_invalid_public')), \
                patch('nexydao.reconciliation.load_state') as legacy,patch('nexydao.cli.Store') as store,patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        legacy.assert_not_called();store.assert_not_called()

    def test_existing_funding_allocation_and_reconcile_work_with_public_state_without_hmac(self):
        from nexydao.cli import main
        self.write_bundle();self.private.unlink()
        for command in ('funding-check','allocation-check','broker-reconcile'):
            output=io.StringIO()
            with self.subTest(command=command),patch('sys.argv',['nexydao',command]), \
                    patch.dict(os.environ,self.environment(),clear=True),patch('nexydao.market.read_key') as key,patch('sys.stdout',output):
                main()
            key.assert_not_called();report=json.loads(output.getvalue());self.assertFalse(report['execution_authorized'])
            if command=='allocation-check':self.assertEqual(report['planning_ceiling_after_reserves_usd'],'0')

    def test_public_collector_host_guard_and_legacy_writer_key_requirements_remain(self):
        from nexydao.cli import main
        with patch('sys.argv',['nexydao','broker-state-public']),patch.dict(os.environ,self.environment(),clear=True), \
                patch('nexydao.access.run_access_check',return_value={'non_loopback_tcp_ingress_denied':False}), \
                patch('nexydao.state_receipts.save_public_state') as save,patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        save.assert_not_called()
        with patch('sys.argv',['nexydao','broker-state']),patch.dict(os.environ,self.environment(),clear=True), \
                patch('nexydao.reconciliation.save_state') as legacy,patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        legacy.assert_not_called()
