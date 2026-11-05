"""Ed25519-only publication into a collector-owned, consumer-readable directory."""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import time

from .sec import research_evidence_from_bytes, check_research_freshness


class PublicationError(RuntimeError):
    """Fixed local codes only, without file names or receipt contents."""


def valid_directory(info,uid,gid):
    return (type(uid) is int and type(gid) is int and uid>0 and gid>0
            and stat.S_ISDIR(info.st_mode) and info.st_uid==uid and info.st_gid==gid
            and stat.S_IMODE(info.st_mode)==0o2750)


def _protected_ancestors(directory):
    for parent in directory.parents:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
            raise PublicationError('protected_publication_ancestors_required')


def _read_receipt(path):
    flags=os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path,flags),'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise PublicationError('regular_research_receipt_required')
        return stream.read(64001)


def publish_research(source,destination,config,group,clock=time.time):
    if os.name!='posix':
        raise PublicationError('unix_publication_required')
    if config.receipt_mode!='ed25519':
        raise PublicationError('public_key_receipt_mode_required')
    import grp
    try:
        gid=grp.getgrnam(group).gr_gid
        uid=os.geteuid()
        destination=Path(destination)
        if not destination.is_absolute() or '..' in destination.parts or destination.name in ('','.'):
            raise PublicationError('absolute_publication_path_required')
        _protected_ancestors(destination.parent)
        directory=os.open(destination.parent,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if not valid_directory(os.fstat(directory),uid,gid):
                raise PublicationError('collector_owned_readonly_group_directory_required')
            raw=_read_receipt(source)
            evidence=research_evidence_from_bytes(raw,config,clock())
            try:
                old=os.stat(destination.name,dir_fd=directory,follow_symlinks=False)
            except FileNotFoundError:
                old=None
            if old is not None and (not stat.S_ISREG(old.st_mode) or old.st_uid!=uid
                                     or old.st_gid!=gid or stat.S_IMODE(old.st_mode)!=0o640):
                raise PublicationError('unsafe_existing_publication')
            name='sec-'+secrets.token_hex(16)+'.tmp'
            fd=os.open(name,os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600,dir_fd=directory)
            try:
                with os.fdopen(fd,'wb') as stream:
                    info=os.fstat(stream.fileno())
                    if info.st_uid!=uid or info.st_gid!=gid:
                        raise PublicationError('publication_group_inheritance_required')
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                    os.fchmod(stream.fileno(),0o640)
                check_research_freshness(evidence,clock())
                os.replace(name,destination.name,src_dir_fd=directory,dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try:os.unlink(name,dir_fd=directory)
                except FileNotFoundError:pass
        finally:
            os.close(directory)
    except (OSError,KeyError):
        raise PublicationError('research_publication_unavailable') from None
    return {'status':'public_research_receipt_published','facts':len(evidence),
            'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'receipt_mode':'ed25519',
            'consumer_group_write_allowed':False,'execution_authorized':False}
