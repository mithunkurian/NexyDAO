"""Explicit finite backup/health scheduling ticks; no daemon or AI/broker job.

Separate private state, stopped initialization, durable claim before work. Unknown
attempt outcomes block further work; no automatic retry or commitment release.
"""
import argparse
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import time

from . import audit_backups as backups
from .config import Config
from .market import canonical
from .operations_health import operations_health,MIN_FREE_BYTES

FIELDS={'source_db','backup_root','api_budget_usd','interval_seconds','max_attempts','max_backup_bytes'}
REASONS={'initialized_stopped','armed','owner_stopped','attempt_failed','attempt_cap','archive_cap','clock_regressed','plan_changed','disk_space_low'}


class JobError(ValueError):pass


def _capacity_stop_reason(plan, attempts):
    if len(attempts) >= plan['max_attempts']:
        return 'attempt_cap'
    if sum(attempt[4] for attempt in attempts) + backups.MAX_DB > plan['max_backup_bytes']:
        return 'archive_cap'
    return None


def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!=FIELDS:raise JobError('maintenance_plan_schema')
    for name in ('source_db','backup_root'):
        value=plan[name]
        if (not isinstance(value,str) or not 0<len(value)<=1024 or not Path(value).is_absolute()
                or '..' in Path(value).parts):raise JobError('maintenance_plan_path')
    for name,low,high in (('interval_seconds',60,86400),('max_attempts',1,100),('max_backup_bytes',backups.MAX_DB,1024*1024*1024)):
        if type(plan[name]) is not int or not low<=plan[name]<=high:raise JobError('maintenance_plan_limit')
    value=plan['api_budget_usd']
    if not isinstance(value,str) or not 0<len(value)<=80:raise JobError('maintenance_plan_budget')
    try:budget=Decimal(value)
    except Exception:raise JobError('maintenance_plan_budget') from None
    if not budget.is_finite() or not 0<budget<=1000000 or budget.as_tuple().exponent < -50:raise JobError('maintenance_plan_budget')
    backups._parent(Path(plan['backup_root'])/'private-root-check')
    return plan


def decode_plan(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=16384:raise JobError('maintenance_plan_size')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise JobError('maintenance_plan_duplicate_field')
            result[key]=value
        return result
    try:return validate_plan(json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError())))
    except (ValueError,TypeError,RecursionError):raise JobError('maintenance_plan_invalid') from None


class MaintenanceJobs:
    def __init__(self,path,clock=time.time):self.path=Path(path).absolute();self.clock=clock

    def _now(self):
        value=self.clock()
        if type(value) not in (int,float) or not 0<value<1e12:raise JobError('maintenance_clock_invalid')
        return int(value)

    @contextmanager
    def _db(self, *, readonly=False):
        with backups._file(self.path,1024*1024):pass
        target=self.path.as_uri()+'?mode=ro' if readonly else self.path
        db=sqlite3.connect(target,uri=readonly,timeout=2,isolation_level=None)
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            if not readonly:db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN' if readonly else 'BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:db.execute('ROLLBACK')
            raise
        finally:db.close()

    def initialize(self,plan):
        validate_plan(plan);backups._parent(self.path)
        descriptor=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
        bootstrap=sqlite3.connect(self.path)
        try:bootstrap.execute('PRAGMA user_version=1')
        finally:bootstrap.close()
        with self._db() as db:
            db.execute('CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,reason TEXT NOT NULL,plan TEXT NOT NULL,digest TEXT NOT NULL)')
            db.execute('CREATE TABLE attempts (id TEXT PRIMARY KEY,started INTEGER NOT NULL,finished INTEGER,status TEXT NOT NULL,bytes INTEGER NOT NULL,digest TEXT NOT NULL)')
            db.execute('INSERT INTO control VALUES(1,0,?,?,?)',('initialized_stopped',canonical(plan).decode(),hashlib.sha256(canonical(plan)).hexdigest()))
        return self.status()

    def _read(self,db):
        objects=set(db.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger') LIMIT 4").fetchall())
        if objects!={('control','table'),('attempts','table')} or db.execute('PRAGMA user_version').fetchone()[0]!=1:
            raise JobError('maintenance_state_invalid')
        rows=db.execute('SELECT enabled,reason,CASE WHEN length(plan)<=16384 THEN plan END,digest FROM control').fetchall()
        if len(rows)!=1:raise JobError('maintenance_state_invalid')
        enabled,reason,raw,digest=rows[0];plan=decode_plan(raw.encode() if isinstance(raw,str) else b'')
        if (type(enabled) is not int or enabled not in (0,1) or reason not in REASONS or bool(enabled)!=(reason=='armed')
                or digest!=hashlib.sha256(canonical(plan)).hexdigest()):
            raise JobError('maintenance_state_invalid')
        attempts=db.execute('SELECT id,started,finished,status,bytes,digest FROM attempts ORDER BY started,id LIMIT 101').fetchall()
        if len(attempts)>plan['max_attempts']:raise JobError('maintenance_state_invalid')
        for identifier,start,finish,status,size,sha in attempts:
            if (not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier)
                    or type(start) is not int or start<=0 or status not in ('running','completed','failed')
                    or (finish is not None if status=='running' else type(finish) is not int or finish<start)
                    or type(size) is not int or not 0<size<=backups.MAX_DB
                    or not isinstance(sha,str) or (sha!='' and (len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha)))):
                raise JobError('maintenance_state_invalid')
            if (status=='running' and (size!=backups.MAX_DB or sha!='')
                    or status=='completed' and sha=='' or sha=='' and size!=backups.MAX_DB):
                raise JobError('maintenance_state_invalid')
        if sum(a[3]=='running' for a in attempts)>1:raise JobError('maintenance_state_invalid')
        if sum(a[4] for a in attempts)>plan['max_backup_bytes']:raise JobError('maintenance_state_invalid')
        return bool(enabled),reason,plan,attempts

    def _report(self,enabled,reason,plan,attempts,**extra):
        completed_at = max((attempt[2] for attempt in attempts if attempt[3] == 'completed'), default=None)
        interval = plan['interval_seconds']
        starts = [attempt[1] for attempt in attempts]
        gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
        return {'enabled':enabled,'reason':reason,'attempt_count':len(attempts),
            'incomplete_attempt_count':sum(a[3]=='running' for a in attempts),
            'failed_attempt_count':sum(a[3]=='failed' for a in attempts),
            'last_completed_at':completed_at,
            'capacity_stop_reason':_capacity_stop_reason(plan, attempts),
            'longest_start_gap_seconds':max(gaps, default=None),
            'unobserved_intervals_between_attempts':sum(max(0, gap // interval - 1) for gap in gaps),
            'retained_or_reserved_backup_bytes':sum(a[4] for a in attempts),
            'max_attempts':plan['max_attempts'],'max_backup_bytes':plan['max_backup_bytes'],
            'recurring_automation_installed':False,'paid_job_supported':False,
            'alert_delivery_performed':False,'execution_authorized':False,**extra}

    def status(self):
        with self._db(readonly=True) as db:return self._report(*self._read(db))

    def verify_archives(self):
        with self._db(readonly=True) as db:
            enabled, reason, plan, attempts = self._read(db)
        root = Path(plan['backup_root'])
        verified = 0
        errors = []
        for identifier, _, _, _, size, digest in attempts:
            if not digest:
                continue
            try:
                archive = backups.verify_backup(root / ('job-' + identifier))
            except backups.BackupError:
                errors.append({'attempt_id': identifier, 'reason': 'archive_unverifiable'})
                continue
            if (archive['database_bytes'], archive['database_sha256']) != (size, digest):
                errors.append({'attempt_id': identifier, 'reason': 'archive_attempt_mismatch'})
            else:
                verified += 1
        return self._report(enabled, reason, plan, attempts,
                            verified_archive_count=verified, archive_errors=errors)

    def stop(self):
        with self._db() as db:
            self._read(db);db.execute("UPDATE control SET enabled=0,reason='owner_stopped'")
            return self._report(*self._read(db))

    def arm(self,plan):
        validate_plan(plan)
        with self._db() as db:
            enabled,reason,stored,attempts=self._read(db)
            if canonical(plan)!=canonical(stored):raise JobError('maintenance_plan_changed')
            if any(a[3]!='completed' for a in attempts):raise JobError('maintenance_unknown_or_failed_attempt_requires_review')
            capacity_stop = _capacity_stop_reason(stored, attempts)
            if capacity_stop:
                raise JobError('maintenance_' + capacity_stop)
            db.execute("UPDATE control SET enabled=1,reason='armed'")
            return self._report(*self._read(db))

    def tick(self,plan):
        validate_plan(plan);started=self._now()
        with self._db() as db:
            enabled,reason,stored,attempts=self._read(db)
            def stop(reason):
                db.execute('UPDATE control SET enabled=0,reason=?',(reason,))
                return self._report(False,reason,stored,attempts,work_started=False)
            if canonical(plan)!=canonical(stored):return stop('plan_changed')
            if not enabled:return self._report(enabled,reason,stored,attempts,work_started=False)
            if any(a[3]=='running' for a in attempts):return self._report(enabled,reason,stored,attempts,work_started=False,blocked_by_incomplete_attempt=True)
            if any(a[3]=='failed' for a in attempts):return stop('attempt_failed')
            last=max((a[1] for a in attempts),default=None)
            if last is not None and started<last:return stop('clock_regressed')
            if last is not None and started<last+plan['interval_seconds']:
                return self._report(enabled,reason,stored,attempts,work_started=False,next_due_at=last+plan['interval_seconds'])
            capacity_stop = _capacity_stop_reason(stored, attempts)
            if capacity_stop:
                return stop(capacity_stop)
            if shutil.disk_usage(plan['backup_root']).free<MIN_FREE_BYTES+backups.MAX_DB:return stop('disk_space_low')
            identifier=secrets.token_hex(16)
            db.execute('INSERT INTO attempts VALUES(?,?,NULL,?,?,?)',(identifier,started,'running',backups.MAX_DB,''))
        # Claim is durable before any archive work. Crash/kill leaves it unknown;
        # later invocations cannot repeat it, release its cap or start another job.
        destination=Path(plan['backup_root'])/('job-'+identifier)
        size=backups.MAX_DB;sha='';passed=False;critical=None
        try:
            archive=backups.create_backup(Path(plan['source_db']),destination)
            size=archive['database_bytes'];sha=archive['database_sha256']
            health=operations_health(Path(plan['source_db']),Decimal(plan['api_budget_usd']),destination)
            passed=health['local_health_checks_passed'];critical=health['critical_alert_count']
        except Exception:pass  # Do not persist vendor/path/SQL exception text.
        finished=self._now()
        if finished<started:passed=False;finished=started
        with self._db() as db:
            enabled,reason,stored,attempts=self._read(db)
            current=[a for a in attempts if a[0]==identifier]
            if len(current)!=1 or current[0][3]!='running':raise JobError('maintenance_claim_changed')
            db.execute('UPDATE attempts SET finished=?,status=?,bytes=?,digest=? WHERE id=?',
                       (finished,'completed' if passed else 'failed',size,sha,identifier))
            if not passed:db.execute("UPDATE control SET enabled=0,reason='attempt_failed'")
            return self._report(*self._read(db),work_started=True,attempt_id=identifier,
                                maintenance_passed=passed,critical_alert_count=critical)


def main():
    parser=argparse.ArgumentParser(description='Explicit finite backup/health ticks; no timer or paid/broker jobs')
    parser.add_argument('action',choices=['init','arm','tick','stop','status','verify-archives'])
    parser.add_argument('--state',required=True,type=Path);parser.add_argument('--plan',type=Path)
    args=parser.parse_args()
    try:
        config=Config.from_env();jobs=MaintenanceJobs(args.state)
        if args.action in ('init','arm','tick'):
            if args.plan is None:raise JobError('maintenance_explicit_plan_required')
            with backups._file(args.plan,16384) as stream:plan=decode_plan(stream.read(16385))
            if Path(plan['source_db']).absolute()!=config.db.absolute() or Decimal(plan['api_budget_usd'])!=config.budget:
                raise JobError('maintenance_runtime_binding_changed')
            result=getattr(jobs,{'init':'initialize','arm':'arm','tick':'tick'}[args.action])(plan)
        else:
            if args.plan is not None:raise JobError('maintenance_plan_modifier_not_applicable')
            result=getattr(jobs,args.action.replace('-','_'))()
        print(json.dumps(result,indent=2))
        if result.get('archive_errors') or result['failed_attempt_count'] or result['incomplete_attempt_count'] or result['reason'] in ('attempt_cap','archive_cap','clock_regressed','plan_changed','disk_space_low'):parser.exit(1)
    except Exception as exc:
        code=str(exc) if isinstance(exc,JobError) else 'maintenance_unavailable'
        parser.exit(1,'NexyDAO maintenance stopped safely ('+code+').\n')


if __name__=='__main__':main()
