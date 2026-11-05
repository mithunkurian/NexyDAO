import copy
from decimal import localcontext
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_broker_observations import state,views
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.market import canonical
from nexydao.executions import DOMAIN as FILLS_DOMAIN
from nexydao.state_receipts import DOMAIN as STATE_DOMAIN
from nexydao.broker_transitions import transition_report,load_transition_report
from nexydao import research_signatures as signatures


def paired(now):
    before=state(now-10);after=state(now)
    _,_,fills=views(now)
    opening=copy.deepcopy(fills);opening.update(started_at=now-10,received_at=now-10,expires_at=now+50)
    opening['executions']=[]
    after['positions']=[{'contract_id':123,'symbol':'TEST','security_type':'STK','currency':'USD',
                         'quantity':'2','average_cost':'100'}]
    for row in after['cash']:row['value']='4799'
    return before,after,opening,fills


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.now=time.time();self.config=BrokerConfig(expected_account='DU123');self.payloads=paired(self.now)

    def report(self):return transition_report(*self.payloads,self.config,self.now)

    def test_matching_new_buy_and_fee_never_establishes_reconciliation(self):
        before=copy.deepcopy(self.payloads);report=self.report()
        self.assertTrue(report['visible_deltas_match']);self.assertEqual(report['new_visible_execution_count'],1)
        self.assertEqual(report['position_residual_count'],0);self.assertEqual(report['cash_residual_currency_count'],0)
        self.assertEqual(report['position_change_count'],1);self.assertEqual(report['cash_change_currency_count'],1)
        self.assertEqual(self.payloads,before)
        for key in ('execution_interval_attribution_verified','settled_cash_reconciled','account_observation_atomic',
                'broker_reconciliation','broker_funding_verified','reservation_amounts_verified','ledger_imported',
                'funding_authorized','execution_authorized'):self.assertFalse(report[key])
        self.assertIn('execution_interval_attribution_unverified',report['missing_checks'])
        self.assertEqual(report['receipt_payloads_sha256']['before_state'],hashlib.sha256(canonical(before[0])).hexdigest())
        text=json.dumps(report)
        for secret in ('DU123','TEST','4799','20261105','private'):self.assertNotIn(secret,text)

    def test_existing_fills_are_not_counted_again_and_absent_positions_mean_zero_only_after_complete_download(self):
        a,b,x,y=self.payloads
        x['executions']=copy.deepcopy(y['executions']);b['positions']=[]
        b['cash']=copy.deepcopy(a['cash'])
        result=self.report();self.assertTrue(result['visible_deltas_match'])
        self.assertEqual(result['retained_execution_count'],1);self.assertEqual(result['new_visible_execution_count'],0)
        a['positions_download_complete']=False
        with self.assertRaises(ProbeError):self.report()

    def test_partial_fills_use_incremental_quantity_not_cumulative_or_average_price(self):
        a,b,x,y=self.payloads
        first=copy.deepcopy(y['executions'][0]);x['executions']=[first]
        second=copy.deepcopy(first);second.update(execution_sha256='b'*64,correction_group_sha256='c'*64,
            quantity='1',price='120',cumulative_quantity='3',average_price='106.6666666666')
        y['executions'].append(second);a['positions']=copy.deepcopy(b['positions'])
        b['positions'][0]['quantity']='3'
        for row in b['cash']:row['value']='4879'
        self.assertTrue(self.report()['visible_deltas_match'])

    def test_sale_and_negative_commission_rebate_have_correct_sign(self):
        a,b,x,y=self.payloads;a['positions']=copy.deepcopy(b['positions']);b['positions']=[]
        y['executions'][0].update(side='SLD',commission='-0.5')
        for row in b['cash']:row['value']='5200.5'
        self.assertTrue(self.report()['visible_deltas_match'])

    def test_cross_currency_fees_are_compared_separately_without_fx_netting(self):
        a,b,x,y=self.payloads;y['executions'][0]['commission_currency']='SEK';y['fee_currency_mismatch_observed']=True
        a['cash'].append({'tag':'CashBalance','currency':'SEK','value':'100'})
        b['cash'].append({'tag':'CashBalance','currency':'SEK','value':'99'})
        for row in b['cash']:
            if row['currency']=='USD':row['value']='4800'
        self.assertTrue(self.report()['visible_deltas_match'])
        b['cash'][-1]['value']='100'
        self.assertEqual(self.report()['cash_residual_currency_count'],1)

    def test_missing_currency_is_not_a_zero_balance_and_scope_is_not_inferred(self):
        a,b,x,y=self.payloads;a['cash'].append({'tag':'CashBalance','currency':'SEK','value':'0'})
        result=self.report();self.assertFalse(result['visible_deltas_match']);self.assertEqual(result['missing_cash_currency_count'],1)
        a['per_currency_scope_verified']=False
        result=self.report();self.assertIsNone(result['cash_residual_currency_count'])
        self.assertEqual(result['comparable_cash_currency_count'],0);self.assertFalse(result['visible_deltas_match'])

    def test_new_fill_fee_currency_not_in_either_state_is_missing(self):
        self.payloads[3]['executions'][0]['commission_currency']='SEK';self.payloads[3]['fee_currency_mismatch_observed']=True
        result=self.report();self.assertEqual(result['missing_cash_currency_count'],1);self.assertFalse(result['visible_deltas_match'])

    def test_transfers_or_unseen_activity_produce_residuals_even_if_net_cash_matches(self):
        a,b,x,y=self.payloads;b['positions'][0]['quantity']='3'
        result=self.report();self.assertEqual(result['position_residual_count'],1)
        self.assertFalse(result['visible_deltas_match'])
        b['cash'][0]['value']='4798'
        result=self.report();self.assertEqual(result['cash_residual_currency_count'],1)

    def test_unchanged_id_content_mutation_or_window_loss_suppresses_fill_arithmetic(self):
        a,b,x,y=self.payloads;x['executions']=copy.deepcopy(y['executions'])
        y['executions'][0]['commission']='2'
        result=self.report();self.assertEqual(result['changed_execution_count'],1)
        self.assertFalse(result['visible_fill_arithmetic_available']);self.assertIsNone(result['position_residual_count'])
        y['executions']=[]
        result=self.report();self.assertEqual(result['disappeared_execution_count'],1)
        self.assertFalse(result['visible_fill_arithmetic_available']);self.assertIsNone(result['cash_residual_currency_count'])

    def test_corrections_pending_prices_and_contract_changes_suppress_arithmetic(self):
        original=copy.deepcopy(self.payloads)
        for change in ('correction','revision','metadata','unsupported'):
            self.payloads=copy.deepcopy(original);a,b,x,y=self.payloads
            if change=='correction':y['executions'][0]['correction_sequence']=2;y['correction_observed']=True
            if change=='revision':y['executions'][0]['pending_price_revision']=True;y['pending_price_revision_observed']=True
            if change=='metadata':b['positions'][0]['symbol']='OTHER'
            if change=='unsupported':b['positions'][0]['security_type']='CFD'
            result=self.report();self.assertFalse(result['visible_fill_arithmetic_available']);self.assertFalse(result['visible_deltas_match'])

    def test_each_payload_requires_current_freshness_exact_account_and_supported_schema(self):
        original=copy.deepcopy(self.payloads)
        for index in range(4):
            self.payloads=copy.deepcopy(original);self.payloads[index]['account_sha256']='a'*64
            with self.subTest(index=index),self.assertRaises(ProbeError):self.report()
        with self.assertRaises(ProbeError):transition_report(*original,self.config,self.now+50)
        self.payloads=copy.deepcopy(original);a=self.payloads[0];a['schema_version']=2;del a['per_currency_scope_verified']
        with self.assertRaises(ProbeError):self.report()

    def test_reversed_identical_or_overlapping_pairs_do_not_establish_progress(self):
        original=copy.deepcopy(self.payloads)
        for pair in ((0,1),(2,3)):
            for mode in ('reversed','identical','overlap'):
                self.payloads=copy.deepcopy(original);items=list(self.payloads);i,j=pair
                if mode=='reversed':items[i],items[j]=items[j],items[i]
                if mode=='identical':items[j]=copy.deepcopy(items[i])
                if mode=='overlap':items[i]['received_at']=self.now+1
                with self.subTest(pair=pair,mode=mode),self.assertRaises(ProbeError):
                    transition_report(*items,self.config,self.now+2)

    def test_arithmetic_preserves_tiny_residuals_under_low_process_precision(self):
        a,b,x,y=self.payloads;y['executions'][0].update(quantity='9999999999999999.123456789012',
            cumulative_quantity='9999999999999999.123456789012',price='0.000000000001',commission='0')
        b['positions'][0]['quantity']='9999999999999999.123456789011'
        with localcontext() as context:
            context.prec=6
            result=self.report()
        self.assertEqual(result['position_residual_count'],1);self.assertFalse(result['visible_deltas_match'])

    def test_cross_pair_overlap_is_rejected_even_when_individual_pairs_advance(self):
        self.payloads[2]['received_at']=self.now+1
        self.payloads[3].update(started_at=self.now+2,received_at=self.now+2,expires_at=self.now+62)
        with self.assertRaisesRegex(ProbeError,'transition_pairs_overlap'):
            transition_report(*self.payloads,self.config,self.now+3)

    def test_tiny_fee_free_fill_notional_cannot_disappear_next_to_large_fill(self):
        a,b,x,y=self.payloads
        first=y['executions'][0];first.update(quantity='9999999999999999',
            cumulative_quantity='9999999999999999',price='0.000000000001',commission='0')
        second=copy.deepcopy(first);second.update(execution_sha256='b'*64,correction_group_sha256='c'*64,
            quantity='0.000000000001',cumulative_quantity='0.000000000001')
        y['executions'].append(second);b['positions'][0]['quantity']='9999999999999999.000000000001'
        for row in a['cash']:row['value']='20000'
        for row in b['cash']:row['value']='10000.000000000001'
        with localcontext() as context:
            context.prec=6
            result=self.report()
        self.assertEqual(result['position_residual_count'],0)
        self.assertEqual(result['cash_residual_currency_count'],1);self.assertFalse(result['visible_deltas_match'])

    def test_numeric_agreement_does_not_hide_negative_cash_short_positions_or_missing_settled_cash(self):
        a,b,x,y=self.payloads
        x['executions']=[];y['executions']=[]
        for s in (a,b):
            s['positions']=[];s['cash']=[{'tag':'CashBalance','currency':'USD','value':'-1'}]
        result=self.report();self.assertTrue(result['visible_deltas_match'])
        self.assertTrue(result['after_state']['negative_currency_cash_observed'])
        self.assertIn('negative_currency_cash_requires_resolution',result['missing_checks'])
        self.assertIn('per_currency_settled_cash_evidence_incomplete',result['missing_checks'])
        self.assertFalse(result['broker_funding_verified'])


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class TransitionReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.now=time.time();self.config=BrokerConfig(expected_account='DU123')
        self.payloads=paired(self.now);self.private=self.root/'key.pem';self.public=self.root/'public.der'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644);self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.paths=[self.root/(name+'.json') for name in ('before-state','after-state','before-fills','after-fills')]
        for path,payload,domain in zip(self.paths,self.payloads,(STATE_DOMAIN,STATE_DOMAIN,FILLS_DOMAIN,FILLS_DOMAIN)):
            path.write_text(json.dumps(signatures.sign(payload,self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=domain)))
            path.chmod(0o600)
        self.environment={'NEXYDAO_IBKR_EXPECTED_ACCOUNT':'DU123','NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT':str(self.paths[1]),
            'NEXYDAO_EXECUTIONS_SNAPSHOT':str(self.paths[3])}
        for prefix in ('STATE','EXECUTION'):
            self.environment['NEXYDAO_'+prefix+'_RECEIPT_PUBLIC_KEY_FILE']=str(self.public)
            self.environment['NEXYDAO_'+prefix+'_RECEIPT_PUBLIC_KEY_SHA256']=self.pin

    def test_actual_cli_after_private_key_removal_needs_no_hmac_db_socket_or_provider(self):
        from nexydao.cli import main
        self.private.unlink();output=io.StringIO();before={p:p.read_bytes() for p in self.paths}
        arguments=['nexydao','broker-transition-report','--before-state',str(self.paths[0]),'--before-executions',str(self.paths[2])]
        with patch.dict(os.environ,self.environment,clear=True),patch('sys.argv',arguments),patch('sys.stdout',output), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('socket.create_connection') as connect,patch('nexydao.market.read_key') as hmac:
            main()
        for operation in (store,provider,connect,hmac):operation.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())['visible_deltas_match']);self.assertNotIn('DU123',output.getvalue())
        self.assertEqual(before,{p:p.read_bytes() for p in self.paths});self.assertFalse(list(self.root.glob('*.sqlite*')))

    def test_missing_swapped_tampered_and_wrong_pinned_receipts_fail_without_fallback(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaises(ProbeError):
            load_transition_report(self.config,self.paths[0],self.paths[2])
        raw=self.paths[0].read_bytes()
        for body in (self.paths[2].read_bytes(),raw.replace(b'5000',b'5001'),b'{"payload":{},"signature":"legacy"}'):
            self.paths[0].write_bytes(body)
            with patch.dict(os.environ,self.environment,clear=True),self.assertRaises(ProbeError):
                load_transition_report(self.config,self.paths[0],self.paths[2])
        self.paths[0].write_bytes(raw)
        with patch.dict(os.environ,{**self.environment,'NEXYDAO_STATE_RECEIPT_PUBLIC_KEY_SHA256':'a'*64},clear=True),self.assertRaises(ProbeError):
            load_transition_report(self.config,self.paths[0],self.paths[2])

    def test_first_receipt_expiring_during_last_verification_is_rejected(self):
        clock=[self.now];a,b,x,y=self.payloads
        def last(*args):clock[0]=self.now+50;return y
        with patch.dict(os.environ,self.environment,clear=True), \
                patch('nexydao.broker_transitions.load_public_state',side_effect=(a,b)), \
                patch('nexydao.broker_transitions.load_executions',side_effect=lambda *args:x if clock[0]==self.now and args[-1]==self.paths[2] else last()), \
                patch('nexydao.broker_transitions.time.time',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(ProbeError,'state_expired'):load_transition_report(self.config,self.paths[0],self.paths[2])

    def test_cli_prior_arguments_are_required_and_rejected_for_other_commands(self):
        from nexydao.cli import main
        for arguments in (['broker-transition-report'],['broker-state-report','--before-state',str(self.paths[0])]):
            with patch.dict(os.environ,self.environment,clear=True),patch('sys.argv',['nexydao',*arguments]), \
                    patch('sys.stderr'),self.assertRaises(SystemExit):main()
