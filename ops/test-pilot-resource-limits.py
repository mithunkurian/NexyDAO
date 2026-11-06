"""Exercise the bounded maintenance pipeline in a disposable systemd service."""

import json
from pathlib import Path
import tempfile
import time

from nexydao.maintenance_jobs import MaintenanceJobs
from nexydao.store import Store


def main():
    group = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::/')
    limits = Path('/sys/fs/cgroup') / group
    quota, period = (limits / 'cpu.max').read_text().split()
    if (quota != period or (limits / 'memory.max').read_text().strip() != '268435456'
            or (limits / 'pids.max').read_text().strip() != '16'):
        raise SystemExit('Expected one CPU, 256 MiB memory, and 16 tasks')

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / 'source.sqlite3'
        store = Store(source)
        try:
            run = store.start()
            for index in range(65):
                store.event(run, 'fixture', {'index': index, 'text': 'x' * (985 * 1024)})
            store.finish(run, 'completed', {})
        finally:
            store.close()
        source.chmod(0o600)
        archives = root / 'archives'
        archives.mkdir(mode=0o700)
        plan = {'source_db': str(source), 'backup_root': str(archives),
                'api_budget_usd': '0.10', 'interval_seconds': 3600,
                'max_attempts': 1, 'max_backup_bytes': 268435456}
        jobs = MaintenanceJobs(root / 'jobs.sqlite3')
        jobs.initialize(plan)
        jobs.arm(plan)

        started = time.monotonic()
        result = jobs.tick(plan)
        elapsed = time.monotonic() - started
        print(json.dumps({'passed': result['maintenance_passed'],
                          'critical_alerts': result['critical_alert_count'],
                          'backup_bytes': result['retained_or_reserved_backup_bytes'],
                          'seconds': round(elapsed, 2)}))
        if not result['maintenance_passed']:
            raise SystemExit('Maintenance fixture failed')


if __name__ == '__main__':
    main()
