"""Private SQLite online backups and stopped, inspection-only recovery copies.

No credential files, authority ledgers, network calls, budget reset or runtime
replacement. Hash manifests detect changes; they are not authenticated signatures.
"""
from contextlib import contextmanager
from decimal import Decimal,localcontext
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

from .market import canonical

MAX_DB=64*1024*1024
MAX_ROWS=100000
TIMEOUT=10
PURPOSE='audit_inspection_only'
CORE={'runs','events','costs','run_revisions'}
PORTFOLIO={'portfolio_state','simulation_fills','simulated_positions','portfolio_marks'}
HOLDS={'simulation_reservations','simulation_reservation_events','simulation_reservation_fills','simulation_reservation_limits'}
ALLOWED=CORE|PORTFOLIO|HOLDS|{'funding_reviews','allocation_reviews','sqlite_sequence','recovery_guard'}
MANIFEST_FIELDS={'schema_version','purpose','created_at','database_sha256','database_bytes','audit'}


class BackupError(ValueError):
    """Fixed codes only; no paths, SQL, balances or credential data in errors."""


def _parent(path):
    path=Path(path).absolute()
    for part in (path.parent,*path.parent.parents):
        if part.is_symlink() or getattr(part,'is_junction',lambda:False)() or not part.is_dir():
            raise BackupError('backup_parent_unavailable')
    info=path.parent.stat()
    if os.name=='posix' and (info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700):
        raise BackupError('backup_private_parent_required')
    return path


@contextmanager
def _file(path,limit):
    path=_parent(path)
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
        raise BackupError('backup_private_regular_file_required')
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_BINARY',0))
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=limit
                or os.name=='posix' and (info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600)):
            raise BackupError('backup_private_regular_file_required')
        yield stream


def _hash(path,limit=MAX_DB):
    digest=hashlib.sha256();size=0
    with _file(path,limit) as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            size+=len(block)
            if size>limit:raise BackupError('backup_size_limit')
            digest.update(block)
    return digest.hexdigest(),size


def _write(path,raw):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
    with os.fdopen(descriptor,'wb') as destination:
        destination.write(raw);destination.flush();os.fsync(destination.fileno())


def _sync(folder):
    if os.name=='posix':
        descriptor=os.open(folder,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


@contextmanager
def _readonly(path,deadline,*,sealed=False):
    # The parent and file are private to the trusted operator. SQLite uses the
    # original path; this is not protection against an adversarial same-UID owner.
    if time.monotonic()>=deadline:raise BackupError('backup_time_limit')
    with _file(path,MAX_DB):pass
    connection=sqlite3.connect(Path(path).absolute().as_uri()+'?mode=ro'+('&immutable=1' if sealed else ''),
                               uri=True,timeout=1,isolation_level=None)
    try:
        connection.execute('PRAGMA trusted_schema=OFF');connection.execute('PRAGMA query_only=ON')
        connection.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        yield connection
    finally:connection.close()


def _audit(connection):
    if connection.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise BackupError('backup_database_corrupt')
    schema=connection.execute("SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','view','trigger') LIMIT 33").fetchall()
    if (len(schema)>32 or any(kind!='table' or name not in ALLOWED or not sql.startswith('CREATE TABLE')
                             for name,kind,sql in schema)):
        raise BackupError('backup_application_schema_required')
    tables={row[0] for row in schema}
    if not CORE<=tables:raise BackupError('backup_application_schema_required')
    if tables&PORTFOLIO and not PORTFOLIO<=tables:raise BackupError('backup_portfolio_schema_incomplete')
    if tables&HOLDS and not PORTFOLIO<=tables:raise BackupError('backup_portfolio_schema_incomplete')
    counts={}
    for name in sorted(tables):
        count=connection.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0]
        if count>MAX_ROWS:raise BackupError('backup_row_limit')
        counts[name]=count
    if connection.execute('SELECT 1 FROM costs c LEFT JOIN runs r ON c.run_id=r.id WHERE r.id IS NULL LIMIT 1').fetchone():
        raise BackupError('backup_orphan_cost_record')
    if connection.execute('SELECT 1 FROM events e LEFT JOIN runs r ON e.run_id=r.id WHERE r.id IS NULL LIMIT 1').fetchone():
        raise BackupError('backup_orphan_event_record')
    with localcontext() as context:
        context.prec=100
        total=Decimal(0);unsettled=0
        for charged,status in connection.execute('SELECT charged,status FROM costs'):
            if not isinstance(charged,str) or not 0<len(charged)<=80 or status not in ('reserved','reported'):
                raise BackupError('backup_cost_record_invalid')
            try:value=Decimal(charged)
            except Exception:raise BackupError('backup_cost_record_invalid') from None
            if not value.is_finite() or value<0 or value.adjusted()>12 or value.as_tuple().exponent < -50:
                raise BackupError('backup_cost_record_invalid')
            total+=value;unsettled+=status=='reserved'
        revision=None;active=0
        if PORTFOLIO<=tables:
            from .portfolio import Portfolio
            from .reservations import active_holds
            ledger=Portfolio.__new__(Portfolio);ledger.db=connection
            ledger.reconcile()  # Read-only replay; never initialize or repair tables.
            row=connection.execute('SELECT revision FROM portfolio_state WHERE id=1').fetchone()
            if row is None or type(row[0]) is not int or row[0]<0:raise BackupError('backup_portfolio_revision_invalid')
            revision=row[0];active=len(active_holds(connection))
    return {'table_row_counts':counts,'api_estimate_or_reserved_usd':str(total),
        'api_call_records':counts['costs'],'unsettled_api_call_records':unsettled,
        'running_run_count':connection.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0],
        'portfolio_revision':revision,'active_simulation_hold_count':active}


def _guard(connection):
    try:rows=connection.execute('SELECT id,schema_version,purpose FROM recovery_guard').fetchall()
    except sqlite3.Error:raise BackupError('backup_recovery_guard_required') from None
    if rows!=[(1,1,PURPOSE)]:raise BackupError('backup_recovery_guard_required')


def _new_folder(path):
    path=_parent(path);path.mkdir(mode=0o700)  # Never reuse/overwrite a target.
    return path


def _discard(folder):
    # Remove only files this operation can create, within its new exclusive dir.
    # Never recursively delete a user-selected directory or follow children.
    for name in ('snapshot.sqlite3','snapshot.sqlite3-journal','snapshot.sqlite3-wal','snapshot.sqlite3-shm','manifest.json'):
        (folder/name).unlink(missing_ok=True)
    folder.rmdir()


def _summary(manifest,status):
    audit=manifest['audit'];warnings=[]
    if audit['unsettled_api_call_records']:warnings.append('uncertain_api_reservations_retained')
    if audit['running_run_count']:warnings.append('interrupted_runs_require_review')
    if audit['active_simulation_hold_count']:warnings.append('active_simulation_holds_retained')
    return {'status':status,'database_sha256':manifest['database_sha256'],'database_bytes':manifest['database_bytes'],
        'audit':audit,'warnings':warnings,'inspection_only':True,'runtime_resume_authorized':False,
        'budget_reset_performed':False,'authority_state_restored':False,'execution_authorized':False}


def create_backup(source_path,folder):
    created=None
    try:
        source_path=_parent(source_path);deadline=time.monotonic()+TIMEOUT
        with _readonly(source_path,deadline) as source:
            if source.execute("SELECT 1 FROM sqlite_master WHERE name='recovery_guard'").fetchone():
                raise BackupError('backup_source_is_recovery_copy')
            page_size=source.execute('PRAGMA page_size').fetchone()[0]
            if source.execute('PRAGMA page_count').fetchone()[0]*page_size>MAX_DB:raise BackupError('backup_size_limit')
            created=_new_folder(folder);snapshot=created/'snapshot.sqlite3'
            _write(snapshot,b'')
            target=sqlite3.connect(snapshot,timeout=1)
            try:
                target.execute('PRAGMA trusted_schema=OFF')
                def progress(status,remaining,total):
                    if time.monotonic()>=deadline:raise BackupError('backup_time_limit')
                    if total*page_size>MAX_DB:raise BackupError('backup_size_limit')
                source.backup(target,pages=64,progress=progress,sleep=0.01)
                target.execute('PRAGMA journal_mode=DELETE')
                target.execute('CREATE TABLE recovery_guard (id INTEGER PRIMARY KEY,schema_version INTEGER NOT NULL,purpose TEXT NOT NULL)')
                target.execute('INSERT INTO recovery_guard VALUES(1,1,?)',(PURPOSE,));target.commit()
                target.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
                audit=_audit(target);_guard(target)
            finally:target.close()
        with snapshot.open('r+b') as stream:os.fsync(stream.fileno())
        digest,size=_hash(snapshot)
        manifest={'schema_version':1,'purpose':PURPOSE,'created_at':int(time.time()),
                  'database_sha256':digest,'database_bytes':size,'audit':audit}
        _write(created/'manifest.json',canonical(manifest));_sync(created);_sync(created.parent)
        return _summary(manifest,'audit_backup_created')
    except Exception as exc:
        if created is not None:_discard(created)
        if isinstance(exc,BackupError):raise
        raise BackupError('audit_backup_failed') from None


def _manifest(folder):
    folder=Path(folder).absolute()
    # No journals are valid in a sealed bundle. Never silently ignore a WAL.
    if any(os.path.lexists(folder/('snapshot.sqlite3'+suffix)) for suffix in ('-wal','-shm','-journal')):
        raise BackupError('backup_unsealed_database')
    with _file(folder/'manifest.json',16384) as stream:raw=stream.read(16385)
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise BackupError('backup_manifest_invalid')
            result[key]=value
        return result
    try:manifest=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except (ValueError,TypeError,RecursionError):raise BackupError('backup_manifest_invalid') from None
    if (not isinstance(manifest,dict) or set(manifest)!=MANIFEST_FIELDS
            or type(manifest['schema_version']) is not int or manifest['schema_version']!=1
            or manifest['purpose']!=PURPOSE or type(manifest['created_at']) is not int or manifest['created_at']<=0
            or type(manifest['database_bytes']) is not int or not 0<manifest['database_bytes']<=MAX_DB):
        raise BackupError('backup_manifest_invalid')
    digest,size=_hash(folder/'snapshot.sqlite3')
    if digest!=manifest['database_sha256'] or size!=manifest['database_bytes']:raise BackupError('backup_digest_mismatch')
    with _readonly(folder/'snapshot.sqlite3',time.monotonic()+TIMEOUT,sealed=True) as connection:
        _guard(connection);audit=_audit(connection)
    if canonical(audit)!=canonical(manifest['audit']):raise BackupError('backup_audit_mismatch')
    if _hash(folder/'snapshot.sqlite3')!=(digest,size):raise BackupError('backup_changed_during_verification')
    return manifest


def verify_backup(folder):
    try:return _summary(_manifest(folder),'audit_backup_verified')
    except BackupError:raise
    except Exception:raise BackupError('audit_backup_verification_failed') from None


def restore_inspection(folder,destination):
    created=None
    try:
        manifest=_manifest(folder);created=_new_folder(destination)
        snapshot=created/'snapshot.sqlite3'
        with _file(Path(folder)/'snapshot.sqlite3',MAX_DB) as source:
            descriptor=os.open(snapshot,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
            with os.fdopen(descriptor,'wb') as target:
                total=0
                for block in iter(lambda:source.read(1024*1024),b''):
                    total+=len(block)
                    if total>MAX_DB:raise BackupError('backup_size_limit')
                    target.write(block)
                target.flush();os.fsync(target.fileno())
        _write(created/'manifest.json',canonical(manifest));_sync(created);_sync(created.parent)
        verified=_manifest(created)
        return _summary(verified,'audit_inspection_copy_restored')
    except Exception as exc:
        if created is not None:_discard(created)
        if isinstance(exc,BackupError):raise
        raise BackupError('audit_inspection_restore_failed') from None
