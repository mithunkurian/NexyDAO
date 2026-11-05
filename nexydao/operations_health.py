"""Bounded read-only local health/alert reporting. No scheduling or repair."""
from datetime import datetime
from decimal import Decimal,localcontext
import hashlib
from pathlib import Path
import shutil
import time

from . import audit_backups as backups
from .market import canonical

RUN_MAX_AGE=20*60
RESERVATION_MAX_AGE=120
BACKUP_MAX_AGE=24*60*60
MIN_FREE_BYTES=128*1024*1024
MAX_ROW_TEXT=1024*1024


class HealthError(ValueError):
    """Fixed local codes; never include database text or filesystem paths."""


def _epoch(raw,now):
    if not isinstance(raw,str) or not 0<len(raw)<=80:raise HealthError('operations_record_time_invalid')
    try:
        stamp=datetime.fromisoformat(raw)
        if stamp.utcoffset() is None:raise ValueError()
        value=stamp.timestamp()
    except (ValueError,TypeError,OverflowError):raise HealthError('operations_record_time_invalid') from None
    if not 0<value<=now:raise HealthError('operations_record_time_invalid')
    return value


def _fingerprint(connection,audit,deadline):
    """Same logical application data, excluding the added recovery guard.

    Include schema, column metadata and rowids/content, not DB page layout. Hash
    each bounded row separately; no model narrative or IDs appear in output.
    """
    digest=hashlib.sha256()
    for name in sorted(set(audit['table_row_counts'])-{'recovery_guard'}):
        sql=connection.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
        columns=connection.execute('PRAGMA table_info("'+name+'")').fetchall()
        if len(sql)>16384 or len(columns)>32:raise HealthError('operations_schema_size_invalid')
        digest.update(canonical([name,sql,columns])+b'\n')
        for row in connection.execute('SELECT rowid,* FROM "'+name+'" ORDER BY rowid'):
            if time.monotonic()>=deadline:raise HealthError('operations_health_time_limit')
            if any(isinstance(value,bytes) for value in row) or sum(len(value) for value in row if isinstance(value,str))>MAX_ROW_TEXT:
                raise HealthError('operations_record_size_or_type_invalid')
            digest.update(canonical(row)+b'\n')
    return digest.hexdigest()


def operations_health(source_path,budget,backup_folder=None,now=None):
    """A consistent local DB observation, not authority to run or spend."""
    try:
        if (not isinstance(budget,Decimal) or not budget.is_finite() or not 0<budget<=Decimal('1000000000000')
                or budget.as_tuple().exponent < -50):
            raise HealthError('operations_budget_invalid')
        source_path=Path(source_path).absolute();deadline=time.monotonic()+backups.TIMEOUT
        with backups._readonly(source_path,deadline) as connection:
            connection.execute('BEGIN')
            audit=backups._audit(connection)
            recovered='recovery_guard' in audit['table_row_counts']
            if recovered:backups._guard(connection)
            fingerprint=_fingerprint(connection,audit,deadline)
            runs=connection.execute('SELECT CASE WHEN length(created)<=80 THEN created END,status,mode FROM runs').fetchall()
            reserved=connection.execute("SELECT CASE WHEN length(c.created)<=80 THEN c.created END,r.status "
                "FROM costs c JOIN runs r ON r.id=c.run_id WHERE c.status='reserved'").fetchall()
            connection.rollback()
        evaluated=time.time() if now is None else now
        if type(evaluated) not in (int,float) or not 0<evaluated<1e12:raise HealthError('operations_clock_invalid')
        alerts=[]
        def alert(code,severity,count=1):alerts.append({'code':code,'severity':severity,'count':count})
        if recovered:alert('inspection_copy_cannot_resume','critical')
        long_running=running=0;latest_time=None;latest_states=set();last_ai_success=None
        for raw,status,mode in runs:
            if status not in ('running','completed','failed') or mode not in ('ai','demo'):
                raise HealthError('operations_run_state_invalid')
            stamp=_epoch(raw,evaluated)
            if status=='running':running+=1;long_running+=evaluated-stamp>=RUN_MAX_AGE
            if mode=='ai':
                if latest_time is None or stamp>latest_time:latest_time=stamp;latest_states={status}
                elif stamp==latest_time:latest_states.add(status)
                if status=='completed':last_ai_success=max(last_ai_success or stamp,stamp)
        latest_status=next(iter(latest_states)) if len(latest_states)==1 else ('ambiguous' if latest_states else None)
        if long_running:alert('long_running_runs_require_review','critical',long_running)
        if running>long_running:alert('active_runs_observed','warning',running-long_running)
        if latest_status=='failed':alert('latest_ai_run_failed','critical')
        if latest_status=='ambiguous':alert('latest_ai_run_order_ambiguous','critical')
        if last_ai_success is None:alert('no_completed_ai_run_observed','warning')
        elif evaluated-last_ai_success>=BACKUP_MAX_AGE:alert('no_recent_ai_completion','warning')
        aged=finished=0
        for raw,status in reserved:
            aged+=evaluated-_epoch(raw,evaluated)>=RESERVATION_MAX_AGE
            finished+=status!='running'
        if aged:alert('aged_api_reservations_require_review','critical',aged)
        if finished:alert('finished_runs_have_uncertain_api_costs','critical',finished)
        if reserved and not aged and not finished:alert('active_api_reservations_retained','warning',len(reserved))
        with localcontext() as context:
            context.prec=100
            spent=Decimal(audit['api_estimate_or_reserved_usd']);remaining=max(Decimal(0),budget-spent)
            if spent>=budget:alert('lifetime_api_budget_exhausted','critical')
            elif remaining<=budget*Decimal('.10'):alert('lifetime_api_budget_near_limit','warning')
        free=shutil.disk_usage(source_path.parent).free
        if type(free) is not int or free<0:raise HealthError('operations_disk_observation_invalid')
        if free<MIN_FREE_BYTES:alert('database_volume_free_space_low','critical')
        backup_verified=False;matches=None;backup_age=None
        if backup_folder is None:alert('verified_backup_not_supplied','critical')
        else:
            try:
                manifest=backups._manifest(backup_folder)
                deadline=time.monotonic()+backups.TIMEOUT
                with backups._readonly(Path(backup_folder)/'snapshot.sqlite3',deadline,sealed=True) as connection:
                    backup_fingerprint=_fingerprint(connection,manifest['audit'],deadline)
                # Recheck the artifact after the additional content reads.
                if backups._hash(Path(backup_folder)/'snapshot.sqlite3')!=(manifest['database_sha256'],manifest['database_bytes']):
                    raise HealthError('operations_backup_changed')
                backup_verified=True;matches=fingerprint==backup_fingerprint
                backup_age=evaluated-manifest['created_at']
                if backup_age<0:alert('backup_timestamp_in_future','critical')
                elif backup_age>=BACKUP_MAX_AGE:alert('verified_backup_too_old','critical')
                if not matches:alert('backup_content_differs_from_observed_database','warning')
            except Exception:
                backup_verified=False;matches=None;backup_age=None
                alert('backup_verification_failed','critical')
        critical=sum(item['severity']=='critical' for item in alerts)
        return {'status':'operations_attention_required' if critical else ('operations_warnings_present' if alerts else 'operations_checks_passed'),
            'local_health_checks_passed':critical==0,'critical_alert_count':critical,'alerts':alerts,
            'evaluated_at':evaluated,'audit':audit,'audit_content_sha256':fingerprint,
            'lifetime_api_budget_usd':str(budget),'remaining_api_budget_usd':str(remaining),
            'latest_ai_run_status':latest_status,'long_running_run_count':long_running,
            'aged_api_reservation_count':aged,'uncertain_costs_on_finished_runs_count':finished,
            'database_volume_free_bytes':free,'backup_verified':backup_verified,
            'backup_matches_observed_database':matches,'backup_age_seconds':backup_age,
            'inspection_copy_detected':recovered,'database_modified':False,'reservations_released':False,
            'recurring_automation_enabled':False,'alert_delivery_performed':False,
            'operational_readiness_verified':False,'scheduling_authorized':False,'execution_authorized':False}
    except HealthError:raise
    except Exception:raise HealthError('operations_health_unavailable') from None
