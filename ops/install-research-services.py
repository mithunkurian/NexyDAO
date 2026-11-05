"""Fresh-install plan/apply for SEC-only roles. Root apply; no existing target overwrite.

Reads only the existing issuer/contact config, not its keys, DB or broker settings.
No timers or paid calls. A failed apply retains artifacts for operator review.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile

CODE=Path('/opt/nexydao')
CONFIG=Path('/etc/nexydao-research')
PRIVATE=Path('/var/lib/nexydao-collector')
CONTROLLER=Path('/var/lib/nexydao-controller')
SHARED=Path('/var/lib/nexydao-evidence')
UNITS=('nexydao-controller-firewall.service','nexydao-sec-collector.service','nexydao-research-consumer.service')


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate operator configuration field')
        result[key]=value
    return result


def operator_config(raw):
    if len(raw)>4096:raise ValueError('Operator config size limit')
    data=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(data,dict) or set(data)!={'issuers','user_agent'}:raise ValueError('Issuer/contact config required')
    issuers=data['issuers'];agent=data['user_agent']
    if not isinstance(issuers,list) or not 1<=len(issuers)<=3:raise ValueError('Bounded issuers required')
    symbols,ciks=set(),set()
    for issuer in issuers:
        if (not isinstance(issuer,dict) or set(issuer)!={'symbol','cik'}
                or not isinstance(issuer['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,11}',issuer['symbol'])
                or not isinstance(issuer['cik'],str) or not re.fullmatch('[0-9]{10}',issuer['cik']) or int(issuer['cik'])==0
                or issuer['symbol'] in symbols or issuer['cik'] in ciks):raise ValueError('Invalid operator issuer scope')
        symbols.add(issuer['symbol']);ciks.add(issuer['cik'])
    if (not isinstance(agent,str) or not 10<=len(agent)<=256 or any(ord(c)<32 or ord(c)>126 for c in agent)
            or not re.search(r'[A-Za-z0-9._+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',agent)):
        raise ValueError('Valid existing operator contact required')
    return data


def checked_archive(path,expected):
    if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Exact archive SHA-256 required')
    with Path(path).open('rb') as stream:raw=stream.read(10_000_001)
    if len(raw)>10_000_000 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Archive digest/size mismatch')
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members=archive.getmembers()
        if len(members)>500:raise ValueError('Archive entry limit')
        seen=set()
        for member in members:
            path=Path(member.name)
            if (path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir())
                    or member.name in seen or path.suffix in {'.pem','.key','.sqlite3','.sqlite','.db'} or path.name=='.env'):
                raise ValueError('Unsafe installation archive')
            seen.add(member.name)
    return raw


def environment_bytes(settings):
    return ''.join(key+'='+json.dumps(value,ensure_ascii=True)+'\n' for key,value in sorted(settings.items())).encode()


def run(arguments,timeout=30):
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','OPENSSL_CONF':'/dev/null','PYTHONDONTWRITEBYTECODE':'1'}
    result=subprocess.run(arguments,capture_output=True,timeout=timeout,env=env,cwd=CODE if CODE.is_dir() else None)
    if result.returncode:raise RuntimeError('Deployment command failed; inspect protected service state')
    return result.stdout


def write(path,raw,mode,uid=0,gid=0):
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(),mode);os.fchown(stream.fileno(),uid,gid);stream.write(raw)


def main():
    if sys.platform!='linux':raise ValueError('Linux systemd installation only')
    import pwd,grp
    parser=argparse.ArgumentParser(description='Fresh SEC-role installation: plan by default, --apply as root')
    parser.add_argument('--archive',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--operator-config',required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    raw=checked_archive(args.archive,args.sha256)
    with Path(args.operator_config).open('rb') as stream:scope=operator_config(stream.read(4097))
    targets=[CODE,CONFIG,PRIVATE,CONTROLLER,SHARED,Path('/usr/local/sbin/nexydao-controller-firewall'),
             *(Path('/etc/systemd/system')/unit for unit in UNITS)]
    if any(p.exists() or p.is_symlink() for p in targets):raise ValueError('Fresh targets required; no overwrite or upgrade')
    for name in ('nexydao-controller','nexydao-collector'):
        try:pwd.getpwnam(name)
        except KeyError:pass
        else:raise ValueError('Existing service account requires separate review')
    for name in ('nexydao-controller','nexydao-collector','nexydao-evidence'):
        try:grp.getgrnam(name)
        except KeyError:pass
        else:raise ValueError('Existing service group requires separate review')
    for parent in {p.parent for p in targets}:
        for component in (parent,*parent.parents):
            info=component.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
                raise ValueError('Protected installation ancestors required')
    print(json.dumps({'plan':'fresh_sec_roles','issuer_count':len(scope['issuers']),
        'creates_accounts':['nexydao-collector','nexydao-controller'],'creates_read_group':'nexydao-evidence',
        'new_key':'collector_owned_ed25519','existing_runtime_modified':False,'timers':False,'paid_calls':0,
        'starts_sec_collector_and_public_consumer':True,'applied':False}),flush=True)
    if not args.apply:return
    if os.geteuid()!=0:raise ValueError('Root apply required')
    os.umask(0o077)
    for name,home in (('nexydao-collector',PRIVATE),('nexydao-controller',CONTROLLER)):
        run(['/usr/sbin/useradd','--system','--user-group','--home-dir',str(home),'--no-create-home',
             '--shell','/usr/sbin/nologin',name])
    run(['/usr/sbin/groupadd','--system','nexydao-evidence'])
    collector=pwd.getpwnam('nexydao-collector');controller=pwd.getpwnam('nexydao-controller')
    readers=grp.getgrnam('nexydao-evidence').gr_gid
    for path,uid,gid,mode in ((PRIVATE,collector.pw_uid,collector.pw_gid,0o700),
            (CONTROLLER,controller.pw_uid,controller.pw_gid,0o700),(SHARED,collector.pw_uid,readers,0o2750),(CONFIG,0,0,0o755)):
        path.mkdir();os.chown(path,uid,gid);path.chmod(mode)
    CODE.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:archive.extractall(CODE,filter='data')
    for path in (CODE,*CODE.rglob('*')):
        os.chown(path,0,0);path.chmod(0o755 if path.is_dir() or path.suffix=='.sh' else 0o644)
    key=PRIVATE/'sec-signing.pem'
    run(['/usr/sbin/runuser','-u','nexydao-collector','--','/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(key)])
    key.chmod(0o600)
    public=run(['/usr/sbin/runuser','-u','nexydao-collector','--','/usr/bin/openssl','pkey','-in',str(key),
                '-passin','pass:','-pubout','-outform','DER'])
    if len(public)!=44 or not public.startswith(bytes.fromhex('302a300506032b6570032100')):
        raise ValueError('Unexpected generated public key')
    write(CONFIG/'sec-public.der',public,0o644)
    common={'NEXYDAO_RESEARCH_UNIVERSE':json.dumps(scope['issuers'],separators=(',',':')),
        'NEXYDAO_RESEARCH_CONCEPTS':'["Assets","NetIncomeLoss"]','NEXYDAO_RESEARCH_RECEIPT_MODE':'ed25519',
        'NEXYDAO_RESEARCH_PUBLIC_KEY_FILE':str(CONFIG/'sec-public.der'),
        'NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256':hashlib.sha256(public).hexdigest(),'NEXYDAO_OPENSSL_PATH':'/usr/bin/openssl'}
    signing={**common,'NEXYDAO_RESEARCH_SIGNING_KEY_FILE':str(key),'NEXYDAO_SEC_USER_AGENT':scope['user_agent'],
        'NEXYDAO_RESEARCH_SNAPSHOT':str(PRIVATE/'sec-research.json'),'NEXYDAO_RESEARCH_READ_GROUP':'nexydao-evidence'}
    write(CONFIG/'collector.env',environment_bytes(signing),0o600)
    write(CONFIG/'consumer.env',environment_bytes(common),0o600)
    write(Path('/usr/local/sbin/nexydao-controller-firewall'),(CODE/'ops/nexydao-controller-firewall.sh').read_bytes(),0o755)
    for unit in UNITS:write(Path('/etc/systemd/system')/unit,(CODE/'ops'/unit).read_bytes(),0o644)
    run(['/usr/bin/systemctl','daemon-reload'])
    run(['/usr/bin/systemctl','enable','--now',UNITS[0]])
    for phase in ('initial_start','bounded_restart'):
        print(json.dumps({'phase':phase}),flush=True)
        command='start' if phase=='initial_start' else 'restart'
        run(['/usr/bin/systemctl',command,UNITS[1]],timeout=330)
        run(['/usr/bin/systemctl',command,UNITS[2]],timeout=90)
    result=run(['/usr/bin/env','PYTHONPATH='+str(CODE),'/usr/bin/python3','-m','nexydao','service-isolation-check'])
    report=json.loads(result)
    if not report['sec_role_boundary_verified']:raise RuntimeError('Installed service audit failed')
    print(json.dumps({'applied':True,'sec_role_boundary_verified':True,'start_and_restart_passed':True,
                      'existing_runtime_modified':False,'paid_calls':0,'execution_authorized':False}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'applied_successfully':False,'error_type':type(error).__name__,
                          'action':'stop_and_review_partial_installation','execution_authorized':False}),flush=True)
        raise SystemExit(1)
