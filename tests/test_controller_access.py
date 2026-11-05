import copy
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from nexydao.cli import main
from nexydao.controller_access import PORTS, TABLE, run_controller_access_check, validate_controller_guard


def guard(uid=1234):
    return {'nftables': [
        {'metainfo': {'json_schema_version': 1}},
        {'table': {'family': 'inet', 'name': TABLE}},
        {'chain': {'family': 'inet', 'table': TABLE, 'name': 'output', 'type': 'filter',
                   'hook': 'output', 'prio': -20, 'policy': 'accept'}},
        {'rule': {'family': 'inet', 'table': TABLE, 'chain': 'output', 'expr': [
            {'match': {'op': '==', 'left': {'meta': {'key': 'skuid'}}, 'right': uid}},
            {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                       'right': {'set': sorted(PORTS)}}}, {'drop': None}]}}]}


class ControllerAccessTests(unittest.TestCase):
    def test_exact_rule_covers_dedicated_uid_ipv4_ipv6_and_loopback(self):
        self.assertTrue(validate_controller_guard(guard(), 1234))
        for uid in (None, 0, -1, True, '1234', 4294967295):
            with self.subTest(uid=uid):
                self.assertFalse(validate_controller_guard(guard(), uid))
        self.assertFalse(validate_controller_guard(guard(999), 1234))

    def test_wrong_direction_identity_protocol_scope_or_verdict_fails(self):
        for mutation in ('table', 'family', 'hook', 'priority', 'chain', 'uid_operator',
                         'gid', 'udp', 'ports', 'interface', 'accept', 'extra_rule'):
            document = copy.deepcopy(guard())
            table = document['nftables'][1]['table']
            chain = document['nftables'][2]['chain']
            rule = document['nftables'][3]['rule']
            if mutation == 'table': table['name'] = 'other'
            elif mutation == 'family': table['family'] = 'ip'
            elif mutation == 'hook': chain['hook'] = 'input'
            elif mutation == 'priority': chain['prio'] = 100
            elif mutation == 'chain': rule['chain'] = 'other'
            elif mutation == 'uid_operator': rule['expr'][0]['match']['op'] = '!='
            elif mutation == 'gid': rule['expr'][0]['match']['left']['meta']['key'] = 'skgid'
            elif mutation == 'udp': rule['expr'][1]['match']['left']['payload']['protocol'] = 'udp'
            elif mutation == 'ports': rule['expr'][1]['match']['right']['set'].remove(4002)
            elif mutation == 'interface': rule['expr'].insert(0, {'match': {'op': '!=', 'left': {'meta': {'key': 'oifname'}}, 'right': 'lo'}})
            elif mutation == 'accept': rule['expr'][-1] = {'accept': None}
            else: document['nftables'].insert(3, copy.deepcopy(document['nftables'][3]))
            with self.subTest(mutation=mutation):
                self.assertFalse(validate_controller_guard(document, 1234))

    def test_malformed_documents_fail_without_exceptions(self):
        for document in (None, [], {}, {'nftables': None}, {'nftables': [None]},
                         {'nftables': [{}]*11}, {'nftables': [{'table': []}, {'chain': {}}, {'rule': {}}]}):
            with self.subTest(document=document):
                self.assertFalse(validate_controller_guard(document, 1234))

    def test_missing_account_does_not_run_privileged_command(self):
        with patch('nexydao.controller_access.controller_uid', return_value=None), \
                patch('nexydao.controller_access.subprocess.run') as run:
            result = run_controller_access_check()
        self.assertFalse(result['controller_account_found'])
        self.assertFalse(result['controller_broker_port_egress_denied'])
        run.assert_not_called()

    def test_dormant_table_cannot_be_reported_as_protection(self):
        document = guard()
        document['nftables'][1]['table']['flags'] = ['dormant']
        self.assertFalse(validate_controller_guard(document, 1234))

    def test_fixed_readonly_audit_distinguishes_guard_from_process_identity(self):
        response = subprocess.CompletedProcess('nft', 0, json.dumps(guard()).encode())
        with patch('nexydao.controller_access.controller_uid', return_value=1234), \
                patch('nexydao.controller_access.os.geteuid', return_value=999, create=True), \
                patch('nexydao.controller_access.subprocess.run', return_value=response) as run:
            result = run_controller_access_check()
        self.assertTrue(result['controller_broker_port_egress_denied'])
        self.assertFalse(result['current_process_is_controller'])
        self.assertFalse(result['controller_service_isolation_verified'])
        self.assertFalse(result['signing_key_separation_verified'])
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(run.call_args.args[0], ['/usr/bin/sudo', '-n', '/usr/sbin/nft', '-j', '-n',
                                               'list', 'table', 'inet', TABLE])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)

    def test_audit_errors_and_oversized_output_fail_without_private_details(self):
        responses = [FileNotFoundError('private'), subprocess.TimeoutExpired('private', 5),
                     subprocess.CalledProcessError(1, 'private'),
                     subprocess.CompletedProcess('nft', 0, b'private'),
                     subprocess.CompletedProcess('nft', 0, b'x'*32769)]
        for response in responses:
            kwargs = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
            with self.subTest(response=type(response).__name__), \
                    patch('nexydao.controller_access.controller_uid', return_value=1234), \
                    patch('nexydao.controller_access.subprocess.run', **kwargs):
                result = run_controller_access_check()
                self.assertFalse(result['controller_broker_port_egress_denied'])
                self.assertNotIn('private', json.dumps(result))

    def test_cli_failure_does_not_open_the_application_database(self):
        with patch('sys.argv', ['nexydao', 'controller-access-check']), patch.dict(os.environ, {}, clear=True), \
                patch('nexydao.controller_access.run_controller_access_check',
                      return_value={'controller_broker_port_egress_denied': False}), \
                patch('nexydao.cli.Store') as store, patch('sys.stdout'):
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(stopped.exception.code, 1)
        store.assert_not_called()
