"""Fresh signed summary checks, explicitly incomplete broker reconciliation."""
import hashlib
import hmac
import json
import re
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .ibkr import ProbeError, TAGS, probe, save_snapshot
from .market import canonical, read_key

TTL = 60


def validate_summary(snapshot, expected_account, now=None):
    now = time.time() if now is None else now
    if not expected_account: raise ProbeError('exact_account_pin_required')
    keys = {'schema_version', 'source', 'retrieved_at', 'protocol_version', 'account',
            'paper_identity_evidence', 'expected_account_matched', 'execution_authorized', 'values'}
    if not isinstance(snapshot, dict) or set(snapshot) != keys: raise ProbeError('invalid_account_snapshot')
    if (type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1
            or snapshot['source'] != 'ibkr_gateway_account_summary'
            or type(snapshot['protocol_version']) is not int or not 100 <= snapshot['protocol_version'] <= 178
            or snapshot['account'] != expected_account or snapshot['expected_account_matched'] is not True
            or snapshot['execution_authorized'] is not False
            or snapshot['paper_identity_evidence'] != 'single_DU_account_namespace'):
        raise ProbeError('account_snapshot_identity_failed')
    try:
        observed = datetime.fromisoformat(snapshot['retrieved_at'])
        if observed.utcoffset() is None: raise ValueError()
        stamp = observed.timestamp()
    except (ValueError, TypeError, OverflowError):
        raise ProbeError('invalid_account_snapshot_time') from None
    if not stamp <= now < stamp + TTL: raise ProbeError('account_snapshot_expired_or_future')
    rows = snapshot['values']
    if not isinstance(rows, list) or not 4 <= len(rows) <= 40: raise ProbeError('invalid_account_snapshot_values')
    values = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'tag', 'currency', 'value'}
                or row['tag'] not in TAGS or not isinstance(row['currency'], str)
                or not re.fullmatch(r'[A-Z]{3}', row['currency']) or not isinstance(row['value'], str)
                or not re.fullmatch(r'-?[0-9]{1,16}(?:\.[0-9]{1,12})?', row['value'])):
            raise ProbeError('invalid_account_snapshot_values')
        key = row['tag'], row['currency']
        if key in values: raise ProbeError('duplicate_account_snapshot_value')
        values[key] = Decimal(row['value'])
    if {tag for tag, _ in values} != set(TAGS): raise ProbeError('incomplete_account_snapshot')
    return values


def report(snapshot, expected_account, now=None):
    values = validate_summary(snapshot, expected_account, now)
    # BuyingPower/AvailableFunds/TotalCashValue do not prove settled USD cash.
    return {'status': 'fresh_summary_verified_reconciliation_incomplete',
            'summary_values_received': len(values), 'exact_account_pin_matched': True,
            'negative_balance_observed': any(v < 0 for v in values.values()),
            'usd_summary_complete': all((tag, 'USD') in values for tag in TAGS),
            'broker_reconciliation': False,
            'missing_checks': ['settled_cash_by_currency', 'positions_and_contracts',
                               'open_orders_and_reservations', 'fills_fees_and_external_transfers'],
            'broker_balances_imported': False, 'execution_authorized': False}


def collect_audit(config, key_path, path):
    if not config.expected_account: raise ProbeError('exact_account_pin_required')
    key = read_key(key_path)  # Validate key before network use.
    snapshot = probe(config)
    result = report(snapshot, config.expected_account)
    payload = {'snapshot': snapshot}
    receipt = {'payload': payload, 'signature': hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}
    result['receipt_sha256'] = save_snapshot(path, receipt)
    return result


def load_audit(config, key_path, path):
    with Path(path).open('rb') as stream:
        body = stream.read(32769)
    if len(body) > 32768: raise ProbeError('account_receipt_size_limit')
    try:
        receipt = json.loads(body)
        if (not isinstance(receipt, dict) or set(receipt) != {'payload', 'signature'}
                or not isinstance(receipt['payload'], dict) or set(receipt['payload']) != {'snapshot'}
                or not isinstance(receipt['signature'], str)):
            raise ValueError()
        actual = hmac.new(read_key(key_path), canonical(receipt['payload']), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual, receipt['signature']): raise ValueError()
    except (ValueError, TypeError):
        raise ProbeError('invalid_account_receipt_signature') from None
    return report(receipt['payload']['snapshot'], config.expected_account)
