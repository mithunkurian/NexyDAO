import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from nexydao.service_isolation import parse_environment

SPEC=importlib.util.spec_from_file_location('research_installer',Path(__file__).resolve().parents[1]/'ops/install-research-services.py')
INSTALLER=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class ServiceInstallationTests(unittest.TestCase):
    def test_operator_scope_is_bounded_and_never_accepts_credentials_or_header_injection(self):
        settings={'issuers':[{'symbol':'TEST','cik':'0000000123'}],'user_agent':'NexyDAO/test operator@example.test'}
        self.assertEqual(INSTALLER.operator_config(json.dumps(settings).encode()),settings)
        for change in ({'OPENAI_API_KEY':'private'},{'user_agent':'Bot\nINJECT=value operator@example.test'},
                       {'issuers':[]},{'issuers':[{'symbol':'TEST','cik':'../secret'}]}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):
                INSTALLER.operator_config(json.dumps({**settings,**change}).encode())

    def test_environment_encoding_roundtrips_literal_json_and_quotes(self):
        values={'NEXYDAO_RESEARCH_UNIVERSE':'[{"symbol":"TEST","cik":"0000000123"}]',
                'NEXYDAO_SEC_USER_AGENT':'NexyDAO/test "operator" operator@example.test'}
        self.assertEqual(parse_environment(INSTALLER.environment_bytes(values)),values)

    def test_archive_digest_and_dangerous_members_are_rejected(self):
        root=Path(__file__).resolve().parents[1]/'data';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path=Path(folder)/'source.tar'
            for name,kind in (('nexydao/cli.py',tarfile.REGTYPE),('../escape',tarfile.REGTYPE),
                              ('key.pem',tarfile.REGTYPE),('source-link',tarfile.SYMTYPE)):
                output=io.BytesIO()
                with tarfile.open(fileobj=output,mode='w') as archive:
                    member=tarfile.TarInfo(name);member.type=kind
                    if kind==tarfile.REGTYPE:
                        member.size=2;archive.addfile(member,io.BytesIO(b'ok'))
                    else:
                        member.linkname='/etc/passwd';archive.addfile(member)
                raw=output.getvalue();path.write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
                if name=='nexydao/cli.py':
                    self.assertEqual(INSTALLER.checked_archive(path,digest),raw)
                    with self.assertRaises(ValueError):INSTALLER.checked_archive(path,'0'*64)
                else:
                    with self.assertRaises(ValueError):INSTALLER.checked_archive(path,digest)
