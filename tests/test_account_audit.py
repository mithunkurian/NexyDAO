import copy
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from nexydao.account_audit import collect_audit, load_audit, report, validate_summary
from nexydao.ibkr import BrokerConfig, ProbeError, TAGS


def snapshot():
    return {'schema_version': 1, 'source': 'ibkr_gateway_account_summary',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'protocol_version': 178,
            'account': 'DU123', 'paper_identity_evidence': 'single_DU_account_namespace',
            'expected_account_matched': True, 'execution_authorized': False,
            'values': [{'tag': tag, 'currency': 'USD', 'value': '1000000'} for tag in TAGS]}


class AccountAuditTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'data'
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.key = self.root / 'key'
        self.key.write_bytes(b'x' * 32)
        self.key.chmod(0o600)
        self.path = self.root / 'audit.json'
        self.config = BrokerConfig(expected_account='DU123')

    def test_signed_roundtrip_private_summary_not_reconciliation_or_funding(self):
        with patch('nexydao.account_audit.probe', return_value=snapshot()):
            result = collect_audit(self.config, self.key, self.path)
        reread = load_audit(self.config, self.key, self.path)
        self.assertFalse(reread['broker_reconciliation'])
        self.assertFalse(reread['broker_balances_imported'])
        self.assertFalse(reread['execution_authorized'])
        self.assertEqual(len(reread['missing_checks']), 4)
        for sensitive in ('DU123', '1000000'):
            self.assertNotIn(sensitive, json.dumps(result))

    def test_exact_pin_required_before_network(self):
        with patch('nexydao.account_audit.probe') as probe:
            with self.assertRaises(ProbeError): collect_audit(BrokerConfig(), self.key, self.path)
            probe.assert_not_called()
        with self.assertRaises(ProbeError): report(snapshot(), 'DU999')

    def test_expired_future_and_naive_times_fail(self):
        item = snapshot()
        for stamp in ('2020-01-01T00:00:00+00:00', '2999-01-01T00:00:00+00:00',
                      '2026-10-12T12:00:00', 'invalid'):
            item['retrieved_at'] = stamp
            with self.assertRaises(ProbeError): validate_summary(item, 'DU123')
        item = snapshot()
        stamp = datetime.fromisoformat(item['retrieved_at']).timestamp()
        with self.assertRaises(ProbeError): validate_summary(item, 'DU123', stamp + 60)

    def test_tampered_and_unsigned_snapshots_fail(self):
        with patch('nexydao.account_audit.probe', return_value=snapshot()):
            collect_audit(self.config, self.key, self.path)
        receipt = json.loads(self.path.read_text())
        receipt['payload']['snapshot']['values'][0]['value'] = '9000000'
        self.path.write_text(json.dumps(receipt))
        with self.assertRaises(ProbeError): load_audit(self.config, self.key, self.path)
        self.path.write_text(json.dumps(snapshot()))
        with self.assertRaises(ProbeError): load_audit(self.config, self.key, self.path)

    def test_duplicate_missing_oversized_and_nonfinite_values_fail(self):
        for mode in ('duplicate', 'missing', 'NaN', 'huge', 'matched_flag', 'execution_flag'):
            item = snapshot()
            if mode == 'duplicate': item['values'].append(copy.deepcopy(item['values'][0]))
            elif mode == 'missing': item['values'].pop()
            elif mode == 'NaN': item['values'][0]['value'] = 'NaN'
            elif mode == 'huge': item['values'][0]['value'] = '1' * 100
            elif mode == 'matched_flag': item['expected_account_matched'] = 1
            else: item['execution_authorized'] = 0
            with self.subTest(mode=mode), self.assertRaises(ProbeError): report(item, 'DU123')

    def test_currency_and_negative_cash_are_not_hidden(self):
        item = snapshot()
        for row in item['values']: row['currency'] = 'SEK'
        item['values'][0]['value'] = '-1'
        result = report(item, 'DU123')
        self.assertFalse(result['usd_summary_complete'])
        self.assertTrue(result['negative_balance_observed'])
        self.assertFalse(result['execution_authorized'])

    def test_failed_collection_preserves_previous_receipt(self):
        self.path.write_text('previous')
        with patch('nexydao.account_audit.probe', side_effect=ProbeError('broker_timeout')):
            with self.assertRaises(ProbeError): collect_audit(self.config, self.key, self.path)
        self.assertEqual(self.path.read_text(), 'previous')

    def test_receipt_read_is_bounded(self):
        self.path.write_bytes(b'x' * 32769)
        with self.assertRaises(ProbeError): load_audit(self.config, self.key, self.path)
