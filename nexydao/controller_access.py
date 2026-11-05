"""Operator-only audit of the dedicated controller UID's outbound port guard."""
import json
import os
import subprocess

ACCOUNT = 'nexydao-controller'
PORTS = {22, 4001, 4002, 5000, 5901, 7496, 7497}
TABLE = 'nexydao_controller_guard'


def controller_uid():
    try:
        import pwd
        uid = pwd.getpwnam(ACCOUNT).pw_uid
        return uid if type(uid) is int and 0 < uid < 4294967295 else None
    except (ImportError, KeyError, OSError):
        return None


def validate_controller_guard(document, uid):
    if type(uid) is not int or not 0 < uid < 4294967295:
        return False
    if not isinstance(document, dict) or set(document) != {'nftables'}:
        return False
    entries = document['nftables']
    if not isinstance(entries, list) or len(entries) > 10:
        return False
    objects = []
    for entry in entries:
        if not isinstance(entry, dict) or len(entry) != 1:
            return False
        if 'metainfo' not in entry:
            objects.append(entry)
    if len(objects) != 3 or [set(item) for item in objects] != [{'table'}, {'chain'}, {'rule'}]:
        return False
    table, chain, rule = (objects[0]['table'], objects[1]['chain'], objects[2]['rule'])
    if not all(isinstance(item, dict) for item in (table, chain, rule)):
        return False
    if table.get('family') != 'inet' or table.get('name') != TABLE or table.get('flags'):
        return False
    if any(item.get('family') != 'inet' or item.get('table') != TABLE for item in (chain, rule)):
        return False
    if (chain.get('name') != 'output' or chain.get('type') != 'filter'
            or chain.get('hook') != 'output' or chain.get('prio') != -20
            or chain.get('policy') != 'accept' or rule.get('chain') != 'output'):
        return False
    expected = [
        {'match': {'op': '==', 'left': {'meta': {'key': 'skuid'}}, 'right': uid}},
        {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                   'right': {'set': sorted(PORTS)}}},
        {'drop': None},
    ]
    return rule.get('expr') == expected


def run_controller_access_check():
    uid = controller_uid()
    protected = False
    if uid is not None:
        try:
            result = subprocess.run(
                ['/usr/bin/sudo', '-n', '/usr/sbin/nft', '-j', '-n', 'list', 'table', 'inet', TABLE],
                capture_output=True, timeout=5, check=True)
            protected = len(result.stdout) <= 32768 and validate_controller_guard(json.loads(result.stdout), uid)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return {'status': 'controller_guard_verified' if protected else 'controller_guard_unverified',
            'controller_account_found': uid is not None,
            'current_process_is_controller': uid is not None and getattr(os, 'geteuid', lambda: -1)() == uid,
            'controller_broker_port_egress_denied': protected,
            'protected_tcp_ports': sorted(PORTS), 'includes_loopback_ipv4_ipv6': protected,
            'controller_service_isolation_verified': False, 'signing_key_separation_verified': False,
            'execution_authorized': False}
