"""Read effective systemd user-unit settings for pilot commissioning."""

import argparse
import json
import os
import re
import subprocess


SERVICE = 'nexydao-alert-pilot.service'
TIMER = 'nexydao-alert-pilot.timer'
SERVICE_SETTINGS = {
    'LoadState': 'loaded', 'NeedDaemonReload': 'no', 'Type': 'oneshot',
    'TimeoutStartUSec': '2min', 'Restart': 'no', 'UMask': '0077',
    'NoNewPrivileges': 'yes', 'CPUAccounting': 'yes', 'CPUQuotaPerSecUSec': '1s',
    'MemoryAccounting': 'yes', 'MemoryMax': '268435456',
    'TasksAccounting': 'yes', 'TasksMax': '16',
}
TIMER_CADENCE = 'OnActiveUSec=1h, OnUnitInactiveUSec=1h'


def read_settings(command, properties):
    args = [*command, *(f'--property={name}' for name in properties)]
    result = subprocess.run(args, capture_output=True, text=True, check=True,
                            timeout=5, env={**os.environ, 'LC_ALL': 'C'})
    settings = {}
    monotonic = []
    for line in result.stdout.splitlines():
        name, separator, value = line.partition('=')
        if not separator:
            continue
        if name == 'TimersMonotonic':
            match = re.fullmatch(r'\{ (\w+=\S+) ; next_elapse=.* \}', value)
            monotonic.append(match[1] if match else 'unrecognized timer')
        else:
            settings[name] = value
    settings['TimersMonotonic'] = ', '.join(sorted(monotonic))
    settings.setdefault('TimersCalendar', '')
    return {name: settings.get(name) for name in properties}


def audit(timer_state):
    timer_settings = {'LoadState': 'loaded', 'NeedDaemonReload': 'no',
                      'ActiveState': 'active' if timer_state == 'active' else 'inactive',
                      'UnitFileState': 'enabled' if timer_state == 'active' else 'disabled',
                      'Unit': SERVICE, 'TimersMonotonic': TIMER_CADENCE, 'TimersCalendar': '',
                      'Persistent': 'no', 'RandomizedDelayUSec': '0'}
    checks = [
        (SERVICE, ['systemctl', '--user', 'show', SERVICE], SERVICE_SETTINGS),
        (TIMER, ['systemctl', '--user', 'show', TIMER], timer_settings),
        ('user', ['loginctl', 'show-user', str(os.getuid())], {'Linger': 'yes'}),
    ]
    mismatches = []
    for scope, command, expected in checks:
        actual = read_settings(command, expected)
        mismatches.extend({'scope': scope, 'property': name, 'expected': value,
                           'actual': actual[name]} for name, value in expected.items() if actual[name] != value)
    return {'passed': not mismatches, 'expected_timer_state': timer_state, 'mismatches': mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timer-state', choices=('active', 'inactive'), required=True)
    args = parser.parse_args()
    try:
        report = audit(args.timer_state)
    except (OSError, subprocess.SubprocessError):
        parser.exit(1, 'Pilot service settings unavailable.\n')
    print(json.dumps(report, indent=2))
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
