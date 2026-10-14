import copy
import hashlib
import hmac
import json
import ssl
import time
import unittest
from decimal import Decimal
from unittest.mock import patch,MagicMock

import test_reconciliation as fixtures
from nexydao.ibkr import ProbeError
from nexydao.market import canonical
from nexydao.web_ledger import (WebConfig,collect_web_ledger,validate_web_ledger,parse_json,
                               monetary,get_json,save_web_ledger,load_web_ledger)


class WebLedgerTests(unittest.TestCase):
    setUp=fixtures.ReconciliationTests.setUp

    def web(self):return WebConfig('DU123',self.key)

    def collect(self,data=None,mode=2,accounts=None):
        # Keep mocked receipt time behind real consumer time, even early in a second.
        now=int(time.time())-1
        values={'USD':{'acctcode':'DU123','currency':'USD','cashbalance':5000,'settledcash':5000,'timestamp':now}} if data is None else data
        self.calls=[]
        def read(config,path,timeout):
            self.calls.append(path)
            if path.endswith('sso/validate'):return {'RESULT':True,'LOGIN_TYPE':mode,'AUTH_TIME':now*1000,'EXPIRES':120000}
            if path.endswith('portfolio/accounts'):return [{'id':'DU123','accountId':'DU123'}] if accounts is None else accounts
            return values
        return collect_web_ledger(self.web(),read,lambda:now+0.25)

    def test_supported_currency_fields_and_double_identity_checks(self):
        payload=self.collect()
        self.assertEqual(payload['cash'][0]['settled_cash'],'5000')
        self.assertEqual(len(self.calls),5)
        self.assertEqual(self.calls[0],self.calls[3])
        self.assertEqual(self.calls[1],self.calls[4])
        self.assertNotIn('DU123',json.dumps(payload))

    def test_live_and_mixed_accounts_fail_before_ledger(self):
        for mode in (1,True,'2'):
            with self.assertRaises(ProbeError):self.collect(mode=mode)
            self.assertEqual(len(self.calls),1)
        for accounts in ([],[{'id':'DU999','accountId':'DU999'}],
                         [{'id':'DU123','accountId':'DU123'},{'id':'U777','accountId':'U777'}]):
            with self.assertRaises(ProbeError):self.collect(accounts=accounts)
            self.assertEqual(len(self.calls),2)

    def test_base_never_supplies_missing_currency_cash(self):
        with self.assertRaises(ProbeError):self.collect(data={'BASE':{'acctcode':'DU123','currency':'BASE','settledcash':1000000}})

    def test_native_stale_future_and_milliseconds_rejected(self):
        now=int(time.time())
        for stamp in (now-61,now+1,now*1000):
            with self.assertRaises(ProbeError):self.collect(data={'USD':{'acctcode':'DU123','currency':'USD','cashbalance':5000,'settledcash':5000,'timestamp':stamp}})

    def test_identity_currency_and_missing_settlement_rejected(self):
        row={'acctcode':'DU123','currency':'USD','cashbalance':5000,'settledcash':5000,'timestamp':int(time.time())}
        for key,value in (('acctcode','U123'),('currency','EUR'),('settledcash',None),('cashbalance',True)):
            changed=copy.deepcopy(row);changed[key]=value
            with self.assertRaises(ProbeError):self.collect(data={'USD':changed})

    def test_decimal_precision_duplicate_json_and_exponent_bounds(self):
        self.assertEqual(parse_json(b'{"value":1.23456789}')['value'],Decimal('1.23456789'))
        for body in (b'{"x":1,"x":2}',b'{"x":NaN}',b'x'*65537):
            with self.assertRaises(ProbeError):parse_json(body)
        for value in (Decimal('1e999999'),Decimal('1e-999999'),Decimal('NaN'),'5000',True):
            with self.assertRaises(ProbeError):monetary(value)

    def test_fixed_https_get_and_no_mutation_paths(self):
        context=ssl.create_default_context()
        response=MagicMock();response.status=200
        response.getheader.side_effect=lambda key,default='':{'Content-Type':'application/json','Content-Encoding':'identity'}.get(key,default)
        response.read.return_value=b'{"x":1}'
        with patch('nexydao.web_ledger.ssl.create_default_context',return_value=context),patch('nexydao.web_ledger.http.client.HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value=response
            self.assertEqual(get_json(self.web(),'/v1/api/portfolio/accounts',5),{'x':1})
            self.assertEqual(connection.call_args.args,('127.0.0.1',5000))
            self.assertEqual(connection.return_value.request.call_args.args,('GET','/v1/api/portfolio/accounts'))
            connection.return_value.close.assert_called_once()
            for path in ('/v1/api/iserver/account/DU123/orders','https://evil.test','/v1/api/portfolio/DU999/ledger'):
                with self.assertRaises(PermissionError):get_json(self.web(),path,5)

    def test_unverified_tls_redirects_html_compression_fail(self):
        context=MagicMock();context.verify_mode=ssl.CERT_NONE;context.check_hostname=False
        with patch('nexydao.web_ledger.ssl.create_default_context',return_value=context),patch('nexydao.web_ledger.http.client.HTTPSConnection') as connection:
            with self.assertRaises(ProbeError):get_json(self.web(),'/v1/api/portfolio/accounts',5)
            connection.assert_not_called()
        context=ssl.create_default_context()
        for status,ctype,encoding in ((302,'application/json','identity'),(200,'text/html','identity'),(200,'application/json','gzip')):
            response=MagicMock();response.status=status
            response.getheader.side_effect=lambda key,default='':{'Content-Type':ctype,'Content-Encoding':encoding}.get(key,default)
            with patch('nexydao.web_ledger.ssl.create_default_context',return_value=context),patch('nexydao.web_ledger.http.client.HTTPSConnection') as connection:
                connection.return_value.getresponse.return_value=response
                with self.assertRaises(ProbeError):get_json(self.web(),'/v1/api/portfolio/accounts',5)

    def test_signed_receipt_roundtrip_tamper_and_wrong_pin(self):
        payload=self.collect()
        receipt={'payload':payload,'signature':hmac.new(b'x'*32,canonical(payload),hashlib.sha256).hexdigest()}
        self.path.write_text(json.dumps(receipt))
        self.assertEqual(load_web_ledger(self.web(),self.key,self.path),payload)
        with self.assertRaises(ProbeError):load_web_ledger(WebConfig('DU999',self.key),self.key,self.path)
        receipt['payload']['cash'][0]['settled_cash']='9999';self.path.write_text(json.dumps(receipt))
        with self.assertRaises(ProbeError):load_web_ledger(self.web(),self.key,self.path)

    def test_expiry_and_paper_scope_cannot_be_forged(self):
        valid=self.collect()
        for key,value in (('scope','BASE'),('paper_session_verified',False),('expires_at',time.time()-1)):
            payload=copy.deepcopy(valid);payload[key]=value
            with self.assertRaises(ProbeError):validate_web_ledger(payload,'DU123')

    def test_failed_collection_preserves_last_receipt(self):
        self.path.write_text('old')
        with patch('nexydao.web_ledger.collect_web_ledger',side_effect=ProbeError('unavailable')):
            with self.assertRaises(ProbeError):save_web_ledger(self.web(),self.key,self.path)
        self.assertEqual(self.path.read_text(),'old')
