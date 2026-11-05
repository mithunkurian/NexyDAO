from datetime import datetime,timezone,timedelta
from contextlib import closing
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import sqlite3
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nexydao.audit_backups import create_backup
from nexydao.operations_health import operations_health,HealthError
from nexydao.store import Store


class OperationsHealthTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.path=self.root/'live.sqlite3';self.backup=self.root/'backup'
        self.store=Store(self.path);self.addCleanup(self.store.close);self.path.chmod(0o600)
        self.run=self.store.start()
        ticket=self.store.reserve(self.run,'private-role','fake',Decimal('.02'),Decimal('.10'))
        self.store.settle(ticket,Decimal('.01'),{},'private-response')
        self.store.event(self.run,'fixture',{'secret':'private narrative'})
        self.store.finish(self.run,'completed',{'private':'decision text'})
        self.now=int(time.time())+2;create_backup(self.path,self.backup)
        disk=patch('nexydao.operations_health.shutil.disk_usage',return_value=SimpleNamespace(free=1024*1024*1024))
        disk.start();self.addCleanup(disk.stop)

    def health(self,budget=Decimal('.10'),backup=True):
        return operations_health(self.path,budget,self.backup if backup else None,self.now)

    def codes(self,result):return {item['code'] for item in result['alerts']}

    def stamp(self,age):return datetime.fromtimestamp(self.now-age,timezone.utc).isoformat()

    def update_run(self,**fields):
        for column,value in fields.items():self.store.db.execute('UPDATE runs SET '+column+'=? WHERE id=?',(value,self.run))
        self.store.db.commit()

    def test_clean_report_is_read_only_and_grants_no_operational_authority(self):
        before=self.store.db.execute('SELECT * FROM runs').fetchall();costs=self.store.costs()
        result=self.health()
        self.assertTrue(result['local_health_checks_passed']);self.assertEqual(result['alerts'],[])
        self.assertTrue(result['backup_verified']);self.assertTrue(result['backup_matches_observed_database'])
        self.assertEqual(result['remaining_api_budget_usd'],'0.09');self.assertEqual(result['latest_ai_run_status'],'completed')
        for key in ('database_modified','reservations_released','recurring_automation_enabled','alert_delivery_performed',
                'operational_readiness_verified','scheduling_authorized','execution_authorized'):self.assertFalse(result[key])
        self.assertEqual(costs,self.store.costs());self.assertEqual(before,self.store.db.execute('SELECT * FROM runs').fetchall())
        text=json.dumps(result)
        for sensitive in ('private narrative','decision text','private-response','private-role',self.run,'live.sqlite3'):
            self.assertNotIn(sensitive,text)

    def test_stale_running_boundary_is_critical_but_does_not_mark_failed_or_retry(self):
        self.update_run(status='running',created=self.stamp(1200))
        result=self.health();self.assertFalse(result['local_health_checks_passed'])
        self.assertEqual(result['long_running_run_count'],1);self.assertIn('long_running_runs_require_review',self.codes(result))
        self.assertEqual(self.store.db.execute('SELECT status FROM runs').fetchone()[0],'running')

    def test_young_running_run_and_inflight_reservation_are_warnings_not_failures(self):
        self.update_run(status='running',created=self.stamp(1199))
        self.store.reserve(self.run,'active','fake',Decimal('.01'),Decimal('.10'))
        self.store.db.execute("UPDATE costs SET created=? WHERE status='reserved'",(self.stamp(119),));self.store.db.commit()
        result=self.health();self.assertTrue(result['local_health_checks_passed'])
        self.assertIn('active_runs_observed',self.codes(result));self.assertIn('active_api_reservations_retained',self.codes(result))

    def test_aged_uncertain_cost_boundary_is_critical_and_money_is_retained(self):
        self.update_run(status='running');self.store.reserve(self.run,'uncertain','fake',Decimal('.03'),Decimal('.10'))
        self.store.db.execute("UPDATE costs SET created=? WHERE status='reserved'",(self.stamp(120),));self.store.db.commit()
        before=self.store.costs();result=self.health()
        self.assertEqual(result['aged_api_reservation_count'],1);self.assertFalse(result['local_health_checks_passed'])
        self.assertEqual(before,self.store.costs());self.assertEqual(before['unsettled_calls'],1)

    def test_finished_run_with_young_unsettled_cost_is_still_critical(self):
        self.store.reserve(self.run,'uncertain','fake',Decimal('.01'),Decimal('.10'))
        result=self.health();self.assertEqual(result['uncertain_costs_on_finished_runs_count'],1)
        self.assertEqual(result['aged_api_reservation_count'],0)
        self.assertIn('finished_runs_have_uncertain_api_costs',self.codes(result))

    def test_budget_near_boundary_exhaustion_and_overrun_do_not_reset_charges(self):
        result=self.health(Decimal('.011'));self.assertTrue(result['local_health_checks_passed'])
        self.assertIn('lifetime_api_budget_near_limit',self.codes(result))
        for cap in (Decimal('.01'),Decimal('.005')):
            result=self.health(cap);self.assertFalse(result['local_health_checks_passed'])
            self.assertEqual(result['remaining_api_budget_usd'],'0');self.assertIn('lifetime_api_budget_exhausted',self.codes(result))
        self.assertEqual(self.store.costs()['estimated_or_reserved_usd'],'0.01')

    def test_new_demo_success_cannot_hide_failed_ai_run(self):
        self.update_run(status='failed',created=self.stamp(10))
        demo=self.store.start('demo');self.store.finish(demo,'completed',{})
        result=self.health();self.assertEqual(result['latest_ai_run_status'],'failed')
        self.assertIn('latest_ai_run_failed',self.codes(result));self.assertFalse(result['local_health_checks_passed'])

    def test_equal_ai_creation_times_with_conflicting_states_are_ambiguous(self):
        stamp=self.stamp(10);self.update_run(created=stamp)
        failed=self.store.start();self.store.finish(failed,'failed',{})
        self.store.db.execute('UPDATE runs SET created=? WHERE id=?',(stamp,failed));self.store.db.commit()
        result=self.health();self.assertEqual(result['latest_ai_run_status'],'ambiguous')
        self.assertIn('latest_ai_run_order_ambiguous',self.codes(result))

    def test_old_or_absent_ai_completion_is_explicit_but_not_fake_live_acceptance(self):
        self.update_run(created=self.stamp(86400))
        self.assertIn('no_recent_ai_completion',self.codes(self.health()))
        self.update_run(mode='demo')
        result=self.health();self.assertIn('no_completed_ai_run_observed',self.codes(result))
        self.assertIsNone(result['latest_ai_run_status']);self.assertFalse(result['operational_readiness_verified'])

    def test_backup_missing_corrupt_future_and_exact_age_boundary_raise_local_alerts(self):
        self.assertIn('verified_backup_not_supplied',self.codes(self.health(backup=False)))
        manifest=self.backup/'manifest.json';raw=manifest.read_bytes();data=json.loads(raw)
        for created,code in ((self.now+1,'backup_timestamp_in_future'),(self.now-86400,'verified_backup_too_old')):
            data['created_at']=created;manifest.write_text(json.dumps(data))
            result=self.health();self.assertIn(code,self.codes(result));self.assertFalse(result['local_health_checks_passed'])
        manifest.write_bytes(b'broken')
        result=self.health();self.assertIn('backup_verification_failed',self.codes(result));self.assertFalse(result['backup_verified'])
        self.assertIsNone(result['backup_matches_observed_database'])

    def test_changed_existing_content_is_detected_despite_identical_audit_counts(self):
        original=self.health();self.store.db.execute("UPDATE events SET payload='{}'");self.store.db.commit()
        result=self.health();self.assertEqual(original['audit'],result['audit'])
        self.assertNotEqual(original['audit_content_sha256'],result['audit_content_sha256'])
        self.assertFalse(result['backup_matches_observed_database'])
        self.assertIn('backup_content_differs_from_observed_database',self.codes(result))

    def test_inspection_database_is_reported_stopped_without_runtime_open(self):
        result=operations_health(self.backup/'snapshot.sqlite3',Decimal('.10'),self.backup,self.now)
        self.assertTrue(result['inspection_copy_detected']);self.assertFalse(result['local_health_checks_passed'])
        self.assertTrue(result['backup_matches_observed_database']);self.assertIn('inspection_copy_cannot_resume',self.codes(result))

    def test_low_disk_free_space_is_critical_at_fixed_bound(self):
        with patch('nexydao.operations_health.shutil.disk_usage',return_value=SimpleNamespace(free=128*1024*1024-1)):
            self.assertIn('database_volume_free_space_low',self.codes(self.health()))
        with patch('nexydao.operations_health.shutil.disk_usage',return_value=SimpleNamespace(free=128*1024*1024)):
            self.assertNotIn('database_volume_free_space_low',self.codes(self.health()))

    def test_missing_source_or_bad_records_fail_without_creating_or_repairing_a_ledger(self):
        missing=self.root/'missing.sqlite3'
        with self.assertRaises(HealthError):operations_health(missing,Decimal('.10'),self.backup,self.now)
        self.assertFalse(missing.exists())
        for values in ({'created':'naive'},{'created':datetime.fromtimestamp(self.now+1,timezone.utc).isoformat()},
                       {'created':'2026-11-05T10:00:00'},{'status':'unknown'},{'mode':'unknown'}):
            self.update_run(created=self.stamp(1),status='completed',mode='ai')
            self.update_run(**values)
            with self.subTest(values=values),self.assertRaises(HealthError):self.health()

    def test_budget_and_clock_types_and_unbounded_record_content_are_rejected(self):
        for budget in (True,'0.1',Decimal('NaN'),Decimal('0'),Decimal('1E-1000000')):
            with self.assertRaises(HealthError):self.health(budget)
        with self.assertRaises(HealthError):operations_health(self.path,Decimal('.1'),self.backup,float('nan'))
        self.store.db.execute("UPDATE events SET payload=?",('x'*(1024*1024+1),));self.store.db.commit()
        with self.assertRaisesRegex(HealthError,'record_size'):self.health()

    def test_database_snapshot_stays_consistent_when_another_writer_commits_during_report(self):
        from nexydao.audit_backups import _audit
        changed=[False]
        def audit_then_write(connection):
            result=_audit(connection)
            if not changed[0]:
                changed[0]=True;self.store.event(self.run,'concurrent',{})
            return result
        with patch('nexydao.operations_health.backups._audit',side_effect=audit_then_write):result=self.health()
        self.assertEqual(result['audit']['table_row_counts']['events'],1)
        self.assertTrue(result['backup_matches_observed_database'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0],2)

    def test_cli_health_exit_codes_and_no_store_provider_or_socket_access(self):
        from nexydao.cli import main
        environment={'NEXYDAO_DB':str(self.path),'NEXYDAO_API_BUDGET_USD':'0.1'}
        for missing in (False,True):
            arguments=['nexydao','operations-health']+([] if missing else ['--backup-dir',str(self.backup)])
            output=io.StringIO()
            with patch.dict(os.environ,environment,clear=True),patch('sys.argv',arguments),patch('sys.stdout',output), \
                    patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider,patch('socket.create_connection') as connect:
                if missing:
                    with self.assertRaises(SystemExit) as error:main()
                    self.assertEqual(error.exception.code,1)
                else:main()
            for operation in (store,provider,connect):operation.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['local_health_checks_passed'],not missing)

    def test_cli_health_rejects_workflow_or_restore_modifiers(self):
        from nexydao.cli import main
        for modifier in (['--with-research'],['--restore-dir',str(self.root/'new')],['--before-state',str(self.path)]):
            with patch.dict(os.environ,{'NEXYDAO_DB':str(self.path)},clear=True), \
                    patch('sys.argv',['nexydao','operations-health',*modifier]),patch('sys.stderr'),self.assertRaises(SystemExit):main()

    def test_partially_consumed_simulation_hold_stays_audited_and_unchanged(self):
        from test_audit_backups import AuditBackupTests
        ledger=AuditBackupTests.portfolio(self);before=ledger.snapshot()
        self.backup=self.root/'portfolio-backup';create_backup(self.path,self.backup)
        result=self.health();self.assertEqual(result['audit']['active_simulation_hold_count'],1)
        self.assertEqual(result['audit']['portfolio_revision'],before['revision'])
        self.assertTrue(result['backup_matches_observed_database']);self.assertEqual(before,ledger.snapshot())

    def test_latest_ai_selection_uses_actual_time_instead_of_lexical_offset_order(self):
        self.update_run(created=datetime.fromtimestamp(self.now-20,timezone(timedelta(hours=2))).isoformat())
        failed=self.store.start();self.store.finish(failed,'failed',{})
        self.store.db.execute('UPDATE runs SET created=? WHERE id=?',(self.stamp(10),failed));self.store.db.commit()
        self.assertEqual(self.health()['latest_ai_run_status'],'failed')

    def test_backup_changing_during_extra_content_reads_is_not_reported_verified(self):
        from nexydao.operations_health import _fingerprint
        calls=[0]
        def fingerprint_then_change(*args):
            result=_fingerprint(*args);calls[0]+=1
            if calls[0]==2:
                with closing(sqlite3.connect(self.backup/'snapshot.sqlite3')) as writer:
                    writer.execute("UPDATE events SET payload='{}'");writer.commit()
            return result
        with patch('nexydao.operations_health._fingerprint',side_effect=fingerprint_then_change):result=self.health()
        self.assertFalse(result['backup_verified']);self.assertIsNone(result['backup_matches_observed_database'])
        self.assertIn('backup_verification_failed',self.codes(result))

    def test_oversized_schema_text_is_rejected_before_fingerprint_serialization(self):
        self.store.db.execute('CREATE TABLE funding_reviews (id TEXT /*'+'x'*17000+'*/)')
        self.store.db.commit()
        with self.assertRaisesRegex(HealthError,'schema_size'):self.health()
