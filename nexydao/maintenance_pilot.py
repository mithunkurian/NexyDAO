"""One bounded maintenance tick with optional critical Gmail delivery."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from .audit_backups import _file
from .config import Config
from .maintenance_jobs import MaintenanceJobs, decode_plan, maintenance_failed
from .operations_email import EmailAlerts, load_profile


def run_tick(config, jobs, plan, mailer, profile):
    for settings in (plan, profile):
        if (Path(settings['source_db']).absolute() != config.db.absolute()
                or Decimal(settings['api_budget_usd']) != config.budget):
            raise ValueError('Pilot runtime binding changed')

    result = jobs.tick(plan)
    failed = maintenance_failed(result)
    if not result['work_started']:
        reason = 'incomplete_attempt' if result['incomplete_attempt_count'] else result['reason']
        return {'maintenance': reason, 'work_started': False}, failed

    mail = mailer.deliver(profile, result)
    report = {'work_started': True, 'maintenance_passed': result['maintenance_passed'],
              'mail': mail['status']}
    return report, failed or bool(mail['uncertain_attempt_count']) or mail['status'] == 'mail_capacity_reached'


def main():
    parser = argparse.ArgumentParser(description='Run one explicit maintenance and critical-alert tick')
    for argument in ('--state', '--plan', '--mail-state', '--profile'):
        parser.add_argument(argument, required=True, type=Path)
    args = parser.parse_args()
    try:
        config = Config.from_env()
        with _file(args.plan, 16384) as stream:
            plan = decode_plan(stream.read(16385))
        profile = load_profile(args.profile)
        report, failed = run_tick(config, MaintenanceJobs(args.state), plan, EmailAlerts(args.mail_state), profile)
    except Exception:
        parser.exit(1, 'NexyDAO pilot tick stopped safely.\n')
    print(json.dumps(report))
    if failed:
        parser.exit(1)


if __name__ == '__main__':
    main()
