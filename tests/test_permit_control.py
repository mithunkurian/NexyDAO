from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nexydao.owner_policy import load_policy
from nexydao.paper_permits import PermitError, ShadowLedger
from nexydao.permit_control import AuthorityControl, parse_control


class PermitControlTests(unittest.TestCase):
    def test_strict_bounded_stopped_and_armed_documents(self):
        stopped={'schema_version':1,'stopped':True,'epoch':'a'*32,'policy_sha256':''}
        armed={**stopped,'stopped':False,'policy_sha256':'b'*64}
        for data in (stopped,armed):self.assertEqual(parse_control(json.dumps(data).encode()),data)
        for data in ({**stopped,'stopped':1},{**stopped,'schema_version':True},
                     {**stopped,'epoch':'bad'},{**stopped,'policy_sha256':'b'*64},
                     {**armed,'policy_sha256':''},{**armed,'extra':True}):
            with self.subTest(data=data),self.assertRaises(PermitError):parse_control(json.dumps(data).encode())
        for raw in (b'x'*2049,b'{"stopped":true,"stopped":false}',b'NaN',b'\xff'):
            with self.assertRaises(PermitError):parse_control(raw)

    def test_unprivileged_roles_cannot_initialize_arm_or_stop(self):
        control=AuthorityControl(Path.cwd()/'not-created-control.json')
        with patch('nexydao.permit_control.os.geteuid',return_value=123,create=True):
            for operation in (control.initialize,control.stop,lambda:control.arm(load_policy())):
                with self.assertRaisesRegex(PermitError,'owner_required'):operation()
        self.assertFalse(control.path.exists());self.assertFalse(control.lock.exists())

    def test_relative_paths_and_unprotected_policy_are_refused(self):
        with self.assertRaises(PermitError):AuthorityControl('relative.json')
        with self.assertRaises(PermitError):AuthorityControl._policy(load_policy())

    def test_external_authority_cannot_be_rearmed_through_consumer_ledger(self):
        ledger=ShadowLedger(Path.cwd()/'not-created-ledger.sqlite3',authority=object())
        for operation in (ledger.stop,lambda:ledger.arm(load_policy())):
            with self.assertRaisesRegex(PermitError,'external_owner'):operation()
        self.assertFalse(ledger.path.exists())

    def test_external_shared_guard_spans_sqlite_commit(self):
        # Exercise real SQLite consumption and observe transaction completion
        # before releasing the cooperative authority's shared guard.
        root=Path(__file__).resolve().parents[1]/'data';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            directory=Path(temporary);directory.chmod(0o700);events=[]
            class Authority:
                @contextmanager
                def locked_epoch(self,policy):
                    events.append('locked')
                    yield 'a'*32
                    import sqlite3
                    with closing(sqlite3.connect(directory/'shadow.sqlite3')) as connection:
                        events.append(connection.execute('SELECT count(*) FROM consumed').fetchone()[0])
                    events.append('unlocked')
            ledger=ShadowLedger(directory/'shadow.sqlite3',authority=Authority());ledger.initialize()
            policy=load_policy()
            intent={'account':'DU123','contract_id':123,'symbol':'TEST','currency':'USD','side':'BUY',
                'quantity':'1','limit_price_usd':'10','fee_cap_usd':'1','max_debit_usd':'11',
                'reservation_id':'b'*32,'quote_sha256':'c'*64,'portfolio_sha256':'d'*64,'review_sha256':'e'*64}
            payload={'schema_version':1,'purpose':'paper_shadow_only','mode':'paper','intent':intent,
                'policy_sha256':policy.digest,'policy_version':1,'epoch':'a'*32,'nonce':'f'*32,
                'issued_at':1000,'expires_at':1030}
            ledger._consume(payload,intent,policy,1001)
            self.assertEqual(events,['locked',1,'unlocked'])

    @unittest.skipUnless(os.name=='posix','Unix path permissions')
    def test_unprivileged_writable_ancestor_or_symlink_control_is_refused(self):
        root=Path(__file__).resolve().parents[1]/'data';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            control=AuthorityControl(Path(temporary)/'control.json')
            with self.assertRaises(PermitError):control.epoch(load_policy())
