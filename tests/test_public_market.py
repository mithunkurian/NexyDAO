from dataclasses import replace
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_market as fixtures
from nexydao import research_signatures as signatures
from nexydao.market import (DOMAIN,MarketConfig,canonical,load_market_evidence,
    market_evidence_from_bytes,run_market_check)
from nexydao.ibkr import BrokerConfig,ProbeError
from nexydao.cli import main,DemoProvider
from nexydao.portfolio import Portfolio
from nexydao.owner_policy import load_policy
from nexydao.quote_liquidity import QuoteLiquidity
from nexydao.store import Store
from nexydao.workflow import run_cycle


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class PublicMarketTests(unittest.TestCase):
    contract=fixtures.MarketTests.contract
    session=fixtures.MarketTests.session
    payload=fixtures.MarketTests.payload

    def setUp(self):
        fixtures.MarketTests.setUp(self);self.legacy=self.config
        self.private=self.root/'fixture.pem';self.public=self.root/'fixture.der'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644);self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.config=replace(self.legacy,key_path=None,receipt_mode='ed25519',public_path=self.public,
                            public_sha256=self.pin,signing_path=self.private)

    def signed(self,payload=None,domain=DOMAIN):
        return json.dumps(signatures.sign(payload or self.payload(),self.private,self.public,self.pin,
                                          signatures.DEFAULT_OPENSSL,domain=domain)).encode()

    def environment(self):
        return {'NEXYDAO_MARKET_RECEIPT_MODE':'ed25519','NEXYDAO_MARKET_PUBLIC_KEY_FILE':str(self.public),
            'NEXYDAO_MARKET_PUBLIC_KEY_SHA256':self.pin,'NEXYDAO_MARKET_SIGNING_KEY_FILE':str(self.private),
            'NEXYDAO_EVIDENCE_KEY_FILE':str(self.key),'NEXYDAO_MARKET_SYMBOL':'SPY','NEXYDAO_IBKR_EXPECTED_ACCOUNT':'DU123'}

    def test_public_consumer_never_opens_missing_legacy_or_signing_keys(self):
        payload=self.payload();raw=self.signed(payload)
        hmac_raw=json.dumps({'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}).encode()
        legacy=market_evidence_from_bytes(hmac_raw,self.legacy,self.now)
        self.private.unlink();self.key.unlink()
        consumer=replace(self.config,key_path=self.key)  # Obsolete paths must be ignored.
        with patch('nexydao.market.read_key',side_effect=AssertionError('HMAC key opened')):
            evidence=market_evidence_from_bytes(raw,consumer,self.now)
        self.assertEqual(evidence,legacy)
        self.assertFalse(QuoteLiquidity(evidence,self.now).report()['market_liquidity_verified'])

    def test_explicit_mode_and_pin_configuration_with_no_legacy_key_requirement(self):
        environment=self.environment();environment['NEXYDAO_EVIDENCE_KEY_FILE']='nonexistent-legacy-key'
        with patch.dict(os.environ,environment,clear=True):
            config=MarketConfig.from_env();self.assertIsNone(config.key_path)
        for change in ({'NEXYDAO_MARKET_RECEIPT_MODE':'auto'},
                       {'NEXYDAO_MARKET_PUBLIC_KEY_SHA256':''},{'NEXYDAO_MARKET_PUBLIC_KEY_FILE':''}):
            with patch.dict(os.environ,{**environment,**change},clear=True),self.assertRaises(ValueError):MarketConfig.from_env()
        with patch.dict(os.environ,{'NEXYDAO_IBKR_EXPECTED_ACCOUNT':'DU123','NEXYDAO_EVIDENCE_KEY_FILE':str(self.key)},clear=True):
            self.assertEqual(MarketConfig.from_env().receipt_mode,'hmac-sha256')

    def test_collector_checks_signer_and_pin_before_opening_broker_connection(self):
        for config in (replace(self.config,signing_path=None),replace(self.config,public_sha256='a'*64)):
            with patch('nexydao.market.collect') as collect:
                with self.assertRaisesRegex(ProbeError,'signer_unavailable'):run_market_check(config)
                collect.assert_not_called()

    def test_collector_save_and_public_only_load_preserve_original_quote_scope(self):
        payload=self.payload()
        with patch('nexydao.market.collect',return_value=payload):result=run_market_check(self.config)
        self.assertEqual(result['receipt_mode'],'ed25519');self.assertFalse(result['execution_authorized'])
        self.assertEqual(json.loads(self.config.snapshot.read_text())['algorithm'],'ed25519')
        self.private.unlink();self.key.unlink()
        evidence=load_market_evidence(self.config.snapshot,replace(self.config,signing_path=None))
        self.assertEqual(json.loads(evidence[0]['summary'])['received_at'],payload['received_at'])

    def test_mode_selection_has_no_algorithm_fallback_in_either_direction(self):
        payload=self.payload();modern=self.signed(payload)
        legacy=json.dumps({'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}).encode()
        with self.assertRaises(ProbeError):market_evidence_from_bytes(legacy,self.config,self.now)
        with self.assertRaises(ProbeError):market_evidence_from_bytes(modern,self.legacy,self.now)

    def test_wrong_domains_cannot_reuse_other_receipts_even_with_same_test_key(self):
        from nexydao.executions import DOMAIN as EXECUTIONS
        from nexydao.order_visibility import DOMAIN as ORDERS
        from nexydao.state_receipts import DOMAIN as STATE
        from nexydao.paper_permits import DOMAIN as PERMITS
        for domain in (signatures.DOMAIN,EXECUTIONS,ORDERS,STATE,PERMITS):
            with self.subTest(domain=domain),self.assertRaises(ProbeError):
                market_evidence_from_bytes(self.signed(domain=domain),self.config,self.now)

    def test_tampered_signature_algorithm_pin_duplicate_json_and_bounds_fail(self):
        raw=self.signed();receipt=json.loads(raw)
        for changed in ({**receipt,'signature':'00'*64},{**receipt,'algorithm':'hmac-sha256'},
                        {**receipt,'key_sha256':'a'*64}):
            with self.assertRaises(ProbeError):market_evidence_from_bytes(json.dumps(changed).encode(),self.config,self.now)
        for body in (raw.replace(b'"schema_version": 1',b'"schema_version": 1,"schema_version": 1'),b'x'*16001,b'NaN'):
            with self.assertRaises(ProbeError):market_evidence_from_bytes(body,self.config,self.now)
        with self.assertRaises(ProbeError):market_evidence_from_bytes(raw,replace(self.config,public_sha256='a'*64),self.now)

    def test_exact_account_symbol_flags_and_freshness_survive_public_authentication(self):
        raw=self.signed()
        for config in (replace(self.config,broker=BrokerConfig(expected_account='DU999')),replace(self.config,symbol='OTHER')):
            with self.assertRaises(ProbeError):market_evidence_from_bytes(raw,config,self.now)
        with self.assertRaises(ProbeError):market_evidence_from_bytes(raw,self.config,self.now+60)
        payload=self.payload();payload['quote']['flags']=1
        with self.assertRaises(ProbeError):market_evidence_from_bytes(self.signed(payload),self.config,self.now)

    def test_failures_or_expiry_after_signing_preserve_prior_file_and_ttl(self):
        self.config.snapshot.write_text('previous')
        with patch('nexydao.market.collect',side_effect=ProbeError('fixture_failure')):
            with self.assertRaises(ProbeError):run_market_check(self.config)
        with patch('nexydao.market.collect',return_value=self.payload()), \
                patch.object(signatures,'sign',side_effect=signatures.ReceiptSignatureError('fixture_failure')):
            with self.assertRaises(ProbeError):run_market_check(self.config)
        clock=[self.now];sign=signatures.sign
        def sign_then_expire(*args,**kwargs):
            receipt=sign(*args,**kwargs);clock[0]=self.now+60
            return receipt
        with patch('nexydao.market.collect',return_value=self.payload()), \
                patch.object(signatures,'sign',side_effect=sign_then_expire), \
                patch('nexydao.market.time.time',side_effect=lambda:clock[0]):
            with self.assertRaises(ProbeError):run_market_check(self.config)
        self.assertEqual(self.config.snapshot.read_text(),'previous')

    def test_cli_report_works_after_both_private_keys_are_removed_without_db_provider_or_socket(self):
        self.config.snapshot.write_bytes(self.signed());self.config.snapshot.chmod(0o600)
        self.private.unlink();self.key.unlink();output=io.StringIO()
        with patch.dict(os.environ,self.environment(),clear=True), \
                patch('sys.argv',['nexydao','quote-liquidity-report','--market-evidence',str(self.config.snapshot)]), \
                patch('nexydao.market.read_key',side_effect=AssertionError('HMAC key opened')), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('socket.create_connection') as connect,patch('sys.stdout',output):main()
        for operation in (store,provider,connect):operation.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['executable_depth_verified'])

    def test_marking_and_advisory_cycle_use_public_only_quote_without_authority(self):
        self.config.snapshot.write_bytes(self.signed());self.config.snapshot.chmod(0o600)
        self.private.unlink();self.key.unlink()
        store=Store(self.root/'simulation.sqlite3');self.addCleanup(store.close)
        ledger=Portfolio(store)
        ledger.fill({'id':'fixture','side':'buy','symbol':'SPY','quantity':'1','price':'100','fee':'0','currency':'USD','asset_type':'STK'},load_policy())
        ledger.mark(self.config.snapshot,self.config)
        self.assertEqual(ledger.snapshot()['positions'][0]['contract_id'],123)
        result=run_cycle(store,DemoProvider(),load_market_evidence(self.config.snapshot,self.config))
        self.assertFalse(result['policy']['execution_authorized']);self.assertEqual(store.costs()['calls'],0)

    @unittest.skipUnless(os.name=='posix','Unix receipt permissions')
    def test_unix_symlink_or_writable_public_receipt_is_rejected(self):
        self.config.snapshot.write_bytes(self.signed());self.config.snapshot.chmod(0o666)
        with self.assertRaises(ProbeError):load_market_evidence(self.config.snapshot,self.config)
        self.config.snapshot.chmod(0o600);link=self.root/'link.json';link.symlink_to(self.config.snapshot)
        with self.assertRaises(ProbeError):load_market_evidence(link,self.config)
