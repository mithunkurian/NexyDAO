"""Read-only root/operator audit of the installed SEC role deployment.

No credentials or unit environments are returned. This is a point-in-time audit,
not an execution permit or administrator-resistant attestation.
"""
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess

from .controller_access import run_controller_access_check
from .research_signatures import public_key
from .sec import ResearchConfig

CODE = Path('/opt/nexydao')
CONFIG = Path('/etc/nexydao-research')
PRIVATE = Path('/var/lib/nexydao-collector')
SHARED = Path('/var/lib/nexydao-evidence')
UNITS = ('nexydao-controller-firewall.service','nexydao-sec-collector.service','nexydao-research-consumer.service')
PROPERTIES = ('User','Group','SupplementaryGroups','WorkingDirectory','ProtectSystem','ProtectHome',
              'NoNewPrivileges','PrivateTmp','PrivateDevices','CapabilityBoundingSet','RestrictAddressFamilies',
              'FragmentPath','DropInPaths','LoadState','Result','ExecMainStatus','ExecMainStartTimestampMonotonic',
              'ExecMainExitTimestampMonotonic')
COMMON_ENV = {'NEXYDAO_RESEARCH_UNIVERSE','NEXYDAO_RESEARCH_CONCEPTS','NEXYDAO_RESEARCH_RECEIPT_MODE',
              'NEXYDAO_RESEARCH_PUBLIC_KEY_FILE','NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256','NEXYDAO_OPENSSL_PATH'}
COLLECTOR_ENV = COMMON_ENV | {'NEXYDAO_RESEARCH_SIGNING_KEY_FILE','NEXYDAO_SEC_USER_AGENT',
                            'NEXYDAO_RESEARCH_SNAPSHOT','NEXYDAO_RESEARCH_READ_GROUP'}


def parse_environment(raw):
    if not isinstance(raw,bytes) or len(raw)>16384:
        raise ValueError('Bounded role environment required')
    result={}
    for line in raw.decode('utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        name,separator,value=line.partition('=')
        if not separator or name in result or not name.startswith('NEXYDAO_'):
            raise ValueError('Invalid role environment')
        words=shlex.split(value,posix=True)
        if len(words)!=1:raise ValueError('One quoted environment value required')
        result[name]=words[0]
    return result


def hardened_service(properties,role):
    if role not in ('collector','consumer'):return False
    user='nexydao-collector' if role=='collector' else 'nexydao-controller'
    expected={'User':user,'Group':user,'WorkingDirectory':str(CODE),'ProtectSystem':'strict',
              'ProtectHome':'yes','NoNewPrivileges':'yes','PrivateTmp':'yes','PrivateDevices':'yes',
              'CapabilityBoundingSet':'','DropInPaths':'','LoadState':'loaded'}
    if any(properties.get(key)!=value for key,value in expected.items()):return False
    families=set(properties.get('RestrictAddressFamilies','').split())
    wanted={'AF_UNIX','AF_INET','AF_INET6'} if role=='collector' else {'AF_UNIX'}
    groups=set(properties.get('SupplementaryGroups','').split())
    return families==wanted and groups==({'nexydao-evidence'} if role=='consumer' else set())


def last_start_succeeded(properties):
    try:
        start=int(properties['ExecMainStartTimestampMonotonic'])
        end=int(properties['ExecMainExitTimestampMonotonic'])
        return start>0 and end>=start and properties['Result']=='success' and properties['ExecMainStatus']=='0'
    except (KeyError,ValueError,TypeError):return False


def _metadata(path,uid,mode=None,directory=False):
    info=path.lstat()
    valid=stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    return valid and info.st_uid==uid and not info.st_mode & 0o022 and (mode is None or stat.S_IMODE(info.st_mode)==mode)


def _root_tree(path):
    if not _metadata(path,0,directory=True):return False
    for index,p in enumerate(path.rglob('*')):
        if index>=500 or not _metadata(p,0,directory=p.is_dir()):return False
    return True


def _environment(path):
    if not _metadata(path,0,0o600):raise ValueError('Protected role file required')
    with path.open('rb') as stream:return parse_environment(stream.read(16385))


def _properties(unit):
    result=subprocess.run(['/usr/bin/systemctl','show',unit,'--no-pager','--property='+','.join(PROPERTIES)],
                          capture_output=True,timeout=5,check=True)
    if len(result.stdout)>32768:raise ValueError('Systemd output limit')
    output={}
    for line in result.stdout.decode('utf-8').splitlines():
        name,separator,value=line.partition('=')
        if not separator or name in output or name not in PROPERTIES:raise ValueError('Unexpected service metadata')
        output[name]=value
    return output


def run_service_isolation_check():
    checks={name:False for name in ('operator_root','identities_distinct','protected_code','protected_units',
            'role_files_protected','public_only_consumer','collector_key_permissions','collector_service_hardened',
            'consumer_service_hardened','collector_last_start_succeeded','consumer_last_start_succeeded',
            'controller_egress_guard')}
    if os.name!='posix' or os.geteuid()!=0:return _report(checks)
    checks['operator_root']=True
    try:
        import pwd,grp
        collector=pwd.getpwnam('nexydao-collector');consumer=pwd.getpwnam('nexydao-controller')
        readers=grp.getgrnam('nexydao-evidence').gr_gid
        checks['identities_distinct']=(collector.pw_uid>0 and consumer.pw_uid>0 and collector.pw_gid>0 and consumer.pw_gid>0
            and collector.pw_uid!=consumer.pw_uid
            and collector.pw_gid!=consumer.pw_gid and readers not in (0,collector.pw_gid,consumer.pw_gid)
            and collector.pw_shell in ('/usr/sbin/nologin','/sbin/nologin')
            and consumer.pw_shell in ('/usr/sbin/nologin','/sbin/nologin')
            and collector.pw_dir==str(PRIVATE) and consumer.pw_dir=='/var/lib/nexydao-controller'
            and set(os.getgrouplist(collector.pw_name,collector.pw_gid))=={collector.pw_gid}
            and set(os.getgrouplist(consumer.pw_name,consumer.pw_gid))<={consumer.pw_gid,readers})
        checks['protected_code']=_root_tree(CODE) and all(_metadata(p,0,directory=True) for p in CODE.parents)
        unit_paths=[Path('/etc/systemd/system')/name for name in UNITS]
        checks['protected_units']=all(_metadata(p,0,0o644) and p.read_bytes()==(CODE/'ops'/p.name).read_bytes() for p in unit_paths)
        guard=Path('/usr/local/sbin/nexydao-controller-firewall')
        checks['protected_units']=checks['protected_units'] and _metadata(guard,0,0o755) and guard.read_bytes()==(CODE/'ops/nexydao-controller-firewall.sh').read_bytes()
        checks['role_files_protected']=all(_metadata(p,0,directory=True) for p in (CONFIG,*CONFIG.parents))
        signing=_environment(CONFIG/'collector.env');verification=_environment(CONFIG/'consumer.env')
        checks['role_files_protected']=checks['role_files_protected'] and set(signing)==COLLECTOR_ENV and set(verification)==COMMON_ENV
        common_match=all(signing.get(k)==verification.get(k) for k in COMMON_ENV)
        checks['public_only_consumer']=(set(verification)==COMMON_ENV and common_match and verification.get('NEXYDAO_RESEARCH_RECEIPT_MODE')=='ed25519'
            and verification.get('NEXYDAO_RESEARCH_PUBLIC_KEY_FILE')==str(CONFIG/'sec-public.der')
            and verification.get('NEXYDAO_OPENSSL_PATH')=='/usr/bin/openssl')
        settings=ResearchConfig(json.loads(verification['NEXYDAO_RESEARCH_UNIVERSE']),None,
            concepts=json.loads(verification['NEXYDAO_RESEARCH_CONCEPTS']),receipt_mode='ed25519',
            public_key_path=CONFIG/'sec-public.der',public_key_sha256=verification['NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256'])
        if not _metadata(settings.public_key_path,0,0o644):raise ValueError('Protected public key required')
        public_key(settings.public_key_path,settings.public_key_sha256)
        shared=SHARED.lstat()
        checks['collector_key_permissions']=(_metadata(PRIVATE,collector.pw_uid,0o700,True)
            and _metadata(PRIVATE/'sec-signing.pem',collector.pw_uid,0o600)
            and signing.get('NEXYDAO_RESEARCH_SIGNING_KEY_FILE')==str(PRIVATE/'sec-signing.pem')
            and signing.get('NEXYDAO_RESEARCH_SNAPSHOT')==str(PRIVATE/'sec-research.json')
            and signing.get('NEXYDAO_RESEARCH_READ_GROUP')=='nexydao-evidence'
            and stat.S_ISDIR(shared.st_mode) and shared.st_uid==collector.pw_uid
            and shared.st_gid==readers and stat.S_IMODE(shared.st_mode)==0o2750)
        for role,unit in (('collector',UNITS[1]),('consumer',UNITS[2])):
            properties=_properties(unit)
            fragment=properties.get('FragmentPath')==str(Path('/etc/systemd/system')/unit)
            checks[role+'_service_hardened']=fragment and hardened_service(properties,role)
            checks[role+'_last_start_succeeded']=last_start_succeeded(properties)
        checks['controller_egress_guard']=run_controller_access_check()['controller_broker_port_egress_denied']
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):pass
    return _report(checks)


def _report(checks):
    verified=all(checks.values())
    return {'status':'sec_service_isolation_verified' if verified else 'sec_service_isolation_unverified',
            'sec_role_boundary_verified':verified,'checks':checks,'other_receipt_types_verified':False,
            'boot_and_sustained_recovery_verified':False,'execution_authorized':False}
