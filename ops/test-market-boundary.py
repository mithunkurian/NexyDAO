"""Root-only temporary two-UID quote signer/public-consumer acceptance.

Generated quotes/keys and /run files only. No broker, API, host provisioning or
existing runtime access. Root copying a fixture receipt is not a production publisher.
"""
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
    if os.name!='posix' or os.geteuid()!=0:raise RuntimeError('Root required for temporary identity fixture')
    signer,consumer=65533,65534
    release=Path(__file__).resolve().parents[1]
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='nexydao-market-boundary-',dir='/run') as temporary:
        root=Path(temporary);root.chmod(0o755)
        code=root/'app';package=code/'nexydao';package.mkdir(parents=True);code.chmod(0o755);package.chmod(0o755)
        for source in (release/'nexydao').glob('*.py'):
            destination=package/source.name;shutil.copyfile(source,destination);destination.chmod(0o644)
        private=root/'signer';private.mkdir();os.chown(private,signer,signer);private.chmod(0o700)
        state=root/'consumer';state.mkdir();os.chown(state,consumer,consumer);state.chmod(0o700)
        config=root/'config';config.mkdir();config.chmod(0o755)
        key=private/'market.pem';derived=private/'public.der';public=config/'public.der'
        legacy=private/'legacy.key';legacy.write_bytes(b'x'*32);os.chown(legacy,signer,signer);legacy.chmod(0o600)
        env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(code),'PYTHONDONTWRITEBYTECODE':'1','OPENSSL_CONF':'/dev/null',
             'NEXYDAO_BROKER_MODE':'paper','NEXYDAO_EXECUTION_ENABLED':'false'}
        def run(uid,arguments,settings=None):
            def identity():os.setgroups([]);os.setgid(uid);os.setuid(uid)
            result=subprocess.run(arguments,cwd=code,env=settings or env,preexec_fn=identity,
                                  capture_output=True,text=True,timeout=30)
            if result.returncode:raise RuntimeError('Market fixture command failed: '+result.stderr[-500:])
            return result
        run(signer,['/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(key)])
        run(signer,['/usr/bin/openssl','pkey','-in',str(key),'-passin','pass:','-pubout','-outform','DER','-out',str(derived)])
        public.write_bytes(derived.read_bytes());public.chmod(0o644);pin=hashlib.sha256(public.read_bytes()).hexdigest()
        now=int(time.time())
        payload={'schema_version':1,'source':'ibkr_paper_tick_by_tick_bid_ask','protocol_version':178,
            'account_sha256':hashlib.sha256(b'DU123').hexdigest(),
            'contract':{'con_id':123,'symbol':'TEST','security_type':'STK','currency':'USD','exchange':'SMART','primary_exchange':'ARCA'},
            'quote':{'bid':'100','ask':'101','bid_size':'10','ask_size':'10','event_time':now,'flags':0},
            'received_at':now,'expires_at':now+60,'raw_sha256':'a'*64}
        fixture=config/'synthetic.json';fixture.write_text(json.dumps(payload));fixture.chmod(0o644)
        source=private/'quote.json';published=config/'quote.json'
        settings={**env,'NEXYDAO_IBKR_EXPECTED_ACCOUNT':'DU123','NEXYDAO_MARKET_SYMBOL':'TEST',
            'NEXYDAO_MARKET_RECEIPT_MODE':'ed25519','NEXYDAO_MARKET_PUBLIC_KEY_FILE':str(public),
            'NEXYDAO_MARKET_PUBLIC_KEY_SHA256':pin,'NEXYDAO_MARKET_SIGNING_KEY_FILE':str(key),
            'NEXYDAO_EVIDENCE_KEY_FILE':str(legacy),'NEXYDAO_MARKET_SNAPSHOT':str(source)}
        sign='''import json,sys
from pathlib import Path
from unittest.mock import patch
from nexydao.market import MarketConfig,run_market_check
payload=json.loads(Path(sys.argv[1]).read_text())
with patch('nexydao.market.collect',return_value=payload):result=run_market_check(MarketConfig.from_env())
assert result['receipt_mode']=='ed25519' and result['execution_authorized'] is False
'''
        run(signer,[sys.executable,'-c',sign,str(fixture)],settings)
        published.write_bytes(source.read_bytes());published.chmod(0o644)
        report=run(consumer,[sys.executable,'-m','nexydao','quote-liquidity-report','--market-evidence',str(published)],settings)
        result=json.loads(report.stdout)
        assert result['quotes'][0]['spread_within_limit'] and not result['market_liquidity_verified']
        consume='''import json,sys
from pathlib import Path
from nexydao.market import MarketConfig,load_market_evidence
from nexydao.store import Store
from nexydao.portfolio import Portfolio
from nexydao.owner_policy import load_policy
from nexydao.workflow import run_cycle
from nexydao.cli import DemoProvider
store=Store(Path(sys.argv[2]))
try:
 ledger=Portfolio(store)
 ledger.fill({'id':'fixture','side':'buy','symbol':'TEST','quantity':'1','price':'100','fee':'0','currency':'USD','asset_type':'STK'},load_policy())
 config=MarketConfig.from_env();assert config.key_path is None
 ledger.mark(Path(sys.argv[1]),config)
 assert ledger.snapshot()['positions'][0]['contract_id']==123
 result=run_cycle(store,DemoProvider(),load_market_evidence(Path(sys.argv[1]),config))
 assert result['policy']['execution_authorized'] is False and store.costs()['calls']==0
finally:store.close()
'''
        db=state/'simulation.sqlite3'
        run(consumer,[sys.executable,'-c',consume,str(published),str(db)],settings)
        probe='''import json,sys
denied=0
for name,mode in zip(sys.argv[1::2],sys.argv[2::2]):
 try:
  with open(name,mode):pass
 except PermissionError:denied+=1
 else:raise RuntimeError('Protected fixture access unexpectedly succeeded')
print(json.dumps({'denied':denied}))
'''
        checked=run(consumer,[sys.executable,'-c',probe,str(key),'rb',str(legacy),'rb',str(published),'wb',
                              str(public),'wb',str(package/'market.py'),'ab'],settings)
        assert json.loads(checked.stdout)['denied']==5
        assert json.loads(run(signer,[sys.executable,'-c',probe,str(db),'rb'],settings).stdout)['denied']==1
        summary={'temporary_two_uid_fixture':True,'public_quote_report_passed':True,'public_marking_and_advisory_passed':True,
            'consumer_protected_accesses_denied':5,'signer_consumer_database_access_denied':True,
            'paid_calls':0,'real_broker_queries':0,'production_runtime_used':False,
            'host_accounts_services_rules_changed':False,'market_liquidity_verified':False,'execution_authorized':False}
    print(json.dumps(summary))


if __name__=='__main__':main()
