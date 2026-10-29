import copy
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import test_research as research_fixtures
from nexydao.cli import DemoProvider, main
from nexydao.config import Config
from nexydao.owner_policy import BASE, load_policy
from nexydao.portfolio import Portfolio
from nexydao.provider import OpenAIProvider
from nexydao.records import PROPOSAL
from nexydao.revisions import prepare_revision
from nexydao.store import Store
from nexydao.workflow import run_cycle


class Advisory(DemoProvider):
    mode = 'ai'

    def __init__(self):
        self.calls = []

    def decide(self, run, role, instructions, context, schema):
        self.calls.append((role, copy.deepcopy(context)))
        return super().decide(run, role, instructions, context, schema)


class RevisionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]/'data'
        root.mkdir(exist_ok=True)
        folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)/'audit.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)

    def parent(self, evidence=None):
        return run_cycle(self.store, Advisory(), evidence or [])

    def test_revision_has_new_reviews_and_persistent_nonrecursive_link(self):
        parent = self.parent()
        previous = self.store.db.execute('select result from runs where id=?', (parent['run_id'],)).fetchone()[0]
        provider = Advisory()
        result = run_cycle(self.store, provider, [], revise_run=parent['run_id'])
        self.assertEqual(len(provider.calls), 6)
        self.assertEqual([r for r, _ in provider.calls], ['ceo', 'risk_capital', 'risk_evidence',
                                                        'committee_investment', 'committee_fiduciary', 'committee_audit'])
        self.assertEqual(result['revision']['depth'], 1)
        self.assertEqual(result['revision']['parent_run_id'], parent['run_id'])
        self.assertFalse(result['policy']['execution_authorized'])
        self.assertNotIn('revision_context', result)
        for _, context in provider.calls:
            self.assertEqual(context['revision_context']['verification'], 'unverified_historical_decision')
        self.assertEqual(provider.calls[1][1], provider.calls[2][1])
        self.assertEqual(previous, self.store.db.execute('select result from runs where id=?', (parent['run_id'],)).fetchone()[0])
        reopened = Store(self.path)
        try:
            self.assertEqual(prepare_revision(reopened, result['run_id'])[0]['depth'], 2)
            self.assertTrue(any(r['run_id'] == result['run_id'] for r in reopened.memory()))
        finally:
            reopened.close()

    def test_old_citation_cannot_be_reused_as_current_evidence(self):
        old = {'id': 'old-source', 'verification': 'unverified'}
        parent = self.parent([old])
        class Reuses(Advisory):
            def decide(self, *args):
                value = super().decide(*args)
                if args[-1] == PROPOSAL:
                    value['evidence_ids'] = ['old-source']
                return value
        provider = Reuses()
        with self.assertRaisesRegex(ValueError, 'unknown evidence'):
            run_cycle(self.store, provider, [], revise_run=parent['run_id'])
        self.assertEqual(len(provider.calls), 1)

    def test_invalid_parent_never_starts_a_run_or_calls_provider(self):
        demo = run_cycle(self.store, DemoProvider(), [])['run_id']
        running = self.store.start('ai')
        failed = self.store.start('ai')
        self.store.finish(failed, 'failed', {})
        before = self.store.db.execute('select count(*) from runs').fetchone()[0]
        provider = Advisory()
        for parent in ('invalid', '00000000-0000-0000-0000-000000000000', demo, running, failed):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                run_cycle(self.store, provider, [], revise_run=parent)
        self.assertEqual(self.store.db.execute('select count(*) from runs').fetchone()[0], before)
        self.assertEqual(provider.calls, [])

    def test_chain_depth_is_bounded_and_does_not_embed_ancestors(self):
        root = self.parent()['run_id']
        parent = root
        for depth in range(1, 4):
            result = run_cycle(self.store, Advisory(), [], revise_run=parent)
            self.assertEqual(result['revision']['root_run_id'], root)
            self.assertEqual(result['revision']['depth'], depth)
            self.assertEqual(set(result['revision']), {'root_run_id', 'parent_run_id', 'parent_result_sha256', 'depth'})
            parent = result['run_id']
        provider = Advisory()
        with self.assertRaisesRegex(ValueError, 'depth limit'):
            run_cycle(self.store, provider, [], revise_run=parent)
        self.assertEqual(provider.calls, [])

    def test_parent_change_during_review_fails_the_child(self):
        parent = self.parent()
        store = self.store
        class Changes(Advisory):
            def decide(self, *args):
                value = super().decide(*args)
                store.finish(parent['run_id'], 'completed', {**parent, 'prompt_version': -1})
                return value
        provider = Changes()
        with self.assertRaisesRegex(ValueError, 'parent changed'):
            run_cycle(self.store, provider, [], revise_run=parent['run_id'])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.store.db.execute("select count(*) from runs where status='failed'").fetchone()[0], 1)

    def test_cannot_downgrade_nine_stage_parent_and_research_context_is_independent(self):
        fixtures = research_fixtures.ResearchTests()
        fixtures.setUp()
        self.addCleanup(fixtures.doCleanups)
        evidence = fixtures.receipt()
        parent = run_cycle(self.store, fixtures.provider(evidence), evidence, research=True, portfolio=True)
        for research, portfolio in ((False, False), (True, False), (False, True)):
            provider = fixtures.provider(evidence)
            with self.assertRaisesRegex(ValueError, 'repeat parent'):
                run_cycle(self.store, provider, evidence, research=research, portfolio=portfolio, revise_run=parent['run_id'])
            self.assertEqual(provider.calls, [])
        provider = fixtures.provider(evidence)
        result = run_cycle(self.store, provider, evidence, research=True, portfolio=True, revise_run=parent['run_id'])
        self.assertEqual(len(provider.calls), 9)
        self.assertEqual(provider.calls[0][1], provider.calls[1][1])
        self.assertIn('revision_context', provider.calls[0][1])
        self.assertFalse(result['policy']['execution_authorized'])

    def test_revision_uses_current_costs_and_portfolio_without_mutating_them(self):
        parent = self.parent()
        self.store.reserve('fixture', 'cost', 'test', Decimal('1'), Decimal('2'))
        ledger = Portfolio(self.store)
        before = ledger.snapshot()
        provider = Advisory()
        run_cycle(self.store, provider, [], revise_run=parent['run_id'])
        self.assertEqual(provider.calls[0][1]['account'], before)
        self.assertEqual(ledger.snapshot(), before)
        self.assertEqual(provider.calls[0][1]['api_costs']['calls'], 1)

    def test_corrupt_link_or_oversized_parent_is_rejected(self):
        root = self.parent()
        child = run_cycle(self.store, Advisory(), [], revise_run=root['run_id'])
        self.store.db.execute("update run_revisions set metadata='{}'")
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, 'audit link'):
            prepare_revision(self.store, child['run_id'])
        self.store.db.execute('update runs set result=? where id=?', ('x'*262145, root['run_id']))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, 'bounded completed'):
            prepare_revision(self.store, root['run_id'])

    def test_cli_rejects_revision_on_demo_before_opening_db(self):
        with patch('sys.argv', ['nexydao', 'demo', '--revise-run', 'anything']), \
                patch.dict(os.environ, {}, clear=True), patch('nexydao.cli.Store') as store, patch('sys.stderr'):
            with self.assertRaises(SystemExit):
                main()
            store.assert_not_called()

    def test_existing_database_adds_revision_table_without_losing_runs(self):
        parent = self.parent()
        self.store.db.execute('drop table run_revisions')
        self.store.db.commit()
        reopened = Store(self.path)
        try:
            self.assertEqual(prepare_revision(reopened, parent['run_id'])[0]['depth'], 1)
        finally:
            reopened.close()

    def test_failed_revision_retains_reported_api_cost(self):
        parent = self.parent()
        config = Config(self.path, 'test-model', 'placeholder', Decimal('1'), Decimal('1'), Decimal('1'))
        def transport(payload, key):
            value = DemoProvider().decide('', '', '', {}, PROPOSAL)
            value['evidence_ids'] = ['old-unsupported-source']
            return {'id': 'fixture', 'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 50},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
        with self.assertRaisesRegex(ValueError, 'unknown evidence'):
            run_cycle(self.store, OpenAIProvider(config, self.store, transport), [], revise_run=parent['run_id'])
        self.assertEqual(self.store.costs()['calls'], 1)
        self.assertEqual(self.store.costs()['unsettled_calls'], 0)
        self.assertEqual(Decimal(self.store.costs()['estimated_or_reserved_usd']), Decimal('0.00015'))

    def test_revision_uses_current_policy_instead_of_parent_policy(self):
        parent = self.parent()
        document = copy.deepcopy(BASE)
        document['policy_version'] = 2
        document['max_position_usd'] = '100'
        path = self.path.parent/'policy.json'
        path.write_text(json.dumps(document));path.chmod(0o600)
        policy = load_policy(path)
        provider = Advisory()
        child = run_cycle(self.store, provider, [], owner_policy=policy, revise_run=parent['run_id'])
        self.assertNotEqual(child['owner_policy_sha256'], parent['owner_policy_sha256'])
        self.assertEqual(provider.calls[0][1]['owner_policy']['max_position_usd'], '100')
