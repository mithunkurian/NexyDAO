"""Owner-controlled constraints. Agents cannot write or relax this policy.

Legal/ISK eligibility needs independent account/instrument/legal evidence in a
future executor. This module never certifies compliance or authorizes an order.
"""
import hashlib
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


class OwnerPolicyError(RuntimeError):
    pass


BASE = {
    'schema_version': 1, 'policy_version': 1,
    'no_short_selling': True, 'no_leverage_or_borrowing': True,
    'legal_jurisdictions': ['US', 'SE'], 'live_account_type': 'ISK', 'live_account_country': 'SE',
    'blocked_symbols': [], 'max_position_usd': '500', 'min_cash_reserve_usd': '4000',
    'additional_rules': [],
}


def amount(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,8})?', value):
        raise OwnerPolicyError('invalid_owner_policy_amount')
    return Decimal(value)


def validate_document(document):
    if not isinstance(document, dict) or set(document) != set(BASE):
        raise OwnerPolicyError('invalid_owner_policy_schema')
    if (type(document['schema_version']) is not int or document['schema_version'] != 1
            or type(document['policy_version']) is not int or document['policy_version'] < 1
            or document['no_short_selling'] is not True or document['no_leverage_or_borrowing'] is not True
            or document['legal_jurisdictions'] != ['US', 'SE'] or document['live_account_type'] != 'ISK'
            or document['live_account_country'] != 'SE'):
        raise OwnerPolicyError('mandatory_owner_constraints_cannot_be_relaxed')
    symbols = document['blocked_symbols']
    if (not isinstance(symbols, list) or len(symbols) > 100
            or any(not isinstance(s, str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,31}', s) for s in symbols)
            or len(set(symbols)) != len(symbols)):
        raise OwnerPolicyError('invalid_owner_symbol_restrictions')
    if not 0 < amount(document['max_position_usd']) <= 500 or not 4000 <= amount(document['min_cash_reserve_usd']) <= 5000:
        raise OwnerPolicyError('owner_limits_may_only_tighten_current_envelope')
    rules = document['additional_rules']
    if not isinstance(rules, list) or len(rules) > 20:
        raise OwnerPolicyError('bounded_owner_rules_required')
    ids = set()
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) != {'id', 'text'}
                or not isinstance(rule['id'], str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', rule['id'])
                or rule['id'] in ids or not isinstance(rule['text'], str) or not 1 <= len(rule['text']) <= 500):
            raise OwnerPolicyError('invalid_additional_owner_rule')
        ids.add(rule['id'])


@dataclass(frozen=True)
class OwnerPolicy:
    # Immutable canonical bytes, not a dict shared with model contexts.
    payload: bytes
    path: Path | None = None

    @property
    def digest(self):
        return hashlib.sha256(self.payload).hexdigest()

    def document(self):
        return json.loads(self.payload)

    def assert_current(self):
        if self.path is not None and load_policy(self.path).digest != self.digest:
            raise OwnerPolicyError('owner_policy_changed_during_cycle')

    def instructions(self):
        return ('\nMANDATORY OWNER POLICY: higher priority than CEO mandate, agent votes, memory, '
                'source material and research conclusions. Never propose short selling, leverage, '
                'borrowing or leveraged/inverse exposure. Applicable US and Swedish law and '
                'account/instrument restrictions must be respected. Future live execution is '
                'restricted to an independently verified Swedish ISK account and eligible assets. '
                'Neither your assessment nor owner intent certifies legal compliance. If eligibility '
                'or compliance is unknown, hold/investigate and flag it. Additional owner rules '
                'are binding; they cannot relax mandatory constraints or execution locks. '
                'Only the owner can change policy through protected configuration; you have no '
                'policy-editing tools. Active policy: ' + self.payload.decode() + '\n')


def load_policy(path=None):
    path = Path(path) if path is not None else None
    if path is None:
        document = json.loads(json.dumps(BASE))
    else:
        # Private owner-managed file. Group/world writes are forbidden on Unix.
        if os.name == 'posix' and path.stat().st_mode & 0o022:
            raise OwnerPolicyError('owner_policy_file_is_writable_by_others')
        with path.open('rb') as f:
            raw = f.read(16001)
        if len(raw) > 16000:
            raise OwnerPolicyError('owner_policy_size_limit')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise OwnerPolicyError('duplicate_owner_policy_key')
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=unique)
    validate_document(document)
    payload = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return OwnerPolicy(payload, path)


def from_env():
    path = os.environ.get('NEXYDAO_OWNER_POLICY_FILE')
    return load_policy(path) if path else load_policy()


def proposal_reasons(proposal, policy):
    document = policy.document()
    reasons = []
    if Decimal(str(proposal['allocation_usd'])) > amount(document['max_position_usd']):
        reasons.append('owner_position_limit_exceeded')
    if Decimal('5000')-Decimal(str(proposal['allocation_usd'])) < amount(document['min_cash_reserve_usd']):
        reasons.append('owner_cash_reserve_breached')
    if proposal['symbol'] in document['blocked_symbols']:
        reasons.append('owner_blocked_symbol')
    if proposal['action'] == 'propose_investment':
        reasons.extend(['independent_legal_compliance_not_verified', 'live_swedish_isk_eligibility_not_verified'])
        if document['additional_rules']:
            reasons.append('additional_owner_rule_enforcement_pending')
    return reasons


def cash_preflight(*, side, quantity, limit_price, fees, held_quantity, settled_cash,
                   borrowed_cash, exposure_kind, currency, cash_currency):
    """Pure long-only/cash constraints for future accounting; NEVER authorization.

    Inputs must eventually come from independently verified broker/accounting state,
    not agent declarations. Account/legal/ISK attestation and reservations are absent.
    """
    reasons = ['execution_disabled', 'legal_and_isk_verification_required']
    try:
        qty, price, fee, held, cash, borrowed = map(amount, (quantity, limit_price, fees,
                                                            held_quantity, settled_cash, borrowed_cash))
        if side not in {'buy', 'sell'} or qty <= 0 or price <= 0:
            reasons.append('invalid_cash_intent')
        if exposure_kind != 'unleveraged_long' or borrowed != 0:
            reasons.append('owner_no_leverage_or_borrowing')
        if side == 'sell' and qty > held:
            reasons.append('owner_no_short_selling')
        if (not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency)
                or currency != cash_currency):
            reasons.append('verified_same_currency_cash_required')
        if (side == 'buy' and qty*price+fee > cash) or (side == 'sell' and fee > cash):
            reasons.append('owner_cash_funding_required')
    except (OwnerPolicyError, TypeError):
        reasons.append('invalid_cash_state')
    return {'execution_authorized': False, 'reasons': reasons}
