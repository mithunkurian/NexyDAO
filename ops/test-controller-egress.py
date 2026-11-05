"""Root-only acceptance fixture. Run ONLY inside `unshare --net --fork`.

Uses the installer's rule body with a fixture UID, not a host account. Never
installs users/services or edits host firewall tables. No external connection.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    if os.geteuid() != 0 or os.stat('/proc/self/ns/net').st_ino == os.stat('/proc/1/ns/net').st_ino:
        raise RuntimeError('Root in a separate network namespace required')
    subprocess.run(['/usr/sbin/ip', 'link', 'set', 'lo', 'up'], check=True, capture_output=True)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from nexydao.controller_access import PORTS, TABLE, validate_controller_guard
    uid = 65534
    source = (root/'ops/nexydao-controller-firewall.sh').read_text()
    rules = source.split('<<NFT\n', 1)[1].split('\nNFT', 1)[0].replace('$controller_uid', str(uid))
    if '$' in rules:
        raise RuntimeError('Unexpected rule substitution')
    for arguments in (['--check', '--file', '-'], ['--file', '-']):
        subprocess.run(['/usr/sbin/nft', *arguments], input=rules.encode(), check=True, capture_output=True)
    result = subprocess.run(['/usr/sbin/nft', '-j', '-n', 'list', 'table', 'inet', TABLE],
                            check=True, capture_output=True)
    assert validate_controller_guard(json.loads(result.stdout), uid)

    def drop_identity():
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)

    probe = '''import json,os,socket,sys
assert os.geteuid()==65534
sock=socket.socket(int(sys.argv[1]),socket.SOCK_STREAM)
sock.settimeout(0.3)
try: code=sock.connect_ex((sys.argv[2],int(sys.argv[3])))
except OSError: code=1
finally: sock.close()
print(json.dumps({'uid':os.geteuid(),'connected':code==0}))
sys.exit(0 if code==0 else 1)
'''
    blocked = 0
    for family, address in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
        for port in (*sorted(PORTS), 18080):
            with socket.socket(family, socket.SOCK_STREAM) as listener:
                if family == socket.AF_INET6:
                    listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener.bind((address, port))
                listener.listen(4)
                listener.settimeout(2)
                attempt = subprocess.run([sys.executable, '-c', probe, str(int(family)), address, str(port)],
                                         preexec_fn=drop_identity, cwd='/tmp', env={'PATH': '/usr/bin:/bin'},
                                         capture_output=True, timeout=5)
                observation = json.loads(attempt.stdout)
                assert observation['uid'] == uid
                if port in PORTS:
                    assert attempt.returncode == 1 and not observation['connected'], 'Fixture UID reached a protected port'
                    blocked += 1
                    with socket.socket(family, socket.SOCK_STREAM) as operator:
                        operator.settimeout(2)
                        operator.connect((address, port))
                        connected, _ = listener.accept()
                        connected.close()
                else:
                    assert attempt.returncode == 0 and observation['connected'], 'Unprotected control port failed'
                    connected, _ = listener.accept()
                    connected.close()
    print(json.dumps({'isolated_network_namespace': True, 'protected_uid_probes_denied': blocked,
                      'ipv4_ipv6_control_ports_passed': True, 'operator_uid_preserved': True,
                      'host_users_services_or_rules_changed': False, 'execution_authorized': False}))


if __name__ == '__main__':
    main()
