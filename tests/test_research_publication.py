import copy
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_research_signatures as fixtures
from nexydao.cli import main
from nexydao.research_publication import PublicationError, publish_research, valid_directory
from nexydao.research_signatures import DEFAULT_OPENSSL
from nexydao.sec import SourceError


class PublicationBoundaryTests(unittest.TestCase):
    def test_only_collector_owned_setgid_reader_directory_is_accepted(self):
        info=SimpleNamespace(st_mode=stat.S_IFDIR | 0o2750,st_uid=1234,st_gid=2345)
        self.assertTrue(valid_directory(info,1234,2345))
        for mode in (0o2770,0o2755,0o0750,0o0700):
            changed=copy.copy(info);changed.st_mode=stat.S_IFDIR | mode
            self.assertFalse(valid_directory(changed,1234,2345))
        for uid,gid in ((0,2345),(1234,0),(999,2345),(1234,999),(True,2345)):
            self.assertFalse(valid_directory(info,uid,gid))
        changed=copy.copy(info);changed.st_mode=stat.S_IFLNK | 0o2750
        self.assertFalse(valid_directory(changed,1234,2345))

    def test_cli_requires_explicit_destination_and_never_opens_db(self):
        with patch('sys.argv',['nexydao','research-publish','--research-evidence','unused']), \
                patch.dict(os.environ,{},clear=True),patch('nexydao.cli.Store') as store,patch('sys.stderr'):
            with self.assertRaises(SystemExit):main()
        store.assert_not_called()


@unittest.skipUnless(DEFAULT_OPENSSL.is_file(),'Optional OpenSSL unavailable')
class ReceiptCheckTests(unittest.TestCase):
    def test_public_receipt_check_does_not_call_provider_or_open_db(self):
        fixture=fixtures.ResearchSignatureTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.receipt()
        fixture.private.unlink();fixture.fixture.key.unlink()
        with patch('sys.argv',['nexydao','research-receipt-check','--research-evidence',str(fixture.config.snapshot)]), \
                patch.dict(os.environ,{},clear=True), \
                patch('nexydao.sec.ResearchConfig.from_env',return_value=fixture.config), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider,patch('sys.stdout'):
            main()
        store.assert_not_called();provider.assert_not_called()


@unittest.skipUnless(os.name=='posix' and getattr(os,'geteuid',lambda:0)()!=0
                     and getattr(os,'getegid',lambda:0)()!=0,'Unprivileged Unix filesystem tests')
class PublicationFilesystemTests(unittest.TestCase):
    def setUp(self):
        import grp
        self.fixture=fixtures.ResearchSignatureTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.receipt()
        self.folder=self.fixture.root/'shared';self.folder.mkdir();self.folder.chmod(0o2750)
        self.destination=self.folder/'receipt.json'
        self.group=grp.getgrgid(os.getegid()).gr_name

    def publish(self,clock=None):
        # A normal unit-test user cannot create root-owned ancestors. The separate
        # root/UID acceptance fixture validates that deployment boundary directly.
        kwargs={} if clock is None else {'clock':clock}
        with patch('nexydao.research_publication._protected_ancestors'):
            return publish_research(self.fixture.config.snapshot,self.destination,self.fixture.config,self.group,**kwargs)

    def test_verified_bytes_are_published_atomically_with_readonly_group_mode(self):
        raw=self.fixture.config.snapshot.read_bytes()
        result=self.publish(clock=lambda:self.fixture.fixture.now)
        self.assertEqual(self.destination.read_bytes(),raw)
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode),0o640)
        self.assertFalse(result['consumer_group_write_allowed'])
        self.assertFalse(result['execution_authorized'])

    def test_bad_signature_or_expiry_preserves_existing_receipt(self):
        self.publish(clock=lambda:self.fixture.fixture.now)
        previous=self.destination.read_bytes()
        clock=iter([self.fixture.fixture.now,self.fixture.fixture.now+86400])
        with self.assertRaises(SourceError):self.publish(clock=lambda:next(clock))
        self.assertEqual(self.destination.read_bytes(),previous)
        value=json.loads(self.fixture.config.snapshot.read_text());value['signature']='00'*64
        self.fixture.config.snapshot.write_text(json.dumps(value))
        with self.assertRaises(SourceError):self.publish()
        self.assertEqual(self.destination.read_bytes(),previous)
        self.assertEqual(list(self.folder.iterdir()),[self.destination])

    def test_group_writable_directory_and_symlink_target_fail(self):
        self.folder.chmod(0o2770)
        with self.assertRaises(PublicationError):self.publish()
        self.folder.chmod(0o2750)
        self.destination.symlink_to(self.fixture.config.snapshot)
        with self.assertRaisesRegex(PublicationError,'unsafe_existing_publication'):self.publish()

    def test_legacy_hmac_and_unprotected_ancestors_are_rejected(self):
        with self.assertRaisesRegex(PublicationError,'public_key_receipt_mode_required'):
            publish_research(self.fixture.config.snapshot,self.destination,self.fixture.fixture.config,self.group)
        # The fixture is under this user's writable workspace, not a trusted root
        # hierarchy, so actual publication without the test patch must fail.
        with self.assertRaisesRegex(PublicationError,'protected_publication_ancestors_required'):
            publish_research(self.fixture.config.snapshot,self.destination,self.fixture.config,self.group)
