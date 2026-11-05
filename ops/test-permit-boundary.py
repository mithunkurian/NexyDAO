"""Root-only temporary three-role shadow fixture. No persistent provisioning.

Generated keys, fabricated intent and /run state only. No network/broker/API calls.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    if os.name!='posix' or os.geteuid()!=0:raise RuntimeError('Root required for isolated UID fixture')
    authorizer,consumer=65533,65534
    release=Path(__file__).resolve().parents[1]
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='nexydao-permit-boundary-',dir='/run') as temporary:
        root=Path(temporary);root.chmod(0o755)
        code=root/'app';package=code/'nexydao';package.mkdir(parents=True)
        code.chmod(0o755);package.chmod(0o755)
        for source in (release/'nexydao').glob('*.py'):
            destination=package/source.name
            shutil.copyfile(source,destination);destination.chmod(0o644)
        config=root/'config';config.mkdir();config.chmod(0o755)
        signer=root/'signer';signer.mkdir();os.chown(signer,authorizer,authorizer);signer.chmod(0o700)
        state=root/'consumer';state.mkdir();os.chown(state,consumer,consumer);state.chmod(0o700)
        env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(code),'PYTHONDONTWRITEBYTECODE':'1','OPENSSL_CONF':'/dev/null'}

        def run(uid,arguments,success=True):
            def identity():os.setgroups([]);os.setgid(uid);os.setuid(uid)
            result=subprocess.run(arguments,cwd=code,env=env,preexec_fn=identity,
                                  capture_output=True,text=True,timeout=30)
            if success and result.returncode:raise RuntimeError('Shadow role command failed: '+result.stderr[-500:])
            return result

        def python(uid,script,*arguments,success=True):
            return run(uid,[sys.executable,'-c',script,*map(str,arguments)],success)

        key=signer/'shadow.pem';derived=signer/'public.der';public=config/'public.der'
        run(authorizer,['/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(key)])
        run(authorizer,['/usr/bin/openssl','pkey','-in',str(key),'-passin','pass:','-pubout','-outform','DER','-out',str(derived)])
        public.write_bytes(derived.read_bytes());public.chmod(0o644)
        pin=hashlib.sha256(public.read_bytes()).hexdigest()
        # Import only from the root-owned copy, never writable release code.
        sys.path.insert(0,str(code))
        from nexydao.owner_policy import BASE,load_policy
        from nexydao.permit_control import AuthorityControl
        from nexydao.paper_permits import PermitError
        policy_path=config/'owner-policy.json';policy_path.write_text(json.dumps(BASE));policy_path.chmod(0o644)
        policy=load_policy(policy_path)
        control=AuthorityControl(config/'control.json');control.initialize()
        try:control.epoch(policy)
        except PermitError:pass
        else:raise RuntimeError('New control was not stopped')
        control.arm(policy)
        intent={'account':'DU123456','contract_id':123,'symbol':'TEST','currency':'USD','side':'BUY',
            'quantity':'1','limit_price_usd':'100','fee_cap_usd':'1','max_debit_usd':'101',
            'reservation_id':'a'*32,'quote_sha256':'b'*64,'portfolio_sha256':'c'*64,'review_sha256':'d'*64}
        intent_path=config/'intent.json';intent_path.write_text(json.dumps(intent));intent_path.chmod(0o644)
        receipt=signer/'permit.json';ledger=state/'shadow.sqlite3'
        prelude='''import json,sys
from pathlib import Path
from nexydao.owner_policy import load_policy
from nexydao.permit_control import AuthorityControl
from nexydao.paper_permits import ShadowLedger,issue_shadow,consume_shadow,PermitError
from nexydao.research_signatures import DEFAULT_OPENSSL
policy=load_policy(Path(sys.argv[1]));control=AuthorityControl(Path(sys.argv[2]))
intent=json.loads(Path(sys.argv[3]).read_text())
'''
        arguments=(policy_path,control.path,intent_path)
        issue=prelude+'''receipt=issue_shadow(intent,policy,control,Path(sys.argv[4]),Path(sys.argv[5]),sys.argv[6],DEFAULT_OPENSSL)
Path(sys.argv[7]).write_text(json.dumps(receipt))
'''
        python(authorizer,issue,*arguments,key,public,pin,receipt)
        published=config/'permit.json';published.write_bytes(receipt.read_bytes());published.chmod(0o644)
        init=prelude+'''ShadowLedger(Path(sys.argv[4]),authority=control).initialize()
'''
        python(consumer,init,*arguments,ledger)
        consume=prelude+'''ledger=ShadowLedger(Path(sys.argv[4]),authority=control)
try:
 result=consume_shadow(Path(sys.argv[5]).read_bytes(),intent,policy,ledger,Path(sys.argv[6]),sys.argv[7],DEFAULT_OPENSSL)
except PermitError as error:
 print(json.dumps({'denied':str(error)}));raise SystemExit(2)
print(json.dumps(result))
'''
        def redeem(success=True):return python(consumer,consume,*arguments,ledger,published,public,pin,success=success)
        result=json.loads(redeem().stdout)
        assert result=={'status':'shadow_permit_consumed','execution_authorized':False,'broker_submission':False}
        assert 'replay' in redeem(False).stdout
        # Genuine OS denials, including attempts to mint with the signer key.
        probe='''import sys,json
denied=0
for name,mode in zip(sys.argv[1::2],sys.argv[2::2]):
 try:
  with open(name,mode):pass
 except PermissionError:denied+=1
 else:raise RuntimeError('Protected access unexpectedly allowed')
print(json.dumps({'denied':denied}))
'''
        consumer_denied=json.loads(python(consumer,probe,key,'rb',control.path,'wb',control.lock,'wb',
            policy_path,'wb',public,'wb',package/'paper_permits.py','ab').stdout)['denied']
        signer_denied=json.loads(python(authorizer,probe,ledger,'rb',control.path,'wb',control.lock,'wb',
            policy_path,'wb',package/'paper_permits.py','ab').stdout)['denied']
        assert consumer_denied==6 and signer_denied==5
        assert python(consumer,issue,*arguments,key,public,pin,state/'forged.json',success=False).returncode!=0
        forbidden=prelude+'''ledger=ShadowLedger(Path(sys.argv[4]),authority=control)
denied=0
for operation in (control.stop,lambda:control.arm(policy),lambda:ledger.arm(policy),ledger.stop):
 try:operation()
 except PermitError:denied+=1
 else:raise RuntimeError('Role changed owner control')
print(json.dumps({'denied':denied}))
'''
        assert json.loads(python(consumer,forbidden,*arguments,ledger).stdout)['denied']==4
        assert json.loads(python(authorizer,forbidden,*arguments,signer/'unused.sqlite3').stdout)['denied']==4
        # Mint a fresh unused nonce, stop as owner, then reopen as consumer.
        python(authorizer,issue,*arguments,key,public,pin,receipt)
        published.write_bytes(receipt.read_bytes())
        control.stop()
        assert 'stopped' in redeem(False).stdout
        control=AuthorityControl(control.path)
        try:control.epoch(policy)
        except PermitError:pass
        else:raise RuntimeError('Reopen lost owner stop')
        control.arm(policy)
        assert 'epoch' in redeem(False).stdout
        python(authorizer,issue,*arguments,key,public,pin,receipt)
        published.write_bytes(receipt.read_bytes())
        assert json.loads(redeem().stdout)['execution_authorized'] is False
        # A cooperative shared lock must prevent an owner transition until release.
        with control.locked_epoch(policy):
            try:control.stop()
            except PermitError as error:assert str(error)=='shadow_control_busy'
            else:raise RuntimeError('Stop changed state during a guarded commit')
        control.stop()
        assert 'stopped' in redeem(False).stdout
        # Verify corruption, unsafe permissions and symlinks do not silently arm.
        original=control.path.read_bytes();control.path.write_bytes(b'{')
        try:control.epoch(policy)
        except PermitError:pass
        else:raise RuntimeError('Corrupt control accepted')
        control.path.write_bytes(original)
        control.path.chmod(0o666)
        assert redeem(False).returncode!=0
        control.path.chmod(0o644)
        saved=config/'saved-control.json';control.path.rename(saved);control.path.symlink_to(saved)
        assert redeem(False).returncode!=0
        control.path.unlink();saved.rename(control.path)
        summary={'temporary_three_role_fixture':True,'consumer_protected_denials':consumer_denied,
            'signer_protected_denials':signer_denied,'role_control_operations_denied':8,
            'consumer_mint_denied':True,'replay_after_reopen_denied':True,'stop_rearm_epoch_checks_passed':True,
            'owner_transition_lock_checked':True,'unsafe_control_rejected':True,
            'host_accounts_services_rules_changed':False,'production_runtime_used':False,
            'paid_calls':0,'execution_authorized':False}
    print(json.dumps(summary))


if __name__=='__main__':main()
