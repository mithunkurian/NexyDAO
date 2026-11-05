from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nexydao import audit_backups as backups
from nexydao.maintenance_jobs import MaintenanceJobs,JobError,validate_plan,decode_plan
from nexydao.store import Store


class MaintenanceJobTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.archives=self.root/'archives';self.archives.mkdir(mode=0o700)
        self.source=self.root/'live.sqlite3';self.store=Store(self.source);self.addCleanup(self.store.close);self.source.chmod(0o600)
        self.run=self.store.start();self.store.finish(self.run,'completed',{})
        self.plan={'source_db':str(self.source),'backup_root':str(self.archives),'api_budget_usd':'0.10',
                   'interval_seconds':60,'max_attempts':10,'max_backup_bytes':256*1024*1024}
        self.clock=[int(time.time())];self.path=self.root/'jobs.sqlite3'
        self.jobs=MaintenanceJobs(self.path,lambda:self.clock[0]);self.jobs.initialize(self.plan)
        disk=patch('nexydao.maintenance_jobs.shutil.disk_usage',return_value=SimpleNamespace(free=1024*1024*1024))
        disk.start();self.addCleanup(disk.stop)

    def arm(self):return self.jobs.arm(self.plan)

    def test_initialization_is_stopped_and_does_not_create_a_source_or_archive(self):
        self.assertFalse(self.jobs.status()['enabled']);self.assertFalse(self.jobs.tick(self.plan)['work_started'])
        self.assertEqual(list(self.archives.iterdir()),[])
        before=self.path.read_bytes()
        with self.assertRaises(FileExistsError):self.jobs.initialize(self.plan)
        self.assertEqual(before,self.path.read_bytes())

    def test_one_tick_creates_verified_archive_and_retains_live_costs_and_state(self):
        self.arm();before=self.store.costs();result=self.jobs.tick(self.plan)
        self.assertTrue(result['maintenance_passed']);self.assertEqual(result['attempt_count'],1)
        self.assertEqual(result['incomplete_attempt_count'],0);self.assertEqual(before,self.store.costs())
        self.assertEqual(backups.verify_backup(self.archives/('job-'+result['attempt_id']))['audit']['api_call_records'],0)
        for key in ('recurring_automation_installed','paid_job_supported','alert_delivery_performed','execution_authorized'):
            self.assertFalse(result[key])
        self.assertNotIn(str(self.source),json.dumps(result))

    def test_cadence_is_persistent_across_instances_and_equal_due_time_is_allowed(self):
        self.arm();self.jobs.tick(self.plan)
        reopened=MaintenanceJobs(self.path,lambda:self.clock[0])
        self.clock[0]+=59;self.assertFalse(reopened.tick(self.plan)['work_started'])
        self.clock[0]+=1;self.assertTrue(reopened.tick(self.plan)['maintenance_passed'])
        self.assertEqual(reopened.status()['attempt_count'],2)

    def test_concurrent_tick_cannot_overlap_or_disarm_a_legitimate_running_attempt(self):
        self.arm();entered=threading.Event();release=threading.Event();create=backups.create_backup
        def blocked(*args):
            entered.set();self.assertTrue(release.wait(5));return create(*args)
        with patch('nexydao.maintenance_jobs.backups.create_backup',side_effect=blocked),ThreadPoolExecutor(1) as pool:
            first=pool.submit(self.jobs.tick,self.plan)
            try:
                self.assertTrue(entered.wait(5));second=MaintenanceJobs(self.path,lambda:self.clock[0]).tick(self.plan)
                self.assertFalse(second['work_started']);self.assertTrue(second['blocked_by_incomplete_attempt'])
            finally:release.set()
            self.assertTrue(first.result(timeout=10)['maintenance_passed'])
        self.assertTrue(self.jobs.status()['enabled']);self.assertEqual(self.jobs.status()['attempt_count'],1)

    def test_process_interruption_retains_claim_and_blocks_retry_after_restart(self):
        self.arm()
        with patch('nexydao.maintenance_jobs.backups.create_backup',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            self.jobs.tick(self.plan)
        reopened=MaintenanceJobs(self.path,lambda:self.clock[0]);state=reopened.status()
        self.assertEqual(state['incomplete_attempt_count'],1);self.assertEqual(state['retained_or_reserved_backup_bytes'],backups.MAX_DB)
        self.assertFalse(reopened.tick(self.plan)['work_started'])
        with self.assertRaisesRegex(JobError,'requires_review'):reopened.arm(self.plan)

    def test_failure_stops_schedule_and_keeps_uncertain_capacity_without_secret_errors(self):
        self.arm()
        with patch('nexydao.maintenance_jobs.backups.create_backup',side_effect=OSError('private secret path')):result=self.jobs.tick(self.plan)
        self.assertFalse(result['enabled']);self.assertEqual(result['reason'],'attempt_failed')
        self.assertEqual(result['retained_or_reserved_backup_bytes'],backups.MAX_DB);self.assertNotIn('secret',json.dumps(result))
        with self.assertRaises(JobError):self.arm()
        self.assertFalse(self.jobs.tick(self.plan)['work_started'])

    def test_health_failure_retains_archive_and_source_uncertain_cost(self):
        self.store.reserve(self.run,'uncertain','fake',Decimal('.02'),Decimal('.10'));self.arm()
        result=self.jobs.tick(self.plan);self.assertFalse(result['maintenance_passed']);self.assertFalse(result['enabled'])
        self.assertGreater(result['critical_alert_count'],0);self.assertEqual(self.store.costs()['unsettled_calls'],1)
        self.assertTrue((self.archives/('job-'+result['attempt_id'])/'manifest.json').exists())

    def test_stop_during_work_does_not_get_undone_by_successful_completion(self):
        self.arm();create=backups.create_backup
        def stop_then_copy(*args):self.jobs.stop();return create(*args)
        with patch('nexydao.maintenance_jobs.backups.create_backup',side_effect=stop_then_copy):result=self.jobs.tick(self.plan)
        self.assertTrue(result['maintenance_passed']);self.assertFalse(result['enabled']);self.assertEqual(result['reason'],'owner_stopped')
        self.assertFalse(self.jobs.tick(self.plan)['work_started'])

    def test_attempt_cap_is_lifetime_and_not_reset_by_manual_rearm(self):
        plan={**self.plan,'max_attempts':1};path=self.root/'limited.sqlite3';jobs=MaintenanceJobs(path,lambda:self.clock[0])
        jobs.initialize(plan);jobs.arm(plan);jobs.tick(plan);self.clock[0]+=60
        result=jobs.tick(plan);self.assertEqual(result['reason'],'attempt_cap');self.assertFalse(result['work_started'])
        jobs.arm(plan);self.assertEqual(jobs.tick(plan)['reason'],'attempt_cap')

    def test_archive_cap_reserves_worst_case_before_work_and_does_not_delete_old_archives(self):
        plan={**self.plan,'max_backup_bytes':backups.MAX_DB};jobs=MaintenanceJobs(self.root/'small.sqlite3',lambda:self.clock[0])
        jobs.initialize(plan);jobs.arm(plan);jobs.tick(plan);self.clock[0]+=60
        result=jobs.tick(plan);self.assertEqual(result['reason'],'archive_cap');self.assertEqual(len(list(self.archives.iterdir())),1)

    def test_plan_change_or_backward_clock_stops_without_more_work(self):
        self.arm();changed={**self.plan,'interval_seconds':120}
        result=self.jobs.tick(changed);self.assertEqual(result['reason'],'plan_changed');self.assertEqual(result['attempt_count'],0)
        self.arm();self.jobs.tick(self.plan);self.clock[0]-=1
        self.assertEqual(self.jobs.tick(self.plan)['reason'],'clock_regressed')

    def test_low_archive_disk_space_stops_before_claim_or_copy(self):
        self.arm()
        with patch('nexydao.maintenance_jobs.shutil.disk_usage',return_value=SimpleNamespace(free=128*1024*1024)):
            result=self.jobs.tick(self.plan)
        self.assertEqual(result['reason'],'disk_space_low');self.assertEqual(result['attempt_count'],0)

    def test_missing_state_never_auto_initializes_and_malformed_state_cannot_dispatch(self):
        with self.assertRaises(FileNotFoundError):MaintenanceJobs(self.root/'missing.sqlite3').status()
        with closing(sqlite3.connect(self.path)) as db:db.execute("UPDATE control SET reason='untrusted secret'");db.commit()
        with self.assertRaisesRegex(JobError,'state_invalid'):self.jobs.tick(self.plan)
        self.assertEqual(list(self.archives.iterdir()),[])

    def test_plan_bounds_unknown_commands_duplicates_and_bad_clocks_fail(self):
        for change in ({'interval_seconds':True},{'max_attempts':101},{'max_backup_bytes':1},{'api_budget_usd':'NaN'},
                       {'source_db':'relative'},{'command':'deliberate'}):
            with self.subTest(change=change),self.assertRaises((JobError,ValueError)):validate_plan({**self.plan,**change})
        with self.assertRaises(JobError):decode_plan(b'{"source_db":1,"source_db":2}')
        with self.assertRaises(JobError):MaintenanceJobs(self.path,lambda:float('nan')).tick(self.plan)

    def test_mismatched_stop_flag_or_state_schema_cannot_dispatch(self):
        with closing(sqlite3.connect(self.path)) as db:db.execute('UPDATE control SET enabled=1');db.commit()
        with self.assertRaises(JobError):self.jobs.tick(self.plan)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE control SET enabled=0');db.execute('CREATE TABLE unexpected (id INTEGER)');db.commit()
        with self.assertRaises(JobError):self.jobs.tick(self.plan)

    def test_incomplete_attempt_capacity_cannot_be_silently_released_in_state(self):
        self.arm()
        with patch('nexydao.maintenance_jobs.backups.create_backup',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):self.jobs.tick(self.plan)
        with closing(sqlite3.connect(self.path)) as db:db.execute('UPDATE attempts SET bytes=0');db.commit()
        with self.assertRaises(JobError):self.jobs.tick(self.plan)

    def test_cli_requires_current_runtime_binding_and_never_uses_provider_or_socket(self):
        from nexydao.maintenance_jobs import main
        plan=self.root/'plan.json';plan.write_text(json.dumps(self.plan));plan.chmod(0o600)
        environment={'NEXYDAO_DB':str(self.source),'NEXYDAO_API_BUDGET_USD':'0.10'}
        for action in ('arm','tick','status','stop'):
            arguments=['jobs',action,'--state',str(self.path)]+(['--plan',str(plan)] if action in ('arm','tick') else [])
            output=io.StringIO()
            with patch.dict(os.environ,environment,clear=True),patch('sys.argv',arguments),patch('sys.stdout',output), \
                    patch('nexydao.provider.OpenAIProvider') as provider,patch('socket.create_connection') as connect:main()
            provider.assert_not_called();connect.assert_not_called();self.assertFalse(json.loads(output.getvalue())['paid_job_supported'])
        with patch.dict(os.environ,{**environment,'NEXYDAO_API_BUDGET_USD':'1'},clear=True), \
                patch('sys.argv',['jobs','arm','--state',str(self.path),'--plan',str(plan)]),patch('sys.stderr'),self.assertRaises(SystemExit):main()

    @unittest.skipUnless(os.name=='posix','Unix state protection')
    def test_unix_writable_or_linked_state_and_public_plan_are_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(backups.BackupError):self.jobs.status()
        self.path.chmod(0o600);link=self.root/'linked';os.link(self.path,link)
        with self.assertRaises(backups.BackupError):self.jobs.status()
