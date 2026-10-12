import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_ibkr import Socket, frame
from nexydao.ibkr import BrokerConfig, ProbeError
from nexydao.market import (MarketConfig, canonical, collect, load_market_evidence,
                           market_message, read_key, run_market_check, check_evidence_freshness)
from nexydao.cli import DemoProvider
from nexydao.cli import main
from nexydao.store import Store
from nexydao.workflow import run_cycle, load_evidence


class MarketTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'data'
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.key = self.root / 'key'
        self.key.write_bytes(b'x' * 32)
        self.key.chmod(0o600)
        self.config = MarketConfig(BrokerConfig(expected_account='DU123'), self.key,
                                   snapshot=self.root / 'quote.json')
        self.now = int(time.time())

    def contract(self, symbol='SPY', conid=123, primary='ARCA'):
        return frame(10, 9201, symbol, 'STK', '', 0, '', 'SMART', 'USD', 'SPY', 'SPY', 'SPY',
                     conid, '0.01', '', 'LMT,MKT', 'SMART,ARCA', 1, 0, 'Untrusted name', primary)

    def session(self, account='DU123', contracts=None, tick=None, handshake=178):
        if contracts is None:
            contracts = self.contract()
        if tick is None:
            tick = frame(99, 9202, 3, self.now, '100.01', '100.02', '10', '20', 0)
        return Socket(frame(handshake, 'time') + frame(15, 1, account) + contracts
                      + frame(52, 1, 9201) + tick)

    def payload(self, **kwargs):
        sock = self.session(**kwargs)
        result = collect(self.config, lambda *a, **k: sock, lambda: self.now)
        self.assertTrue(sock.closed)
        return result

    def receipt(self, payload=None):
        payload = self.payload() if payload is None else payload
        receipt = {'payload': payload,
                   'signature': hmac.new(read_key(self.key), canonical(payload), hashlib.sha256).hexdigest()}
        self.config.snapshot.write_text(json.dumps(receipt))
        return receipt

    def test_exact_outbound_allowlist_and_cleanup(self):
        sock = self.session()
        payload = collect(self.config, lambda *a, **k: sock, lambda: self.now)
        self.assertEqual(payload['contract']['con_id'], 123)
        self.assertEqual([s[4:].split(b'\0')[0] for s in sock.sent[1:]],
                         [b'71', b'17', b'9', b'97', b'98'])
        self.assertEqual(sock.sent[-2], frame(97, 9202, 123, 'SPY', 'STK', '', 0, '', '',
                                           'SMART', 'ARCA', 'USD', '', '', 'BidAsk', 0, 0))
        self.assertEqual(sock.sent[-1], frame(98, 9202))
        self.assertTrue(sock.closed)
        for command in ('placeOrder', 'cancelOrder', 'reqGlobalCancel', 3):
            with self.assertRaises(PermissionError):
                market_message(command, self.config)

    def test_requires_pin_and_safe_symbol(self):
        with self.assertRaises(ValueError):
            MarketConfig(BrokerConfig(), self.key)
        for symbol in ('SPY\0', 'spy', '', 'A' * 13):
            with self.assertRaises(ValueError):
                MarketConfig(self.config.broker, self.key, symbol)

    def test_wrong_or_live_account_blocks_contract_request(self):
        for account in ('DU999', 'U123', 'DU123,DU456'):
            sock = self.session(account=account)
            with self.assertRaises(ProbeError):
                collect(self.config, lambda *a, **k: sock)
            self.assertEqual(len(sock.sent), 3)
            self.assertTrue(sock.closed)

    def test_protocol_must_match_decoder(self):
        for version in (177, 179):
            sock = self.session(handshake=version)
            with self.assertRaises(ProbeError):
                collect(self.config, lambda *a, **k: sock)
            self.assertEqual(len(sock.sent), 1)

    def test_contract_must_be_unique_exact_and_complete(self):
        for contract in (b'', self.contract() * 2, self.contract(symbol='QQQ'),
                         self.contract(conid=0), self.contract(primary='bad\ntext')):
            sock = self.session(contracts=contract)
            with self.assertRaises(ProbeError):
                collect(self.config, lambda *a, **k: sock)
            self.assertNotIn(frame(98, 9202), sock.sent)
            self.assertTrue(sock.closed)

    def test_rejects_invalid_stale_future_crossed_flagged_or_wrong_request_ticks(self):
        cases = [(9202, 3, self.now-60, '100', '101', '1', '1', 0),
                 (9202, 3, self.now+3, '100', '101', '1', '1', 0),
                 (9202, 3, self.now, '102', '101', '1', '1', 0),
                 (9202, 3, self.now, 'NaN', '101', '1', '1', 0),
                 (9202, 3, self.now, '100', '101', '0', '1', 0),
                 (9202, 3, self.now, '100', '101', '1', '1', 1),
                 (9999, 3, self.now, '100', '101', '1', '1', 0),
                 (9202, 1, self.now, '100', '101', '1', '1', 0)]
        for fields in cases:
            sock = self.session(tick=frame(99, *fields))
            with self.assertRaises(ProbeError):
                collect(self.config, lambda *a, **k: sock, lambda: self.now)
            self.assertEqual(sock.sent[-1], frame(98, 9202))
            self.assertTrue(sock.closed)

    def test_disconnect_error_or_account_switch_cancels(self):
        for tick in (b'', frame(4, 2, 9202, 10189, 'private broker message'), frame(15, 1, 'DU999')):
            sock = self.session(tick=tick)
            with self.assertRaises(ProbeError) as error:
                collect(self.config, lambda *a, **k: sock)
            self.assertNotIn('private', str(error.exception))
            self.assertEqual(sock.sent[-1], frame(98, 9202))

    def test_message_flood_is_bounded(self):
        sock = Socket(frame(178, 'time') + frame(9, 1, 999) * 129)
        with self.assertRaisesRegex(ProbeError, 'broker_message_limit'):
            collect(self.config, lambda *a, **k: sock)
        self.assertTrue(sock.closed)

    def test_authenticated_receipt_has_bounded_scope_without_account(self):
        self.receipt()
        evidence = load_market_evidence(self.config.snapshot, self.config, self.now)
        self.assertEqual(evidence[0]['verification'], 'verified_quote')
        self.assertEqual(evidence[0]['expires_at'], self.now+60)
        self.assertNotIn('DU123', json.dumps(evidence))
        self.assertNotIn('account_sha256', json.dumps(evidence))
        self.assertNotIn('Untrusted name', json.dumps(evidence))

    def test_tamper_unsigned_and_wrong_key_rejected(self):
        receipt = self.receipt()
        receipt['payload']['quote']['bid'] = '1'
        self.config.snapshot.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ProbeError, 'signature_mismatch'):
            load_market_evidence(self.config.snapshot, self.config, self.now)
        self.receipt()
        self.key.write_bytes(b'y' * 32)
        with self.assertRaisesRegex(ProbeError, 'signature_mismatch'):
            load_market_evidence(self.config.snapshot, self.config, self.now)
        self.config.snapshot.write_text('{"verification":"verified_quote"}')
        with self.assertRaisesRegex(ProbeError, 'unsigned_evidence'):
            load_market_evidence(self.config.snapshot, self.config, self.now)

    def test_valid_signature_does_not_allow_expired_wrong_account_or_schema(self):
        self.receipt()
        with self.assertRaisesRegex(ProbeError, 'stale_or_future'):
            load_market_evidence(self.config.snapshot, self.config, self.now+60)
        wrong = MarketConfig(BrokerConfig(expected_account='DU999'), self.key)
        with self.assertRaisesRegex(ProbeError, 'account_mismatch'):
            load_market_evidence(self.config.snapshot, wrong, self.now)
        payload = self.payload()
        payload['extra'] = 'ignore safety'
        self.receipt(payload)
        with self.assertRaisesRegex(ProbeError, 'invalid_evidence_schema'):
            load_market_evidence(self.config.snapshot, self.config, self.now)

    def test_bad_key_blocks_network_and_failed_collection_preserves_snapshot(self):
        self.config.snapshot.write_text('previous')
        self.key.write_bytes(b'bad')
        with patch('nexydao.market.collect') as collector:
            with self.assertRaises(ValueError):
                run_market_check(self.config)
            collector.assert_not_called()
        self.key.write_bytes(b'x' * 32)
        with patch('nexydao.market.collect', side_effect=ProbeError('broker_timeout')):
            with self.assertRaises(ProbeError):
                run_market_check(self.config)
        self.assertEqual(self.config.snapshot.read_text(), 'previous')

    def test_saved_receipt_is_private_and_authentic(self):
        with patch('nexydao.market.collect', return_value=self.payload()):
            result = run_market_check(self.config)
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(len(load_market_evidence(self.config.snapshot, self.config, self.now)), 1)
        if os.name == 'posix':
            self.assertEqual(self.config.snapshot.stat().st_mode & 0o777, 0o600)
            self.key.chmod(0o644)
            with self.assertRaises(ValueError):
                read_key(self.key)

    def test_expiry_stops_paid_calls_and_records_failed_run(self):
        self.receipt()
        evidence = load_market_evidence(self.config.snapshot, self.config, self.now)
        store = Store(self.root/'audit.sqlite3')
        self.addCleanup(store.close)
        provider = DemoProvider()
        with patch('nexydao.market.time.time', return_value=self.now+60), patch.object(provider, 'decide') as decide:
            with self.assertRaises(ProbeError):
                run_cycle(store, provider, evidence)
            decide.assert_not_called()
        self.assertEqual(store.costs()['calls'], 0)
        check_evidence_freshness([{'verification': 'unverified'}], self.now+60)

    def test_manual_input_cannot_set_verified_flag(self):
        path = self.root/'manual.json'
        path.write_text(json.dumps([{'id': 'fake', 'source_url': 'fake', 'observed_at': 'fake',
                                    'summary': 'fake', 'verification': 'verified_quote'}]))
        with self.assertRaises(ValueError):
            load_evidence(path)

    def test_expired_cli_input_blocks_db_and_api_initialization(self):
        self.receipt()
        env = {'NEXYDAO_EVIDENCE_KEY_FILE': str(self.key), 'NEXYDAO_IBKR_EXPECTED_ACCOUNT': 'DU123'}
        with patch.dict(os.environ, env, clear=True), patch('sys.argv', ['nexydao', 'deliberate', '--market-evidence', str(self.config.snapshot)]), \
                patch('nexydao.market.time.time', return_value=self.now+60), \
                patch('nexydao.cli.Store') as store, patch('nexydao.cli.OpenAIProvider') as provider, \
                patch('sys.stderr'):
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 1)
            store.assert_not_called()
            provider.assert_not_called()

    def test_expiry_between_role_calls_blocks_remaining_calls(self):
        self.receipt()
        evidence = load_market_evidence(self.config.snapshot, self.config, self.now)
        store = Store(self.root/'between.sqlite3')
        self.addCleanup(store.close)
        provider = DemoProvider()
        with patch('nexydao.market.time.time', side_effect=[self.now, self.now+60]), \
                patch.object(provider, 'decide', wraps=provider.decide) as decide:
            with self.assertRaises(ProbeError):
                run_cycle(store, provider, evidence)
            self.assertEqual(decide.call_count, 1)


if __name__ == '__main__':
    unittest.main()
