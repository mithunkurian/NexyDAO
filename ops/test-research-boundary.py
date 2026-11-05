"""Root-only two-UID fixture under a temporary /run tree; no host users/services.

Generates synthetic facts/test keys. Never reads or changes the private runtime.
"""
from datetime import datetime,timezone,timedelta
import grp
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def main():
    if os.geteuid()!=0:
        raise RuntimeError('Root required for isolated fixture UID switching')
    collector,consumer=65533,65534
    group=grp.getgrgid(consumer).gr_name
    release=Path(__file__).resolve().parents[1]
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='nexydao-boundary-',dir='/run') as temporary:
        root=Path(temporary);root.chmod(0o755)
        code=root/'app';package=code/'nexydao'
        code.mkdir();code.chmod(0o755)
        package.mkdir();package.chmod(0o755)
        for source in (release/'nexydao').glob('*.py'):
            target=package/source.name
            shutil.copyfile(source,target);target.chmod(0o644)
        private=root/'collector';private.mkdir();os.chown(private,collector,collector);private.chmod(0o700)
        shared=root/'evidence';shared.mkdir();os.chown(shared,collector,consumer);shared.chmod(0o2750)
        config=root/'config';config.mkdir();config.chmod(0o755)
        key=private/'signing.pem';local_public=private/'public.der';public=config/'public.der'
        env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(code),'PYTHONDONTWRITEBYTECODE':'1',
             'OPENSSL_CONF':'/dev/null','NEXYDAO_BROKER_MODE':'paper','NEXYDAO_EXECUTION_ENABLED':'false'}

        def run(uid,gid,arguments,settings=None,success=True):
            def identity():
                os.setgroups([]);os.setgid(gid);os.setuid(uid)
            result=subprocess.run(arguments,env=settings or env,cwd=code,preexec_fn=identity,
                                  capture_output=True,text=True,timeout=30)
            if success and result.returncode!=0:
                raise RuntimeError('Fixture role command failed: '+result.stderr[-500:])
            return result

        run(collector,collector,['/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(key)])
        run(collector,collector,['/usr/bin/openssl','pkey','-in',str(key),'-passin','pass:',
                                 '-pubout','-outform','DER','-out',str(local_public)])
        public.write_bytes(local_public.read_bytes());public.chmod(0o644)
        pin=hashlib.sha256(public.read_bytes()).hexdigest()
        issuer={'symbol':'TEST','cik':'0000000123'}
        now=int(time.time());today=datetime.fromtimestamp(now,timezone.utc).date()
        facts=[]
        for concept in ('Assets','NetIncomeLoss'):
            facts.append({**issuer,'concept':concept,'unit':'USD','value':'100',
                          'start':'' if concept=='Assets' else (today-timedelta(days=100)).isoformat(),
                          'end':(today-timedelta(days=20)).isoformat(),'filed':(today-timedelta(days=10)).isoformat(),
                          'form':'10-Q','accession':'0000000123-26-000001'})
        paths=['/submissions/CIK0000000123.json',
               '/api/xbrl/companyconcept/CIK0000000123/us-gaap/Assets.json',
               '/api/xbrl/companyconcept/CIK0000000123/us-gaap/NetIncomeLoss.json']
        payload={'schema_version':2,'concepts':['Assets','NetIncomeLoss'],'source':'sec_companyconcept',
                 'retrieved_at':now,'expires_at':now+86400,'issuers':[issuer],'facts':facts,
                 'sources':[{'path':path,'sha256':'a'*64} for path in paths]}
        payload_path=config/'synthetic.json';payload_path.write_text(json.dumps(payload));payload_path.chmod(0o644)
        settings={**env,'NEXYDAO_RESEARCH_UNIVERSE':json.dumps([issuer]),
                  'NEXYDAO_RESEARCH_RECEIPT_MODE':'ed25519','NEXYDAO_RESEARCH_PUBLIC_KEY_FILE':str(public),
                  'NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256':pin,'NEXYDAO_RESEARCH_READ_GROUP':group}
        protected_config=config/'consumer.json';protected_config.write_text(json.dumps(settings));protected_config.chmod(0o644)
        source=private/'receipt.json';destination=shared/'receipt.json'
        signer='''import json,sys
from pathlib import Path
from nexydao.research_signatures import sign,DEFAULT_OPENSSL
from nexydao.ibkr import save_snapshot
payload=json.loads(Path(sys.argv[1]).read_text())
receipt=sign(payload,Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],DEFAULT_OPENSSL)
save_snapshot(Path(sys.argv[5]),receipt)
'''
        run(collector,collector,[sys.executable,'-c',signer,str(payload_path),str(key),str(public),pin,str(source)],settings)
        publication=run(collector,collector,[sys.executable,'-m','nexydao','research-publish',
                          '--research-evidence',str(source),'--published-evidence',str(destination)],settings)
        assert json.loads(publication.stdout)['facts']==2
        assert destination.stat().st_gid==consumer and destination.stat().st_mode & 0o777==0o640
        checked=run(consumer,consumer,[sys.executable,'-m','nexydao','research-receipt-check',
                                     '--research-evidence',str(destination)],settings)
        assert json.loads(checked.stdout)['facts']==2
        probe='''from pathlib import Path
import json,os,sys
denied=0
for name,mode in zip(sys.argv[1:],('rb','wb','wb','wb','ab')):
 try:
  with open(name,mode):pass
 except PermissionError:denied+=1
 else:raise RuntimeError('Consumer accessed protected target')
print(json.dumps({'uid':os.geteuid(),'denied':denied}))
'''
        result=run(consumer,consumer,[sys.executable,'-c',probe,str(key),str(destination),
                   str(shared/'new.json'),str(protected_config),str(package/'sec.py')],settings)
        assert json.loads(result.stdout)=={'uid':consumer,'denied':5}
        rejected=run(consumer,consumer,[sys.executable,'-m','nexydao','research-publish',
                     '--research-evidence',str(destination),'--published-evidence',str(destination)],settings,success=False)
        assert rejected.returncode!=0
        assert not list(root.rglob('*.sqlite3'))
        summary={'isolated_uid_fixture':True,'collector_uid_distinct_from_consumer':True,'verified_facts':2,
                 'consumer_protected_accesses_denied':5,'consumer_republication_denied':True,
                 'paid_calls':0,'production_runtime_used':False,'host_accounts_services_rules_changed':False,
                 'execution_authorized':False}
    print(json.dumps(summary))


if __name__=='__main__':
    main()
