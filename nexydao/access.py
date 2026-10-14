"""Operator-only kernel firewall audit. No agents, credentials or network changes."""
import json
import subprocess

PORTS = {4001, 4002, 5901, 7496, 7497}
WEB_PORTS = PORTS | {5000}


def validate_guard(document,web=False):
    """Recognize our exact drop rule; unknown shapes cannot establish protection."""
    if not isinstance(document, dict) or set(document) != {'nftables'}:
        return False
    entries = document['nftables']
    if not isinstance(entries, list) or len(entries) > 10:
        return False
    objects = []
    for entry in entries:
        if not isinstance(entry, dict) or len(entry) != 1: return False
        if 'metainfo' not in entry: objects.append(entry)
    if len(objects) != 3: return False
    table, chain, rule = objects
    if set(table) != {'table'} or set(chain) != {'chain'} or set(rule) != {'rule'}: return False
    table, chain, rule = table['table'], chain['chain'], rule['rule']
    if not all(isinstance(x, dict) for x in (table, chain, rule)): return False
    if table.get('family') != 'inet' or table.get('name') != 'nexydao_guard': return False
    if any(x.get('family') != 'inet' or x.get('table') != 'nexydao_guard' for x in (chain, rule)): return False
    if (chain.get('name') != 'input' or chain.get('type') != 'filter' or chain.get('hook') != 'input'
            or chain.get('prio') != -20 or chain.get('policy') != 'accept' or rule.get('chain') != 'input'):
        return False
    expected = [
        {'match': {'op': '!=', 'left': {'meta': {'key': 'iifname'}}, 'right': 'lo'}},
        {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                   'right': {'set': sorted(PORTS)}}},
        {'drop': None}]
    if not web and rule.get('expr')==expected:return True
    expected[1]['match']['right']['set']=sorted(WEB_PORTS)
    return rule.get('expr')==expected


def run_access_check(web=False):
    # Fixed argv; no shell, no arbitrary sudo command, no raw output in logs.
    try:
        result = subprocess.run(['/usr/bin/sudo', '-n', '/usr/sbin/nft', '-j', 'list', 'table',
                                 'inet', 'nexydao_guard'], capture_output=True, timeout=5, check=True)
        protected = len(result.stdout) <= 32768 and validate_guard(json.loads(result.stdout),web=web)
    except (OSError, subprocess.SubprocessError, ValueError):
        protected = False
    return {'status': 'host_guard_verified' if protected else 'host_guard_unverified',
            'non_loopback_tcp_ingress_denied': protected, 'protected_ports': sorted(WEB_PORTS if web else PORTS),
            'ipv4_and_ipv6': protected, 'cloud_firewall_verified': False,
            'collector_agent_os_separation_verified': False, 'execution_authorized': False}
