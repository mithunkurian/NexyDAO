from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nexydao import paper_permits as permits
from nexydao import research_signatures as signatures
from nexydao.owner_policy import BASE, OwnerPolicy, OwnerPolicyError, load_policy
from nexydao.safety import PaperBroker
from nexydao.config import Config


@unittest.skipUnless(signatures.DEFAULT_OPENSSL.is_file(),'Protected OpenSSL unavailable')
class PaperPermitTests(unittest.TestCase):
    def setUp(self):
        data=Path(__file__).resolve().parents[1]/'data';data.mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=data)
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700)
        self.private=self.root/'fixture.pem';self.public=self.root/'fixture.der'
        self.private.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,['genpkey','-algorithm','ED25519']))
        self.private.chmod(0o600)
        self.public.write_bytes(signatures._command(signatures.DEFAULT_OPENSSL,
            ['pkey','-in',str(self.private),'-passin','pass:','-pubout','-outform','DER']))
        self.public.chmod(0o644)
        self.pin=hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.policy=load_policy()
        self.ledger=permits.ShadowLedger(self.root/'shadow.sqlite3');self.ledger.initialize()
        self.ledger.arm(self.policy)
        self.intent={'account':'DU123456','contract_id':123,'symbol':'TEST','currency':'USD','side':'BUY',
            'quantity':'2','limit_price_usd':'100','fee_cap_usd':'1','max_debit_usd':'201',
            'reservation_id':'a'*32,'quote_sha256':'b'*64,'portfolio_sha256':'c'*64,'review_sha256':'d'*64}

    def issue(self,**kwargs):
        return permits.issue_shadow(self.intent,self.policy,self.ledger,self.private,self.public,self.pin,
                                    signatures.DEFAULT_OPENSSL,now=1000,**kwargs)

    def consume(self,receipt,**kwargs):
        return permits.consume_shadow(json.dumps(receipt).encode(),kwargs.pop('intent',self.intent),
            kwargs.pop('policy',self.policy),kwargs.pop('ledger',self.ledger),self.public,self.pin,
            signatures.DEFAULT_OPENSSL,now=kwargs.pop('now',1001),**kwargs)

    def test_public_only_consumer_never_authorizes_or_submits(self):
        receipt=self.issue();self.private.unlink()
        result=self.consume(receipt)
        self.assertEqual(result,{'status':'shadow_permit_consumed','execution_authorized':False,'broker_submission':False})
        with self.assertRaises(PermissionError):PaperBroker().execute(receipt)
        with patch.dict(os.environ,{'NEXYDAO_EXECUTION_ENABLED':'true'}),self.assertRaises(ValueError):Config.from_env()

    def test_cross_domain_research_and_shadow_signatures_are_incompatible(self):
        receipt=self.issue()
        with self.assertRaises(signatures.ReceiptSignatureError):
            signatures.verify(receipt,self.public,self.pin,signatures.DEFAULT_OPENSSL)
        research=signatures.sign(receipt['payload'],self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL)
        with self.assertRaises(permits.PermitError):self.consume(research)

    def test_replay_is_denied_after_reopening_without_reset(self):
        receipt=self.issue();self.consume(receipt)
        reopened=permits.ShadowLedger(self.ledger.path)
        with self.assertRaises(FileExistsError):reopened.initialize()
        with self.assertRaisesRegex(permits.PermitError,'replay'):self.consume(receipt,ledger=reopened)

    def test_concurrent_consumers_get_exactly_one_success(self):
        receipt=self.issue()
        def attempt(_):
            try:self.consume(receipt,ledger=permits.ShadowLedger(self.ledger.path));return True
            except permits.PermitError:return False
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(attempt,range(6))),1)

    def test_default_stop_and_stop_survives_restart(self):
        other=permits.ShadowLedger(self.root/'new.sqlite3');other.initialize()
        with self.assertRaisesRegex(permits.PermitError,'stopped'):other.epoch(self.policy)
        receipt=self.issue();self.ledger.stop()
        with self.assertRaisesRegex(permits.PermitError,'stopped'):
            self.consume(receipt,ledger=permits.ShadowLedger(self.ledger.path))

    def test_rearm_revokes_outstanding_permits_and_keeps_replay_history(self):
        old=self.issue();self.ledger.stop();self.ledger.arm(self.policy)
        with self.assertRaisesRegex(permits.PermitError,'epoch'):self.consume(old)
        current=self.issue();self.consume(current);self.ledger.arm(self.policy)
        # Even a freshly signed copy of the used nonce in the new epoch is denied.
        payload=current['payload'];payload['epoch']=self.ledger.epoch(self.policy)
        signed=signatures.sign(payload,self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=permits.DOMAIN)
        with self.assertRaisesRegex(permits.PermitError,'replay'):self.consume(signed)

    def test_stop_between_signature_check_and_transaction_blocks_consumption(self):
        receipt=self.issue();verify=signatures.verify
        def stop_after_verifying(*args,**kwargs):
            verify(*args,**kwargs);self.ledger.stop()
        with patch.object(signatures,'verify',side_effect=stop_after_verifying):
            with self.assertRaisesRegex(permits.PermitError,'stopped'):self.consume(receipt)

    def test_every_expected_intent_field_is_bound_and_failure_does_not_consume(self):
        receipt=self.issue()
        changes={'account':'DU654321','contract_id':124,'symbol':'OTHER','currency':'EUR','side':'SELL',
            'quantity':'1','limit_price_usd':'99','fee_cap_usd':'0','max_debit_usd':'202',
            'reservation_id':'e'*32,'quote_sha256':'e'*64,'portfolio_sha256':'e'*64,'review_sha256':'e'*64}
        for name,value in changes.items():
            with self.subTest(name=name),self.assertRaises(permits.PermitError):
                self.consume(receipt,intent={**self.intent,name:value})
        self.consume(receipt)

    def test_expiry_future_clock_and_maximum_ttl(self):
        receipt=self.issue(ttl=30)
        for now in (999,1030,2000,True):
            with self.subTest(now=now),self.assertRaises(permits.PermitError):self.consume(receipt,now=now)
        for ttl in (0,61,True):
            with self.subTest(ttl=ttl),self.assertRaises(permits.PermitError):self.issue(ttl=ttl)
        self.consume(receipt,now=1029)

    def test_expiry_is_checked_after_signature_verification(self):
        receipt=self.issue();verify=signatures.verify;clock=[1001]
        def advance_after_verification(*args,**kwargs):
            verify(*args,**kwargs);clock[0]=1030
        with patch.object(signatures,'verify',side_effect=advance_after_verification), \
                patch('nexydao.paper_permits.time.time',side_effect=lambda:clock[0]):
            with self.assertRaises(permits.PermitError):
                permits.consume_shadow(json.dumps(receipt).encode(),self.intent,self.policy,self.ledger,
                    self.public,self.pin,signatures.DEFAULT_OPENSSL)
        self.consume(receipt)

    def test_invalid_signatures_pins_and_algorithm_do_not_burn_valid_nonce(self):
        receipt=self.issue()
        for field,value in (('signature','00'*64),('key_sha256','e'*64),('algorithm','hmac-sha256')):
            with self.subTest(field=field),self.assertRaises(permits.PermitError):self.consume({**receipt,field:value})
        self.consume(receipt)

    def test_signed_wrong_purpose_mode_or_schema_fails(self):
        original=self.issue()
        for field,value in (('purpose','execute_order'),('mode','live'),('schema_version',True),
                            ('policy_version',2),('policy_sha256','e'*64),('expires_at',1061)):
            payload={**original['payload'],field:value}
            receipt=signatures.sign(payload,self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=permits.DOMAIN)
            with self.subTest(field=field),self.assertRaises(permits.PermitError):self.consume(receipt)
        self.consume(original)

    def test_signed_boolean_or_float_contract_cannot_equal_expected_integer(self):
        self.intent['contract_id']=1
        original=self.issue()
        for value in (True,1.0):
            payload={**original['payload'],'intent':{**self.intent,'contract_id':value}}
            receipt=signatures.sign(payload,self.private,self.public,self.pin,signatures.DEFAULT_OPENSSL,domain=permits.DOMAIN)
            with self.subTest(value=value),self.assertRaises(permits.PermitError):self.consume(receipt)
        self.consume(original)

    def test_owner_policy_version_change_and_file_change_invalidate(self):
        receipt=self.issue()
        changed=OwnerPolicy(json.dumps({**BASE,'policy_version':2},sort_keys=True,separators=(',',':')).encode())
        with self.assertRaises(permits.PermitError):self.consume(receipt,policy=changed)
        path=self.root/'policy.json';path.write_bytes(self.policy.payload);path.chmod(0o600)
        current=load_policy(path);path.write_bytes(changed.payload)
        with self.assertRaises(OwnerPolicyError):self.consume(receipt,policy=current)
        self.consume(receipt)

    def test_underfunded_debit_oversizing_wrong_account_and_unsupported_rules_fail(self):
        for field,value in (('max_debit_usd','200'),('max_debit_usd','501'),('account','U123456'),
                            ('contract_id',True),('quantity','NaN'),('quantity','-1'),('limit_price_usd','0')):
            with self.subTest(field=field),self.assertRaises(permits.PermitError):
                permits.validate_intent({**self.intent,field:value},self.policy)
        for change in ({'blocked_symbols':['TEST']},{'max_position_usd':'100'},
                       {'additional_rules':[{'id':'manual','text':'Unimplemented independent rule'}]}):
            policy=OwnerPolicy(json.dumps({**BASE,**change}).encode())
            with self.assertRaises(permits.PermitError):permits.validate_intent(self.intent,policy)

    def test_bounded_strict_json_and_private_ledger_metadata(self):
        for raw in (b'x'*8193,b'{"payload":1,"payload":2}',b'NaN',b'\xff',b'['*2000):
            with self.subTest(raw=raw[:20]),self.assertRaises(permits.PermitError):permits.decode(raw)
        if os.name=='posix':
            self.ledger.path.chmod(0o644)
            with self.assertRaises(permits.PermitError):self.ledger.epoch(self.policy)

    def test_ledger_capacity_stops_without_pruning_history(self):
        receipt=self.issue()
        with self.ledger._transaction() as connection:
            connection.executemany('INSERT INTO consumed VALUES (?,?,?)',
                                   ((str(i),'0'*64,999) for i in range(10000)))
        with self.assertRaisesRegex(permits.PermitError,'capacity'):self.consume(receipt)
