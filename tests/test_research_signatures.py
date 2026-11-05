import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import test_research as fixtures
from nexydao.research_signatures import DEFAULT_OPENSSL, ReceiptSignatureError, _command, sign
from nexydao.sec import ResearchConfig, SourceError, collect, load_research_evidence, run_source_check
from nexydao.store import Store
from nexydao.workflow import run_cycle


@unittest.skipUnless(DEFAULT_OPENSSL.is_file(), 'Optional protected OpenSSL executable unavailable')
class ResearchSignatureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ResearchTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.private = self.root/'collector.pem'
        self.private.write_bytes(_command(DEFAULT_OPENSSL, ['genpkey', '-algorithm', 'ED25519']))
        self.private.chmod(0o600)
        self.public = self.root/'collector-public.der'
        self.public.write_bytes(_command(DEFAULT_OPENSSL, ['pkey', '-in', str(self.private), '-passin', 'pass:',
                                                           '-pubout', '-outform', 'DER']))
        self.public.chmod(0o644)
        self.pin = hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.config = replace(self.fixture.config, key_path=None, receipt_mode='ed25519',
                              signing_key_path=self.private, public_key_path=self.public,
                              public_key_sha256=self.pin, openssl_path=DEFAULT_OPENSSL)
        self.payload = self.fixture.payload()

    def receipt(self, payload=None):
        value = sign(self.payload if payload is None else payload, self.private, self.public, self.pin, DEFAULT_OPENSSL)
        self.config.snapshot.write_text(json.dumps(value))
        return value

    def load(self, config=None, now=None):
        return load_research_evidence(self.config.snapshot, config or replace(self.config, signing_key_path=None),
                                      self.fixture.now if now is None else now)

    def test_public_only_consumer_and_nine_role_workflow_need_no_signing_secret(self):
        self.receipt()
        self.private.unlink()
        self.fixture.key.unlink()
        evidence = self.load()
        self.assertTrue(all(e['receipt_authentication'] == 'ed25519' for e in evidence))
        store = Store(self.root/'public-consumer.sqlite3')
        self.addCleanup(store.close)
        provider = self.fixture.provider(evidence)
        result = run_cycle(store, provider, evidence, research=True, portfolio=True)
        self.assertEqual(len(provider.calls), 9)
        self.assertFalse(result['policy']['execution_authorized'])
        self.assertEqual(store.costs()['calls'], 0)

    def test_mutated_payload_signature_algorithm_pin_and_extra_fields_fail(self):
        original = self.receipt()
        for mutation in ('payload', 'signature', 'truncated', 'algorithm', 'pin', 'extra'):
            value = copy.deepcopy(original)
            if mutation == 'payload': value['payload']['facts'][0]['value'] = '999'
            if mutation == 'signature': value['signature'] = '00'*64
            if mutation == 'truncated': value['signature'] = '00'
            if mutation == 'algorithm': value['algorithm'] = 'hmac-sha256'
            if mutation == 'pin': value['key_sha256'] = 'a'*64
            if mutation == 'extra': value['trusted'] = True
            self.config.snapshot.write_text(json.dumps(value))
            with self.subTest(mutation=mutation), self.assertRaises(SourceError):
                self.load()

    def test_no_algorithm_downgrade_or_legacy_fallback(self):
        self.fixture.receipt(self.payload)
        with self.assertRaises(SourceError):
            self.load()
        self.receipt()
        with self.assertRaises(SourceError):
            load_research_evidence(self.config.snapshot, self.fixture.config, self.fixture.now)

    def test_wrong_trusted_public_key_cannot_verify_signature(self):
        value = self.receipt()
        other = self.root/'other.pem'
        other.write_bytes(_command(DEFAULT_OPENSSL, ['genpkey', '-algorithm', 'ED25519']));other.chmod(0o600)
        raw = _command(DEFAULT_OPENSSL, ['pkey', '-in', str(other), '-passin', 'pass:', '-pubout', '-outform', 'DER'])
        self.public.write_bytes(raw)
        pin = hashlib.sha256(raw).hexdigest()
        value['key_sha256'] = pin
        self.config.snapshot.write_text(json.dumps(value))
        with self.assertRaises(SourceError):
            self.load(replace(self.config, public_key_sha256=pin, signing_key_path=None))

    def test_consumer_cannot_collect_and_bad_signer_fails_before_network(self):
        getter = Mock()
        with self.assertRaises(ReceiptSignatureError):
            collect(replace(self.config, signing_key_path=None), getter=getter)
        getter.assert_not_called()
        self.public.write_bytes(b'x'*44)
        with self.assertRaises(ReceiptSignatureError):
            collect(self.config, getter=getter)
        getter.assert_not_called()

    def test_signing_failure_preserves_last_successful_receipt(self):
        self.config.snapshot.write_text('last-successful-receipt')
        self.private.write_bytes(b'invalid key')
        with patch('nexydao.sec.collect', return_value=self.payload), self.assertRaises(ReceiptSignatureError):
            run_source_check(self.config)
        self.assertEqual(self.config.snapshot.read_text(), 'last-successful-receipt')

    def test_collector_publishes_receipt_from_bounded_source_collection(self):
        getter = Mock(side_effect=self.fixture.getter)
        with patch('nexydao.sec.collect', side_effect=lambda config:
                   collect(config, getter, lambda: self.fixture.now, lambda _: None)):
            result = run_source_check(self.config)
        self.assertEqual(getter.call_count, 3)
        self.assertEqual(result['facts'], 2)
        self.assertEqual(len(self.load()), 2)
        self.assertFalse(result['execution_authorized'])

    def test_expiry_and_concept_scope_are_still_enforced(self):
        self.receipt()
        with self.assertRaisesRegex(SourceError, 'expired_research_receipt'):
            self.load(now=self.fixture.now+86400)
        with self.assertRaisesRegex(SourceError, 'concept_scope_mismatch'):
            self.load(replace(self.config, concepts=('Liabilities', 'NetIncomeLoss')))

    def test_tool_failure_is_sanitized(self):
        self.receipt()
        error = subprocess.CalledProcessError(1, 'openssl', stderr=b'private key material')
        with patch('nexydao.research_signatures.subprocess.run', side_effect=error):
            with self.assertRaisesRegex(SourceError, '^research_public_signature_rejected$'):
                self.load()

    def test_duplicate_receipt_keys_fail_before_crypto(self):
        self.receipt()
        raw = self.config.snapshot.read_text()
        self.config.snapshot.write_text('{"algorithm":"ed25519",'+raw[1:])
        with patch('nexydao.research_signatures.verify') as verifier, self.assertRaisesRegex(SourceError, 'duplicate_source_key'):
            self.load()
        verifier.assert_not_called()

    def test_environment_supports_public_only_configuration_without_hmac_key(self):
        env = {'NEXYDAO_RESEARCH_UNIVERSE': json.dumps([self.fixture.issuer]),
               'NEXYDAO_RESEARCH_RECEIPT_MODE': 'ed25519', 'NEXYDAO_RESEARCH_PUBLIC_KEY_FILE': str(self.public),
               'NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256': self.pin, 'NEXYDAO_OPENSSL_PATH': str(DEFAULT_OPENSSL)}
        with patch.dict(os.environ, env, clear=True):
            config = ResearchConfig.from_env()
        self.assertIsNone(config.key_path)
        self.assertIsNone(config.signing_key_path)
        self.assertEqual(config.receipt_mode, 'ed25519')
        with self.assertRaises(ValueError):
            replace(config, receipt_mode='auto')

    @unittest.skipUnless(os.name == 'posix', 'Unix permission enforcement')
    def test_shared_private_key_permissions_reject_before_collection(self):
        self.private.chmod(0o644)
        getter = Mock()
        with self.assertRaisesRegex(ReceiptSignatureError, 'key_permissions'):
            collect(self.config, getter=getter)
        getter.assert_not_called()
        self.private.chmod(0o600)
        alias = self.root/'public-alias.der'
        alias.symlink_to(self.public)
        with self.assertRaisesRegex(ReceiptSignatureError, 'key_unavailable'):
            collect(replace(self.config, public_key_path=alias), getter=getter)
        getter.assert_not_called()
        untrusted = self.root/'openssl'
        untrusted.write_text('untrusted executable');untrusted.chmod(0o755)
        with self.assertRaisesRegex(ReceiptSignatureError, 'protected_openssl_required'):
            _command(untrusted, ['version'])
