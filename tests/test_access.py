import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from nexydao.access import PORTS, WEB_PORTS, run_access_check, validate_guard


def guard():
    return {'nftables': [
        {'metainfo': {'json_schema_version': 1}},
        {'table': {'family': 'inet', 'name': 'nexydao_guard', 'handle': 1}},
        {'chain': {'family': 'inet', 'table': 'nexydao_guard', 'name': 'input', 'handle': 1,
                   'type': 'filter', 'hook': 'input', 'prio': -20, 'policy': 'accept'}},
        {'rule': {'family': 'inet', 'table': 'nexydao_guard', 'chain': 'input', 'handle': 2,
                  'expr': [
                      {'match': {'op': '!=', 'left': {'meta': {'key': 'iifname'}}, 'right': 'lo'}},
                      {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                                 'right': {'set': sorted(PORTS)}}}, {'drop': None}]}}]}


class AccessTests(unittest.TestCase):
    def test_web_gateway_requires_additional_port_guard(self):
        self.assertFalse(validate_guard(guard(),web=True))
        document=guard()
        document['nftables'][3]['rule']['expr'][1]['match']['right']['set']=sorted(WEB_PORTS)
        self.assertTrue(validate_guard(document,web=True))
        self.assertTrue(validate_guard(document))

    def test_exact_ipv4_ipv6_guard(self):
        self.assertTrue(validate_guard(guard()))

    def test_wrong_scope_or_verdict_fails(self):
        for change in ('family', 'hook', 'priority', 'loopback', 'ports', 'accept', 'extra_rule'):
            document = copy.deepcopy(guard())
            table, chain, rule = document['nftables'][1:]
            if change == 'family': table['table']['family'] = 'ip'
            elif change == 'hook': chain['chain']['hook'] = 'output'
            elif change == 'priority': chain['chain']['prio'] = 100
            elif change == 'loopback': rule['rule']['expr'][0]['match']['op'] = '=='
            elif change == 'ports': rule['rule']['expr'][1]['match']['right']['set'].remove(4002)
            elif change == 'accept': rule['rule']['expr'][-1] = {'accept': None}
            else: document['nftables'].insert(3, copy.deepcopy(rule))
            with self.subTest(change=change): self.assertFalse(validate_guard(document))

    def test_errors_fail_closed_without_raw_output(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('nft', 5),
                      subprocess.CalledProcessError(1, 'nft', stderr=b'private')):
            with patch('nexydao.access.subprocess.run', side_effect=error):
                result = run_access_check()
                self.assertFalse(result['non_loopback_tcp_ingress_denied'])
                self.assertFalse(result['execution_authorized'])
                self.assertNotIn('private', json.dumps(result))

    def test_fixed_readonly_process(self):
        with patch('nexydao.access.subprocess.run', return_value=subprocess.CompletedProcess('nft', 0,
                                                                                          json.dumps(guard()).encode())) as run:
            result = run_access_check()
            self.assertTrue(result['non_loopback_tcp_ingress_denied'])
            self.assertFalse(result['cloud_firewall_verified'])
            self.assertFalse(result['collector_agent_os_separation_verified'])
            self.assertEqual(run.call_args.args[0], ['/usr/bin/sudo', '-n', '/usr/sbin/nft', '-j',
                                                     'list', 'table', 'inet', 'nexydao_guard'])
