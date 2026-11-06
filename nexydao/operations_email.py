"""Explicit Gmail self-alerts from local health; no timer, test send or retries."""
import argparse
from contextlib import contextmanager
from decimal import Decimal
from email.message import EmailMessage
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import smtplib
import sqlite3
import ssl
import time

from . import audit_backups as backups
from .config import Config
from .market import canonical
from .operations_health import operations_health,HealthError

HOST='smtp.gmail.com'
PORT=465
WINDOW=86400
COOLDOWN=3600
MAX_DAILY=3
MAX_RECORDS=1000
CODES={'inspection_copy_cannot_resume','long_running_runs_require_review','latest_ai_run_failed',
       'latest_ai_run_order_ambiguous','aged_api_reservations_require_review','finished_runs_have_uncertain_api_costs',
       'lifetime_api_budget_exhausted','database_volume_free_space_low','verified_backup_not_supplied',
       'backup_timestamp_in_future','verified_backup_too_old','backup_verification_failed','operations_health_unavailable'}


class EmailError(ValueError):pass


def validate_profile(profile):
    if not isinstance(profile,dict) or set(profile)!={'mailbox','secret_file','source_db','api_budget_usd'}:
        raise EmailError('mail_profile_schema')
    mailbox=profile['mailbox']
    if not isinstance(mailbox,str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.]{0,62}[a-z0-9])?@gmail\.com',mailbox) or '..' in mailbox:
        raise EmailError('mail_single_gmail_mailbox_required')
    for name in ('secret_file','source_db'):
        value=profile[name]
        if (not isinstance(value,str) or not 0<len(value)<=1024 or any(ord(c)<32 for c in value)
                or not Path(value).is_absolute() or '..' in Path(value).parts):raise EmailError('mail_profile_path')
    value=profile['api_budget_usd']
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,7}(?:\.[0-9]{1,20})?',value) or not 0<Decimal(value)<=1000000:
        raise EmailError('mail_profile_budget')
    return profile


def load_profile(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise EmailError('mail_profile_duplicate')
            result[key]=value
        return result
    try:
        with backups._file(path,8192) as stream:raw=stream.read(8193)
        if len(raw)>8192:raise EmailError('mail_profile_size')
        return validate_profile(json.loads(raw,object_pairs_hook=unique))
    except Exception:raise EmailError('mail_profile_unavailable_or_invalid') from None


def read_secret(profile):
    try:
        with backups._file(Path(profile['secret_file']),128) as stream:raw=stream.read(129)
        if len(raw)>128:raise ValueError()
        secret=raw.decode('ascii').strip().replace(' ','')
        if not re.fullmatch(r'[A-Za-z0-9]{16}',secret):raise ValueError()
        return secret
    except Exception:raise EmailError('mail_private_app_password_required') from None


def critical_items(report):
    if not isinstance(report,dict):raise EmailError('mail_health_alerts_invalid')
    rows=report.get('alerts');items=[];seen=set()
    if not isinstance(rows,list) or len(rows)>32:raise EmailError('mail_health_alerts_invalid')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'code','severity','count'} or row['severity'] not in ('critical','warning'):
            raise EmailError('mail_health_alerts_invalid')
        if row['severity']=='warning':continue
        code=row['code'];count=row['count']
        if not isinstance(code,str) or code not in CODES or code in seen or type(count) is not int or not 1<=count<=100000:
            raise EmailError('mail_health_alerts_invalid')
        seen.add(code);items.append((code,count))
    if type(report.get('critical_alert_count')) is not int or report['critical_alert_count']!=len(items):
        raise EmailError('mail_health_alerts_invalid')
    return sorted(items)


def send_gmail(mailbox,secret,message):
    context=ssl.create_default_context();context.minimum_version=ssl.TLSVersion.TLSv1_2
    with smtplib.SMTP_SSL(HOST,PORT,local_hostname='nexydao.local',context=context,timeout=10) as client:
        client.login(mailbox,secret)
        if client.send_message(message,from_addr=mailbox,to_addrs=[mailbox]):raise EmailError('mail_smtp_recipient_refused')


class EmailAlerts:
    def __init__(self,path,transport=None,clock=time.time):
        self.path=Path(path).absolute();self.transport=transport or send_gmail;self.clock=clock

    @contextmanager
    def _db(self,initializing=False,*,readonly=False):
        if not initializing:
            with backups._file(self.path,1024*1024):pass
        target=self.path.as_uri()+'?mode=ro' if readonly else self.path
        db=sqlite3.connect(target,uri=readonly,timeout=2,isolation_level=None)
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            if not readonly:db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN' if readonly else 'BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:db.execute('ROLLBACK')
            raise
        finally:db.close()

    def _read(self,db,profile=None):
        schema=set(db.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger') LIMIT 4").fetchall())
        if schema!={('control','table'),('deliveries','table')} or db.execute('PRAGMA user_version').fetchone()[0]!=1:
            raise EmailError('mail_state_invalid')
        rows=db.execute('SELECT enabled,pin FROM control').fetchall()
        if len(rows)!=1 or type(rows[0][0]) is not int or rows[0][0] not in (0,1) or not isinstance(rows[0][1],str) or not re.fullmatch('[0-9a-f]{64}',rows[0][1]):
            raise EmailError('mail_state_invalid')
        enabled,pin=rows[0]
        if profile is not None and hashlib.sha256(canonical(profile)).hexdigest()!=pin:raise EmailError('mail_profile_changed')
        records=db.execute('SELECT id,fingerprint,created,status FROM deliveries ORDER BY created,id LIMIT 1001').fetchall()
        if len(records)>MAX_RECORDS or sum(row[3]=='pending' for row in records)>1:raise EmailError('mail_state_invalid')
        for identifier,fingerprint,created,status in records:
            if (not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{32}',identifier) or not isinstance(fingerprint,str)
                    or not re.fullmatch('[0-9a-f]{64}',fingerprint) or type(created) is not int or not 0<created<1e12
                    or status not in ('pending','sent','unknown')):raise EmailError('mail_state_invalid')
        return bool(enabled),records

    def _result(self,db,reason,accepted=False):
        enabled,records=self._read(db)
        return {'status':reason,'enabled':enabled,'smtp_accepted':accepted,'attempt_count':len(records),
            'lifetime_capacity_reached':len(records)>=MAX_RECORDS,
            'uncertain_attempt_count':sum(r[3]!='sent' for r in records),'recurring_automation_enabled':False,
            'execution_authorized':False}

    def initialize(self,profile):
        validate_profile(profile);backups._parent(self.path)
        descriptor=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
        with self._db(initializing=True) as db:
            db.execute('PRAGMA user_version=1')
            db.execute('CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,pin TEXT NOT NULL)')
            db.execute('CREATE TABLE deliveries (id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,created INTEGER NOT NULL,status TEXT NOT NULL)')
            db.execute('INSERT INTO control VALUES(1,0,?)',(hashlib.sha256(canonical(profile)).hexdigest(),))
        return self.status()

    def status(self):
        with self._db(readonly=True) as db:return self._result(db,'mail_status')

    def stop(self):
        with self._db() as db:
            self._read(db);db.execute('UPDATE control SET enabled=0');return self._result(db,'mail_stopped')

    def arm(self,profile):
        validate_profile(profile)
        with self._db() as db:
            _,records=self._read(db,profile)
            if any(row[3]!='sent' for row in records):raise EmailError('mail_uncertain_delivery_requires_review')
            if len(records)>=MAX_RECORDS:raise EmailError('mail_capacity_reached')
            read_secret(profile);db.execute('UPDATE control SET enabled=1');return self._result(db,'mail_armed')

    def deliver(self,profile,report):
        profile=dict(validate_profile(profile));items=critical_items(report);now=self.clock()
        if type(now) not in (int,float) or not 0<now<1e12:raise EmailError('mail_clock_invalid')
        now=int(now);fingerprint=hashlib.sha256(canonical(items)).hexdigest()
        with self._db() as db:
            enabled,records=self._read(db,profile)
            if any(row[3]!='sent' for row in records):return self._result(db,'mail_uncertain_delivery_requires_review')
            if not enabled:return self._result(db,'mail_stopped')
            if not items:return self._result(db,'mail_no_critical_alert')
            if any(row[2]>now for row in records):raise EmailError('mail_clock_regressed')
            recent=[row for row in records if now-row[2]<WINDOW]
            if any(row[1]==fingerprint for row in recent):return self._result(db,'mail_duplicate_suppressed')
            if len(records)>=MAX_RECORDS or len(recent)>=MAX_DAILY:return self._result(db,'mail_capacity_reached')
            if recent and now-recent[-1][2]<COOLDOWN:return self._result(db,'mail_cooldown')
            secret=read_secret(profile);identifier=secrets.token_hex(16)
            db.execute("INSERT INTO deliveries VALUES(?,?,?,'pending')",(identifier,fingerprint,now))
        # A crash or ambiguous SMTP result never gets an automatic second send.
        message=EmailMessage();mailbox=profile['mailbox']
        message['From']=mailbox;message['To']=mailbox;message['Subject']='NexyDAO critical operations alert'
        message['Message-ID']='<nexydao-'+identifier+'@gmail.com>'
        message.set_content('NexyDAO reported critical local health findings.\n\n'+
            ''.join(f'{code}: {count}\n' for code,count in items)+
            '\nReview the local operations-health report. No action was taken on the ledger or broker.\n')
        accepted=False
        try:self.transport(mailbox,secret,message);accepted=True
        except Exception:pass
        with self._db() as db:
            self._read(db,profile)
            updated=db.execute("UPDATE deliveries SET status=? WHERE id=? AND status='pending'",('sent' if accepted else 'unknown',identifier))
            if updated.rowcount!=1:raise EmailError('mail_claim_changed')
            if not accepted:db.execute('UPDATE control SET enabled=0')
            return self._result(db,'mail_smtp_accepted' if accepted else 'mail_delivery_outcome_unknown',accepted)


def main():
    parser=argparse.ArgumentParser(description='Explicit critical Gmail self-alerts; no recurring activation')
    parser.add_argument('action',choices=['init','arm','send','status','stop'])
    parser.add_argument('--state',required=True,type=Path);parser.add_argument('--profile',type=Path);parser.add_argument('--backup-dir',type=Path)
    args=parser.parse_args()
    try:
        config=Config.from_env();mailer=EmailAlerts(args.state)
        if args.action in ('init','arm','send'):
            if args.profile is None:raise EmailError('mail_explicit_profile_required')
            profile=load_profile(args.profile)
            if Path(profile['source_db']).absolute()!=config.db.absolute() or Decimal(profile['api_budget_usd'])!=config.budget:
                raise EmailError('mail_runtime_binding_changed')
            if args.action=='send':
                if args.backup_dir is None:raise EmailError('mail_explicit_backup_required')
                try:report=operations_health(config.db,config.budget,args.backup_dir)
                except HealthError:report={'alerts':[{'code':'operations_health_unavailable','severity':'critical','count':1}],'critical_alert_count':1}
                result=mailer.deliver(profile,report)
            else:
                if args.backup_dir is not None:raise EmailError('mail_backup_argument_not_applicable')
                result=getattr(mailer,{'init':'initialize','arm':'arm'}[args.action])(profile)
        else:
            if args.profile is not None or args.backup_dir is not None:raise EmailError('mail_arguments_not_applicable')
            result=getattr(mailer,args.action)()
        print(json.dumps(result,indent=2))
        if result['uncertain_attempt_count'] or result['status']=='mail_capacity_reached':parser.exit(1)
    except Exception as exc:
        code=str(exc) if isinstance(exc,EmailError) else 'mail_unavailable'
        parser.exit(1,'NexyDAO mail stopped safely ('+code+').\n')


if __name__=='__main__':main()
