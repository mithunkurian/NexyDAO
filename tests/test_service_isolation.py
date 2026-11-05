import copy
import os
import unittest
from unittest.mock import patch

from nexydao.cli import main
from nexydao.service_isolation import CODE,hardened_service,last_start_succeeded,parse_environment,run_service_isolation_check


def properties(role='consumer'):
    user='nexydao-controller' if role=='consumer' else 'nexydao-collector'
    return {'User':user,'Group':user,'WorkingDirectory':str(CODE),'ProtectSystem':'strict','ProtectHome':'yes',
            'NoNewPrivileges':'yes','PrivateTmp':'yes','PrivateDevices':'yes','CapabilityBoundingSet':'',
            'DropInPaths':'','LoadState':'loaded','SupplementaryGroups':'nexydao-evidence' if role=='consumer' else '',
            'RestrictAddressFamilies':'AF_UNIX' if role=='consumer' else 'AF_UNIX AF_INET AF_INET6',
            'Result':'success','ExecMainStatus':'0','ExecMainStartTimestampMonotonic':'10',
            'ExecMainExitTimestampMonotonic':'20','RemainAfterExit':'yes','ActiveState':'active','SubState':'exited'}


class ServiceIsolationTests(unittest.TestCase):
    def test_effective_profiles_require_role_identity_and_hardening(self):
        self.assertTrue(hardened_service(properties(),'consumer'))
        self.assertTrue(hardened_service(properties('collector'),'collector'))
        self.assertFalse(hardened_service(properties(),'other'))
        self.assertFalse(hardened_service(properties('collector'),'consumer'))

    def test_wrong_user_network_capabilities_overrides_or_filesystem_fail(self):
        for field,value in (('User','root'),('Group','sudo'),('ProtectSystem','no'),('ProtectHome','no'),
                            ('NoNewPrivileges','no'),('PrivateTmp','no'),('CapabilityBoundingSet','cap_dac_override'),
                            ('DropInPaths','override.conf'),('SupplementaryGroups','sudo nexydao-evidence'),
                            ('RestrictAddressFamilies','AF_UNIX AF_INET'),('LoadState','not-found'),('RemainAfterExit','no')):
            changed=properties();changed[field]=value
            with self.subTest(field=field):self.assertFalse(hardened_service(changed,'consumer'))

    def test_never_started_or_failed_process_cannot_count_as_acceptance(self):
        self.assertTrue(last_start_succeeded(properties()))
        for field,value in (('ExecMainStartTimestampMonotonic','0'),('ExecMainExitTimestampMonotonic','1'),
                            ('ExecMainStatus','1'),('Result','exit-code'),('ExecMainStartTimestampMonotonic','invalid'),
                            ('ActiveState','inactive'),('SubState','running')):
            changed=properties();changed[field]=value
            with self.subTest(field=field):self.assertFalse(last_start_succeeded(changed))
        self.assertFalse(last_start_succeeded({}))

    def test_environment_is_data_and_duplicate_or_malformed_lines_fail(self):
        self.assertEqual(parse_environment(b'NEXYDAO_TEST="a b"\n'),{'NEXYDAO_TEST':'a b'})
        self.assertEqual(parse_environment(b'NEXYDAO_TEST="$(no-command)"\n')['NEXYDAO_TEST'],'$(no-command)')
        for value in (b'NEXYDAO_X=a\nNEXYDAO_X=b',b'OPENAI_API_KEY=private',b'NEXYDAO_X=a b',b'NEXYDAO_X="bad',b'x'*16385):
            with self.subTest(value=value[:20]),self.assertRaises(ValueError):parse_environment(value)

    def test_unprivileged_audit_fails_without_running_systemctl(self):
        with patch('nexydao.service_isolation.os.geteuid',return_value=1234,create=True), \
                patch('nexydao.service_isolation.subprocess.run') as runner:
            result=run_service_isolation_check()
        self.assertFalse(result['sec_role_boundary_verified'])
        self.assertFalse(result['execution_authorized'])
        runner.assert_not_called()

    def test_cli_failure_does_not_open_db_or_provider(self):
        with patch('sys.argv',['nexydao','service-isolation-check']),patch.dict(os.environ,{},clear=True), \
                patch('nexydao.service_isolation.run_service_isolation_check',return_value={'sec_role_boundary_verified':False}), \
                patch('nexydao.cli.Store') as store,patch('nexydao.cli.OpenAIProvider') as provider,patch('sys.stdout'):
            with self.assertRaises(SystemExit) as stopped:main()
        self.assertEqual(stopped.exception.code,1)
        store.assert_not_called();provider.assert_not_called()
