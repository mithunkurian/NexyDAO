import copy
from contextlib import closing
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nexydao.audit_backups import create_backup,verify_backup,restore_inspection,BackupError
from nexydao.store import Store
from nexydao.portfolio import Portfolio
from nexydao.reservations import Reservations
from nexydao.owner_policy import load_policy
from nexydao.allocation import AllocationConfig


class AuditBackupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.source=self.root/'live.sqlite3';self.bundle=self.root/'backup';self.restore=self.root/'restored'
        self.store=Store(self.source);self.addCleanup(self.store.close);self.source.chmod(0o600)
        self.run=self.store.start()
        paid=self.store.reserve(self.run,'fixture','fake',Decimal('0.02'),Decimal('0.10'))
        self.store.settle(paid,Decimal('0.01'),{'input_tokens':1,'output_tokens':1},'fake-response')
        self.store.reserve(self.run,'uncertain','fake',Decimal('0.03'),Decimal('0.10'))
        self.store.event(self.run,'fixture',{'private':'must not appear in reports'})

    def backup(self):return create_backup(self.source,self.bundle)

    def test_backup_accepts_database_from_before_run_revisions(self):
        self.store.db.execute('DROP TABLE run_revisions')
        self.store.db.commit()

        self.backup()
        audit = verify_backup(self.bundle)['audit']

        self.assertNotIn('run_revisions', audit['table_row_counts'])
        self.assertEqual(audit['api_call_records'], self.store.costs()['calls'])

    def portfolio(self):
        ledger=Portfolio(self.store);book=Reservations(ledger)
        data={'id':'plan','proposal_sha256':'a'*64,'symbol':'TEST','notional_usd':'400','fee_usd':'2','fee_currency':'USD'}
        book.reserve(data,load_policy(),AllocationConfig())
        book.fill({'reservation_id':'plan','proposal_sha256':'a'*64,
            'fill':{'id':'fill','side':'buy','symbol':'TEST','quantity':'1','price':'100','fee':'1','currency':'USD','asset_type':'STK'}},load_policy())
        return ledger

    def rehash(self,folder=None):
        folder=folder or self.bundle;path=folder/'snapshot.sqlite3';manifest=folder/'manifest.json'
        data=json.loads(manifest.read_text());data['database_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        data['database_bytes']=path.stat().st_size;manifest.write_text(json.dumps(data));manifest.chmod(0o600)

    def test_online_backup_preserves_committed_wal_records_and_uncertain_costs(self):
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.store.event(self.run,'wal-only',{'committed':True})
        with closing(sqlite3.connect(self.source.as_uri()+'?immutable=1',uri=True)) as disk:
            self.assertEqual(disk.execute('SELECT count(*) FROM events').fetchone()[0],1)
        before=self.store.costs();report=self.backup();verified=verify_backup(self.bundle)
        self.assertEqual(report['database_sha256'],verified['database_sha256'])
        self.assertEqual(report['audit']['table_row_counts']['events'],2)
        self.assertEqual(report['audit']['api_estimate_or_reserved_usd'],'0.04')
        self.assertEqual(report['audit']['api_call_records'],2);self.assertEqual(report['audit']['unsettled_api_call_records'],1)
        self.assertIn('uncertain_api_reservations_retained',report['warnings'])
        self.assertIn('interrupted_runs_require_review',report['warnings']);self.assertEqual(before,self.store.costs())
        self.assertFalse(report['execution_authorized']);self.assertFalse(report['budget_reset_performed'])
        for sensitive in ('must not appear','fake-response','live.sqlite3',self.run):self.assertNotIn(sensitive,json.dumps(report))

    def test_portfolio_partial_hold_and_audit_replay_survive_exact_restore(self):
        ledger=self.portfolio();snapshot=ledger.snapshot();costs=self.store.costs()
        report=self.backup();restored=restore_inspection(self.bundle,self.restore)
        self.assertEqual(report['database_sha256'],restored['database_sha256'])
        self.assertEqual(report['audit'],restored['audit']);self.assertEqual(restored['audit']['portfolio_revision'],snapshot['revision'])
        self.assertEqual(restored['audit']['active_simulation_hold_count'],1)
        self.assertIn('active_simulation_holds_retained',restored['warnings'])
        with closing(sqlite3.connect(self.restore/'snapshot.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT charged,status FROM costs ORDER BY rowid').fetchall(),
                             self.store.db.execute('SELECT charged,status FROM costs ORDER BY rowid').fetchall())
            for table in ('simulation_reservations','simulation_reservation_fills','simulation_reservation_limits','portfolio_state'):
                self.assertEqual(db.execute('SELECT * FROM '+table).fetchall(),self.store.db.execute('SELECT * FROM '+table).fetchall())
        self.assertEqual(snapshot,ledger.snapshot());self.assertEqual(costs,self.store.costs())
        self.assertTrue(restored['inspection_only']);self.assertFalse(restored['runtime_resume_authorized'])

    def test_backup_and_restored_database_are_refused_before_runtime_wal_or_schema_changes(self):
        self.backup();restore_inspection(self.bundle,self.restore)
        for folder in (self.bundle,self.restore):
            path=folder/'snapshot.sqlite3';raw=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'Inspection-only'):Store(path)
            self.assertEqual(raw,path.read_bytes());self.assertFalse(Path(str(path)+'-wal').exists())
        with self.assertRaisesRegex(BackupError,'recovery_copy'):create_backup(self.bundle/'snapshot.sqlite3',self.root/'copy-again')

    def test_later_costs_in_source_are_not_erased_by_restoring_older_backup(self):
        self.backup();self.store.reserve(self.run,'later','fake',Decimal('0.02'),Decimal('0.10'))
        restored=restore_inspection(self.bundle,self.restore)
        self.assertEqual(self.store.costs()['estimated_or_reserved_usd'],'0.06')
        self.assertEqual(restored['audit']['api_estimate_or_reserved_usd'],'0.04')
        self.assertFalse(restored['runtime_resume_authorized'])
        with self.assertRaises(ValueError):Store(self.restore/'snapshot.sqlite3')

    def test_uncommitted_source_transaction_is_not_included_or_committed(self):
        self.store.db.execute('BEGIN IMMEDIATE')
        try:
            self.store.db.execute('INSERT INTO events(run_id,created,role,payload) VALUES(?,?,?,?)',(self.run,'now','uncommitted','{}'))
            report=self.backup();self.assertEqual(report['audit']['table_row_counts']['events'],1)
            self.assertTrue(self.store.db.in_transaction)
        finally:self.store.db.rollback()

    def test_existing_target_directories_and_live_source_are_never_overwritten(self):
        self.bundle.mkdir();sentinel=self.bundle/'sentinel';sentinel.write_text('keep')
        with self.assertRaises(BackupError):self.backup()
        self.assertEqual(sentinel.read_text(),'keep')
        with self.assertRaises(BackupError):create_backup(self.source,self.source.parent)
        sentinel.unlink();self.bundle.rmdir();self.backup()
        with self.assertRaises(BackupError):restore_inspection(self.bundle,self.root)
        self.assertTrue(self.source.exists());self.assertEqual(self.store.costs()['calls'],2)

    def test_missing_source_never_creates_an_empty_budget_ledger(self):
        missing=self.root/'missing.sqlite3'
        with self.assertRaises(BackupError):create_backup(missing,self.bundle)
        self.assertFalse(missing.exists());self.assertFalse(self.bundle.exists())

    def test_manifest_duplicate_fields_or_malformed_values_are_rejected(self):
        self.backup();path=self.bundle/'manifest.json';raw=path.read_bytes();original=json.loads(raw)
        cases=[raw.replace(b'"schema_version":1',b'"schema_version":1,"schema_version":1'),b'NaN',b'x'*16385]
        for key,value in (('schema_version',True),('purpose','runtime'),('created_at',True),('database_bytes',True),('audit',{})):
            data=copy.deepcopy(original);data[key]=value;cases.append(json.dumps(data).encode())
        for changed in cases:
            path.write_bytes(changed)
            with self.subTest(changed=changed[:30]),self.assertRaises(BackupError):verify_backup(self.bundle)
        path.write_bytes(raw)
        self.assertEqual(verify_backup(self.bundle)['audit']['api_call_records'],2)

    def test_truncated_or_altered_database_and_manifest_audit_are_rejected(self):
        self.backup();path=self.bundle/'snapshot.sqlite3';raw=path.read_bytes()
        path.write_bytes(raw[:100])
        with self.assertRaises(BackupError):verify_backup(self.bundle)
        path.write_bytes(raw);manifest=self.bundle/'manifest.json';data=json.loads(manifest.read_text())
        data['audit']['unsettled_api_call_records']=0;manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(BackupError,'audit_mismatch'):verify_backup(self.bundle)

    def test_guard_removal_or_a_sealed_wal_is_rejected_even_if_hash_is_recomputed(self):
        self.backup();path=self.bundle/'snapshot.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('DELETE FROM recovery_guard');db.commit()
        self.rehash()
        with self.assertRaisesRegex(BackupError,'recovery_guard'):verify_backup(self.bundle)
        (self.bundle/'snapshot.sqlite3-wal').write_bytes(b'ignored changes')
        with self.assertRaisesRegex(BackupError,'unsealed'):verify_backup(self.bundle)

    def test_non_application_or_authority_database_is_not_accepted(self):
        path=self.root/'authority.sqlite3'
        with closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE control (killed INTEGER)')
        path.chmod(0o600)
        with self.assertRaisesRegex(BackupError,'application_schema'):create_backup(path,self.bundle)
        self.assertFalse(self.bundle.exists())
        self.store.db.execute('CREATE TABLE control (killed INTEGER)');self.store.db.commit()
        with self.assertRaisesRegex(BackupError,'application_schema'):self.backup()

    def test_invalid_or_orphan_cost_records_fail_without_releasing_or_repairing_them(self):
        for value in ('-1','NaN','1E999999'):
            self.store.db.execute('UPDATE costs SET charged=?',(value,));self.store.db.commit()
            with self.assertRaisesRegex(BackupError,'cost_record'):self.backup()
            self.assertFalse(self.bundle.exists())
            self.assertEqual(self.store.db.execute('SELECT charged FROM costs LIMIT 1').fetchone()[0],value)
        self.store.db.execute("UPDATE costs SET charged='0.02',run_id='missing'");self.store.db.commit()
        with self.assertRaisesRegex(BackupError,'orphan_cost'):self.backup()

    def test_simulation_replay_failure_stops_backup_instead_of_repairing_source(self):
        ledger=self.portfolio();self.store.db.execute("UPDATE portfolio_state SET cash='5000'");self.store.db.commit()
        with self.assertRaises(BackupError):self.backup()
        self.assertFalse(self.bundle.exists())
        self.assertEqual(self.store.db.execute('SELECT cash FROM portfolio_state').fetchone()[0],'5000')

    def test_failed_copy_or_size_time_limit_leaves_no_valid_bundle(self):
        with patch('nexydao.audit_backups.MAX_DB',64),self.assertRaises(BackupError):self.backup()
        self.assertFalse(self.bundle.exists())
        with patch('nexydao.audit_backups.TIMEOUT',-1),self.assertRaises(BackupError):self.backup()
        self.assertFalse(self.bundle.exists())
        with patch('nexydao.audit_backups._audit',side_effect=sqlite3.OperationalError('private details')),self.assertRaises(BackupError) as error:
            self.backup()
        self.assertNotIn('private',str(error.exception));self.assertFalse(self.bundle.exists())

    def test_source_changed_after_snapshot_remains_live_and_backup_is_a_fixed_copy(self):
        self.backup();digest=verify_backup(self.bundle)['database_sha256']
        self.store.event(self.run,'later',{'new':True})
        self.assertEqual(verify_backup(self.bundle)['database_sha256'],digest)
        self.assertEqual(verify_backup(self.bundle)['audit']['table_row_counts']['events'],1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0],2)

    def test_source_row_limit_does_not_truncate_history_to_make_backup_pass(self):
        with patch('nexydao.audit_backups.MAX_ROWS',1),self.assertRaisesRegex(BackupError,'row_limit'):self.backup()
        self.assertFalse(self.bundle.exists());self.assertEqual(self.store.costs()['calls'],2)

    def test_restore_failure_does_not_change_bundle_or_source_or_leave_a_valid_restore(self):
        self.backup();digest=verify_backup(self.bundle)['database_sha256'];before=self.store.costs()
        with patch('nexydao.audit_backups._write',side_effect=OSError('fixture interrupted write')),self.assertRaises(BackupError):
            restore_inspection(self.bundle,self.restore)
        self.assertFalse(self.restore.exists());self.assertEqual(verify_backup(self.bundle)['database_sha256'],digest)
        self.assertEqual(before,self.store.costs())

    def test_change_during_verification_is_detected_even_if_audit_counts_stay_identical(self):
        from nexydao.audit_backups import _audit
        self.backup()
        def audit_then_change(connection):
            result=_audit(connection)
            with closing(sqlite3.connect(self.bundle/'snapshot.sqlite3')) as writer:
                writer.execute("UPDATE events SET payload='{}'");writer.commit()
            return result
        with patch('nexydao.audit_backups._audit',side_effect=audit_then_change), \
                self.assertRaisesRegex(BackupError,'changed_during_verification'):verify_backup(self.bundle)

    @unittest.skipUnless(os.name=='posix','Unix private path checks')
    def test_unix_wrong_modes_hardlinks_and_symlinks_are_rejected(self):
        self.source.chmod(0o644)
        with self.assertRaises(BackupError):self.backup()
        self.source.chmod(0o600);self.root.chmod(0o755)
        with self.assertRaises(BackupError):self.backup()
        self.root.chmod(0o700);link=self.root/'link';link.symlink_to(self.source)
        with self.assertRaises(BackupError):create_backup(link,self.bundle)
        link.unlink();os.link(self.source,link)
        with self.assertRaises(BackupError):self.backup()
        link.unlink();self.backup();(self.bundle/'manifest.json').chmod(0o644)
        with self.assertRaises(BackupError):verify_backup(self.bundle)

    def test_cli_backup_verify_restore_and_runtime_denial_use_no_network_provider_or_normal_store(self):
        from nexydao.cli import main
        environment={'NEXYDAO_DB':str(self.source)}
        commands=[['audit-backup','--backup-dir',str(self.bundle)],['audit-backup-check','--backup-dir',str(self.bundle)],
                  ['audit-restore-inspection','--backup-dir',str(self.bundle),'--restore-dir',str(self.restore)]]
        for command in commands:
            output=io.StringIO()
            with patch.dict(os.environ,environment,clear=True),patch('sys.argv',['nexydao',*command]),patch('sys.stdout',output), \
                    patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider,patch('socket.create_connection') as connect:
                main()
            for operation in (store,provider,connect):operation.assert_not_called()
            self.assertTrue(json.loads(output.getvalue())['inspection_only'])
        with patch.dict(os.environ,{'NEXYDAO_DB':str(self.restore/'snapshot.sqlite3')},clear=True), \
                patch('sys.argv',['nexydao','demo']),patch('sys.stderr'),self.assertRaises(SystemExit):main()

    def test_cli_requires_explicit_paths_and_rejects_unrelated_arguments(self):
        from nexydao.cli import main
        for command in (['audit-backup'],['audit-restore-inspection','--backup-dir',str(self.bundle)],
                ['demo','--backup-dir',str(self.bundle)],['audit-backup','--backup-dir',str(self.bundle),'--with-research']):
            with patch.dict(os.environ,{'NEXYDAO_DB':str(self.source)},clear=True), \
                    patch('sys.argv',['nexydao',*command]),patch('sys.stderr'),self.assertRaises(SystemExit):main()
