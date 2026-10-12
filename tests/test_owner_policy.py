import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexydao.cli import DemoProvider, main
from nexydao.owner_policy import BASE, OwnerPolicyError, load_policy, cash_preflight
from nexydao.safety import evaluate
from nexydao.store import Store
from nexydao.workflow import run_cycle


class OwnerTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]/'data'
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.path = self.root/'policy.json'
        self.document = copy.deepcopy(BASE)

    def policy(self):
        self.path.write_text(json.dumps(self.document))
        self.path.chmod(0o600)
        return load_policy(self.path)

    def test_mandatory_four_rules_cannot_be_relaxed(self):
        for key, value in [('no_short_selling', False), ('no_leverage_or_borrowing', False),
                           ('legal_jurisdictions', ['US']), ('live_account_type', 'general'),
                           ('live_account_country', 'US'), ('max_position_usd', '1000'),
                           ('min_cash_reserve_usd', '3999')]:
            self.document = copy.deepcopy(BASE)
            self.document[key] = value
            with self.assertRaises(OwnerPolicyError): self.policy()

    def test_unknown_fields_duplicate_keys_and_bad_limits_fail_closed(self):
        for text in ('{"schema_version":1,"schema_version":1}',
                     json.dumps({**BASE, 'execution_enabled': True}), 'x'*16001):
            self.path.write_text(text)
            with self.assertRaises((OwnerPolicyError, ValueError)): load_policy(self.path)
        self.document['max_position_usd'] = 'NaN'
        with self.assertRaises(OwnerPolicyError): self.policy()

    def test_owner_can_add_rules_block_symbols_and_tighten_limits(self):
        self.document.update(policy_version=2, blocked_symbols=['TEST'], max_position_usd='100',
                             min_cash_reserve_usd='4900', additional_rules=[{'id': 'new-rule', 'text': 'Avoid tobacco exposure.'}])
        policy = self.policy()
        proposal = {'action': 'propose_investment', 'symbol': 'TEST', 'allocation_usd': 200, 'evidence_ids': ['fact']}
        result = evaluate(proposal, [{'verdict': 'pass'}]*2, [{'vote': 'approve'}]*3, policy)
        self.assertFalse(result['execution_authorized'])
        for reason in ('owner_blocked_symbol', 'owner_position_limit_exceeded', 'owner_cash_reserve_breached',
                       'additional_owner_rule_enforcement_pending', 'independent_legal_compliance_not_verified',
                       'live_swedish_isk_eligibility_not_verified'):
            self.assertIn(reason, result['reasons'])

    def test_context_copy_cannot_change_authoritative_policy(self):
        policy = load_policy()
        copied = policy.document()
        copied['no_short_selling'] = False
        self.assertTrue(policy.document()['no_short_selling'])
        with self.assertRaises(Exception): policy.payload = b'changed'

    def test_all_six_roles_get_owner_policy_and_results_are_audited(self):
        policy = self.policy()
        seen = []
        class Capture(DemoProvider):
            def decide(inner, run, role, instructions, context, spec):
                seen.append(role)
                self.assertIn('MANDATORY OWNER POLICY', instructions)
                self.assertTrue(context['owner_policy']['no_leverage_or_borrowing'])
                self.assertEqual(context['owner_policy_sha256'], policy.digest)
                return super().decide(run, role, instructions, context, spec)
        store = Store(self.root/'audit.sqlite3')
        self.addCleanup(store.close)
        result = run_cycle(store, Capture(), [], owner_policy=policy)
        self.assertEqual(len(seen), 6)
        self.assertEqual(result['owner_policy_sha256'], policy.digest)
        self.assertEqual(result['owner_policy_version'], 1)

    def test_policy_change_between_calls_stops_before_next_agent(self):
        policy = self.policy()
        calls = []
        class Change(DemoProvider):
            def decide(inner, *args):
                calls.append(1)
                self.document['policy_version'] = 2
                self.path.write_text(json.dumps(self.document))
                return super().decide(*args)
        store = Store(self.root/'failed.sqlite3')
        self.addCleanup(store.close)
        with self.assertRaisesRegex(OwnerPolicyError, 'changed_during_cycle'):
            run_cycle(store, Change(), [], owner_policy=policy)
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.db.execute('SELECT status FROM runs').fetchone()[0], 'failed')

    def test_missing_configured_file_blocks_provider_and_database(self):
        with patch.dict(os.environ, {'NEXYDAO_OWNER_POLICY_FILE': str(self.root/'missing')}, clear=True), \
                patch('sys.argv', ['nexydao', 'deliberate']), patch('nexydao.cli.Store') as store, \
                patch('nexydao.cli.OpenAIProvider') as provider, patch('sys.stderr'):
            with self.assertRaises(SystemExit): main()
            store.assert_not_called()
            provider.assert_not_called()

    def cash(self, **changes):
        state = dict(side='buy', quantity='1', limit_price='100', fees='1', held_quantity='2',
                     settled_cash='200', borrowed_cash='0', exposure_kind='unleveraged_long', currency='USD', cash_currency='USD')
        state.update(changes)
        return cash_preflight(**state)

    def test_short_borrowed_leveraged_and_unfunded_cash_intents_rejected(self):
        cases = [({'side':'sell','quantity':'3'}, 'owner_no_short_selling'),
                 ({'borrowed_cash':'1'}, 'owner_no_leverage_or_borrowing'),
                 ({'exposure_kind':'leveraged_etf'}, 'owner_no_leverage_or_borrowing'),
                 ({'quantity':'2'}, 'owner_cash_funding_required'),
                 ({'cash_currency':'SEK'}, 'verified_same_currency_cash_required')]
        for changes, reason in cases:
            result = self.cash(**changes)
            self.assertFalse(result['execution_authorized'])
            self.assertIn(reason, result['reasons'])
        self.assertFalse(self.cash()['execution_authorized'])
        self.assertIn('legal_and_isk_verification_required', self.cash()['reasons'])

    def test_cash_input_cannot_use_nan_negative_or_boolean(self):
        for value in ('NaN', '-1', True):
            self.assertIn('invalid_cash_state', self.cash(quantity=value)['reasons'])


if __name__ == '__main__': unittest.main()
