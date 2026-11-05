from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from nexydao.operations_email import EmailAlerts,EmailError,load_profile,send_gmail,validate_profile


def alert(code='latest_ai_run_failed',count=1):
    return {'alerts':[{'code':code,'severity':'critical','count':count}],'critical_alert_count':1,
            'private_context':'never send this narrative or credential'}


class OperationsEmailTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.secret=self.root/'password';self.state=self.root/'mail.sqlite3'
        self.profile={'mailbox':'fixture.owner@gmail.com','secret_file':str(self.secret),
                      'source_db':str(self.root/'fixture.sqlite3'),'api_budget_usd':'0.10'}
        self.transport=Mock();self.clock=[1000000];self.mail=EmailAlerts(self.state,self.transport,lambda:self.clock[0]);self.mail.initialize(self.profile)

    def arm(self):
        self.secret.write_text('abcd efgh ijkl mnop\n');self.secret.chmod(0o600)
        return self.mail.arm(self.profile)

    def test_stopped_init_never_reads_password_or_sends_and_cannot_overwrite_state(self):
        self.assertFalse(self.mail.status()['enabled']);self.assertEqual(self.mail.deliver(self.profile,alert())['status'],'mail_stopped')
        self.transport.assert_not_called();self.assertFalse(self.secret.exists())
        with self.assertRaises(FileExistsError):self.mail.initialize(self.profile)
        with self.assertRaisesRegex(EmailError,'password_required'):self.mail.arm(self.profile)

    def test_one_critical_self_alert_contains_only_whitelisted_operational_data(self):
        self.arm();result=self.mail.deliver(self.profile,alert())
        self.assertTrue(result['smtp_accepted']);self.assertFalse(result['recurring_automation_enabled'])
        mailbox,secret,message=self.transport.call_args.args
        self.assertEqual(mailbox,self.profile['mailbox']);self.assertEqual(secret,'abcdefghijklmnop')
        self.assertEqual(message['From'],message['To']);self.assertEqual(message['To'],mailbox)
        self.assertIn('latest_ai_run_failed: 1',message.get_content())
        for private in ('credential','narrative','abcdefghijklmnop',str(self.root)):
            self.assertNotIn(private,message.get_content())
        self.assertNotIn(mailbox,json.dumps(result));self.assertNotIn(b'abcdefghijklmnop',self.state.read_bytes())

    def test_warnings_and_healthy_reports_do_not_read_missing_credentials_or_send(self):
        self.arm();self.secret.unlink()
        for rows in ([],[{'code':'active_runs_observed','severity':'warning','count':1}]):
            result=self.mail.deliver(self.profile,{'alerts':rows,'critical_alert_count':0})
            self.assertEqual(result['status'],'mail_no_critical_alert')
        self.transport.assert_not_called()

    def test_profile_binding_rejects_recipient_changes_and_header_injection(self):
        self.arm();changed={**self.profile,'mailbox':'different@gmail.com'}
        with self.assertRaisesRegex(EmailError,'profile_changed'):self.mail.deliver(changed,alert())
        for bad in ('a@gmail.com\r\nCc: target@example.org','a@gmail.com,b@gmail.com','owner@example.org'):
            with self.assertRaises(EmailError):validate_profile({**self.profile,'mailbox':bad})
        self.transport.assert_not_called()

    def test_invalid_critical_reports_cannot_send_arbitrary_text_or_counts(self):
        self.arm()
        for report in (alert('unknown\nprivate'),alert(count=True),alert(count=0),{**alert(),'critical_alert_count':False}):
            with self.assertRaises(EmailError):self.mail.deliver(self.profile,report)
        self.transport.assert_not_called();self.assertEqual(self.mail.status()['attempt_count'],0)

    def test_duplicate_window_and_cooldown_persist_across_reopen(self):
        self.arm();self.mail.deliver(self.profile,alert());self.clock[0]+=100
        other=EmailAlerts(self.state,self.transport,lambda:self.clock[0])
        self.assertEqual(other.deliver(self.profile,alert())['status'],'mail_duplicate_suppressed')
        self.assertEqual(other.deliver(self.profile,alert('backup_verification_failed'))['status'],'mail_cooldown')
        self.clock[0]+=86300;self.assertTrue(other.deliver(self.profile,alert())['smtp_accepted'])
        self.assertEqual(self.transport.call_count,2)

    def test_rolling_daily_cap_is_not_reset_by_stop_and_rearm(self):
        self.arm()
        for count in (1,2,3):
            self.assertTrue(self.mail.deliver(self.profile,alert(count=count))['smtp_accepted']);self.clock[0]+=3600
        self.mail.stop();self.arm()
        self.assertEqual(self.mail.deliver(self.profile,alert(count=4))['status'],'mail_capacity_reached')
        self.assertEqual(self.transport.call_count,3)

    def test_backward_clock_cannot_bypass_delivery_limits(self):
        self.arm();self.mail.deliver(self.profile,alert());self.clock[0]-=1
        with self.assertRaisesRegex(EmailError,'clock_regressed'):self.mail.deliver(self.profile,alert(count=2))
        self.assertEqual(self.transport.call_count,1)

    def test_transport_failure_is_uncertain_and_never_retried_or_echoed(self):
        self.arm();self.transport.side_effect=TimeoutError('private password and SMTP text')
        result=self.mail.deliver(self.profile,alert());self.assertFalse(result['smtp_accepted']);self.assertFalse(result['enabled'])
        self.assertEqual(result['uncertain_attempt_count'],1);self.assertNotIn('password',json.dumps(result))
        other=EmailAlerts(self.state,self.transport,lambda:self.clock[0]);self.clock[0]+=86400
        self.assertEqual(other.deliver(self.profile,alert())['status'],'mail_uncertain_delivery_requires_review')
        with self.assertRaises(EmailError):other.arm(self.profile)
        self.transport.assert_called_once()

    def test_interruption_leaves_a_durable_pending_claim_that_blocks_another_send(self):
        self.arm();self.transport.side_effect=KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):self.mail.deliver(self.profile,alert())
        other=EmailAlerts(self.state,self.transport,lambda:self.clock[0]);self.assertEqual(other.status()['uncertain_attempt_count'],1)
        self.assertFalse(other.deliver(self.profile,alert(count=2))['smtp_accepted']);self.transport.assert_called_once()

    def test_concurrent_delivery_cannot_create_a_second_smtp_transaction(self):
        self.arm();entered=threading.Event();release=threading.Event()
        def blocking(*args):entered.set();self.assertTrue(release.wait(5))
        self.transport.side_effect=blocking
        with ThreadPoolExecutor(1) as pool:
            first=pool.submit(self.mail.deliver,self.profile,alert())
            try:
                self.assertTrue(entered.wait(5));self.assertFalse(self.mail.deliver(self.profile,alert(count=2))['smtp_accepted'])
                self.mail.stop()
            finally:release.set()
            self.assertTrue(first.result(timeout=10)['smtp_accepted'])
        self.transport.assert_called_once();self.assertFalse(self.mail.status()['enabled'])

    def test_smtp_adapter_requires_verified_implicit_tls_and_one_envelope_recipient(self):
        from email.message import EmailMessage
        message=EmailMessage();mailbox=self.profile['mailbox']
        with patch('nexydao.operations_email.smtplib.SMTP_SSL') as smtp:
            client=smtp.return_value.__enter__.return_value;client.send_message.return_value={}
            send_gmail(mailbox,'synthetic-secret',message)
            self.assertEqual(smtp.call_args.args,('smtp.gmail.com',465));context=smtp.call_args.kwargs['context']
            self.assertTrue(context.check_hostname);self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
            self.assertEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
            client.login.assert_called_once_with(mailbox,'synthetic-secret')
            client.send_message.assert_called_once_with(message,from_addr=mailbox,to_addrs=[mailbox])
            client.send_message.return_value={mailbox:(550,b'private vendor response')}
            with self.assertRaisesRegex(EmailError,'recipient_refused'):send_gmail(mailbox,'synthetic-secret',message)

    def test_missing_bad_and_duplicate_profile_inputs_fail_before_dispatch(self):
        path=self.root/'profile.json'
        with self.assertRaises(EmailError):load_profile(path)
        path.write_text('{"mailbox":"one@gmail.com","mailbox":"two@gmail.com"}');path.chmod(0o600)
        with self.assertRaises(EmailError):load_profile(path)
        self.secret.write_text('not-a-valid-app-password');self.secret.chmod(0o600)
        with self.assertRaises(EmailError):self.mail.arm(self.profile)
        self.transport.assert_not_called()

    @unittest.skipUnless(os.name=='posix','Unix secret protection')
    def test_unix_public_secret_or_symlink_is_refused(self):
        self.arm();self.secret.chmod(0o644)
        with self.assertRaises(EmailError):self.mail.deliver(self.profile,alert())
        actual=self.root/'actual';self.secret.rename(actual);actual.chmod(0o600);self.secret.symlink_to(actual)
        with self.assertRaises(EmailError):self.mail.deliver(self.profile,alert())
        self.transport.assert_not_called()

    def test_cli_recomputes_local_health_and_does_not_accept_user_supplied_message(self):
        from nexydao.operations_email import main
        self.arm();path=self.root/'profile.json';path.write_text(json.dumps(self.profile));path.chmod(0o600)
        args=['mail','send','--state',str(self.state),'--profile',str(path),'--backup-dir',str(self.root/'backup')]
        environment={'NEXYDAO_DB':self.profile['source_db'],'NEXYDAO_API_BUDGET_USD':'0.10'};output=io.StringIO()
        with patch.dict(os.environ,environment,clear=True),patch('sys.argv',args),patch('sys.stdout',output), \
                patch('nexydao.operations_email.operations_health',return_value=alert()) as health,patch('nexydao.operations_email.send_gmail') as sender:
            main()
        health.assert_called_once();sender.assert_called_once();self.assertTrue(json.loads(output.getvalue())['smtp_accepted'])
        with patch.dict(os.environ,environment,clear=True),patch('sys.argv',args+['--message','anything']), \
                patch('sys.stderr'),self.assertRaises(SystemExit):main()
