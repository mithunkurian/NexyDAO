"""Unix root-owned shadow stop authority shared by separate unprivileged roles.

No deployment, root escalation, broker authority or automatic resume. All paths
and policy snapshots must already be protected. Root remains fully trusted.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import stat

from .paper_permits import PermitError, _hex, _unique


def parse_control(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=2048:
        raise PermitError('shadow_control_size')
    try:data=json.loads(raw,object_pairs_hook=_unique)
    except (ValueError,UnicodeError,RecursionError):raise PermitError('shadow_control_json') from None
    if (not isinstance(data,dict) or set(data)!={'schema_version','stopped','epoch','policy_sha256'}
            or type(data['schema_version']) is not int or data['schema_version']!=1
            or type(data['stopped']) is not bool or not _hex(data['epoch'],32)
            or (data['policy_sha256']!='' if data['stopped'] else not _hex(data['policy_sha256']))):
        raise PermitError('shadow_control_schema')
    return data


def _protected(path, *, directory=False):
    info=path.lstat()
    expected=stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022
            or not directory and (stat.S_IMODE(info.st_mode)!=0o644 or info.st_nlink!=1)):
        raise PermitError('shadow_control_permissions')


class AuthorityControl:
    def __init__(self,path):
        self.path=Path(path)
        if not self.path.is_absolute():raise PermitError('shadow_control_absolute_path')
        self.lock=self.path.with_name(self.path.name+'.lock')

    def _parents(self):
        if os.name!='posix':raise PermitError('shadow_control_unix_required')
        for parent in self.path.parents:_protected(parent,directory=True)

    @staticmethod
    def _root():
        if os.name!='posix' or os.geteuid()!=0:raise PermitError('shadow_control_owner_required')

    @staticmethod
    def _policy(policy):
        if policy.path is None or not policy.path.is_absolute():raise PermitError('shadow_control_policy_path')
        for parent in policy.path.parents:_protected(parent,directory=True)
        _protected(policy.path)
        policy.assert_current()

    def initialize(self):
        self._root();self._parents()
        if any(p.exists() or p.is_symlink() for p in (self.path,self.lock)):
            raise PermitError('shadow_control_fresh_paths_required')
        # A partial initialization stays stopped/unavailable; never overwrite it.
        for path,raw in ((self.lock,b''),(self.path,self._bytes(True,''))):
            with path.open('xb') as stream:
                os.fchmod(stream.fileno(),0o644);stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self._sync_parent()

    @staticmethod
    def _bytes(stopped,digest):
        return json.dumps({'schema_version':1,'stopped':stopped,'epoch':secrets.token_hex(16),
                           'policy_sha256':digest},sort_keys=True,separators=(',',':')).encode()

    def _sync_parent(self):
        descriptor=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)

    @contextmanager
    def _locked(self, *, exclusive=False):
        import fcntl
        self._parents();_protected(self.lock)
        descriptor=os.open(self.lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1
                    or stat.S_IMODE(info.st_mode)!=0o644):raise PermitError('shadow_control_permissions')
            try:fcntl.flock(descriptor,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
            except BlockingIOError:raise PermitError('shadow_control_busy') from None
            yield
        finally:os.close(descriptor)

    def _read(self):
        _protected(self.path)
        descriptor=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            info=os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1
                    or stat.S_IMODE(info.st_mode)!=0o644):raise PermitError('shadow_control_permissions')
            return parse_control(stream.read(2049))

    @contextmanager
    def locked_epoch(self,policy):
        with self._locked():
            self._policy(policy)
            state=self._read()
            if state['stopped'] or state['policy_sha256']!=policy.digest:
                raise PermitError('shadow_authority_stopped_or_policy_changed')
            yield state['epoch']

    def epoch(self,policy):
        with self.locked_epoch(policy) as epoch:return epoch

    def _transition(self,stopped,policy=None):
        self._root()
        with self._locked(exclusive=True):
            self._read()  # Corrupt/missing state requires explicit review, never reset.
            if not stopped:self._policy(policy)
            raw=self._bytes(stopped,'' if stopped else policy.digest)
            temporary=self.path.with_name(self.path.name+'.'+secrets.token_hex(8)+'.tmp')
            try:
                with temporary.open('xb') as stream:
                    os.fchmod(stream.fileno(),0o644);stream.write(raw);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,self.path);self._sync_parent()
            finally:
                if temporary.exists():temporary.unlink()

    def stop(self):self._transition(True)

    def arm(self,policy):self._transition(False,policy)
