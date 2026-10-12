"""Fixed SEC endpoints; bounded public retrieval and typed filing observations.

No agent-supplied URL, redirect, proxy, HTML or custom taxonomy is accepted.
SEC facts are filer reports, not independent proof of economic truth.
"""
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from .ibkr import save_snapshot
from .market import canonical, read_key

HOST = 'data.sec.gov'
CONCEPTS = ('Assets', 'NetIncomeLoss')
MAX_BYTES = 1_000_000
RECEIPT_TTL = 86400
MAX_FILING_AGE = 180


class SourceError(RuntimeError):
    """Fixed local codes only; no HTTP bodies, headers or contact information."""


def universe(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        raise ValueError('Configure one to three research issuers')
    symbols, ciks = set(), set()
    for issuer in value:
        if not isinstance(issuer, dict) or set(issuer) != {'symbol', 'cik'}:
            raise ValueError('Issuer requires symbol and ten-digit CIK')
        symbol, cik = issuer['symbol'], issuer['cik']
        if (not isinstance(symbol, str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,11}', symbol)
                or not isinstance(cik, str) or not re.fullmatch(r'[0-9]{10}', cik) or int(cik) == 0
                or symbol in symbols or cik in ciks):
            raise ValueError('Invalid or duplicate issuer')
        symbols.add(symbol)
        ciks.add(cik)
    return value


@dataclass(frozen=True)
class ResearchConfig:
    issuers: list
    key_path: Path
    user_agent: str = field(default='', repr=False)
    snapshot: Path = Path('data/sec-research.json')

    def __post_init__(self):
        universe(self.issuers)
        object.__setattr__(self, 'issuers', [dict(i) for i in self.issuers])

    @classmethod
    def from_env(cls):
        raw = os.environ.get('NEXYDAO_RESEARCH_UNIVERSE', '[]')
        key = os.environ.get('NEXYDAO_EVIDENCE_KEY_FILE', '')
        if len(raw) > 2048 or not key:
            raise ValueError('Bounded research universe and evidence key required')
        return cls(json.loads(raw), Path(key), os.environ.get('NEXYDAO_SEC_USER_AGENT', ''),
                   Path(os.environ.get('NEXYDAO_RESEARCH_SNAPSHOT', 'data/sec-research.json')))


def source_path(cik, concept=None):
    if not isinstance(cik, str) or not re.fullmatch(r'[0-9]{10}', cik) or int(cik) == 0:
        raise SourceError('invalid_source_identifier')
    if concept is None:
        return f'/submissions/CIK{cik}.json'
    if concept not in CONCEPTS:
        raise SourceError('unapproved_concept')
    return f'/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json'


class PublicTLS(http.client.HTTPSConnection):
    def connect(self):
        # Resolve once, reject every non-public answer, and connect to that exact
        # address. TLS still verifies the fixed hostname. No DNS rebinding gap.
        if self.host != HOST or self.port != 443 or self._tunnel_host:
            raise SourceError('unapproved_source_host')
        answers = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
            raise SourceError('non_public_source_address')
        family, kind, proto, _, address = answers[0]
        raw = socket.socket(family, kind, proto)
        try:
            raw.settimeout(self.timeout)
            raw.connect(address)
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
        except Exception:
            raw.close()
            raise


def fetch(path, user_agent):
    if not re.fullmatch(r'/submissions/CIK[0-9]{10}\.json|/api/xbrl/companyconcept/CIK[0-9]{10}/us-gaap/(Assets|NetIncomeLoss)\.json', path):
        raise SourceError('unapproved_source_path')
    if (not 10 <= len(user_agent) <= 256 or any(ord(c) < 32 or ord(c) > 126 for c in user_agent)
            or not re.search(r'[A-Za-z0-9._+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', user_agent)):
        raise SourceError('identifying_sec_user_agent_required')
    connection = PublicTLS(HOST, timeout=15)
    deadline = time.monotonic()+15
    try:
        connection.request('GET', path, headers={'User-Agent': user_agent, 'Accept': 'application/json',
                                                'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200:
            raise SourceError('sec_http_not_ok')
        if (response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json'
                or response.getheader('Content-Encoding', 'identity').lower() != 'identity'):
            raise SourceError('unsupported_sec_content')
        chunks = bytearray()
        # read1 performs at most one underlying read. Recompute the remaining
        # budget for every read, so a slow-drip body cannot renew the deadline.
        while True:
            if response.isclosed():
                if response.length not in (None, 0):
                    raise SourceError('incomplete_sec_response')
                break
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise SourceError('sec_response_timeout')
            response.fp.raw._sock.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BYTES+1-len(chunks)))
            if not chunk:
                if response.length not in (None, 0):
                    raise SourceError('incomplete_sec_response')
                break
            chunks.extend(chunk)
            if len(chunks)>MAX_BYTES:
                raise SourceError('source_size_limit')
        return bytes(chunks)
    except (OSError, http.client.HTTPException):
        raise SourceError('sec_transport_failure') from None
    finally:
        connection.close()


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise SourceError('source_size_limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SourceError('duplicate_source_key')
            result[key] = value
        return result
    def reject_constant(value):
        raise SourceError('nonfinite_source_number')
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_float=Decimal,
                          parse_constant=reject_constant)
    except (UnicodeError, ValueError):
        raise SourceError('invalid_source_json') from None


def numeric(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?[0-9]{1,30}(?:\.[0-9]{1,12})?', value):
        raise SourceError('invalid_filing_value')
    return Decimal(value)


def check_fact(fact, now):
    keys = {'symbol', 'cik', 'concept', 'unit', 'value', 'start', 'end', 'filed', 'form', 'accession'}
    if not isinstance(fact, dict) or set(fact) != keys:
        raise SourceError('invalid_fact_schema')
    universe([{'symbol': fact['symbol'], 'cik': fact['cik']}])
    if fact['concept'] not in CONCEPTS or fact['unit'] != 'USD' or fact['form'] not in {'10-K', '10-Q', '10-K/A', '10-Q/A'}:
        raise SourceError('unsupported_filing_fact')
    numeric(fact['value'])
    if not isinstance(fact['accession'], str) or not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}', fact['accession']):
        raise SourceError('invalid_filing_accession')
    try:
        end, filed = date.fromisoformat(fact['end']), date.fromisoformat(fact['filed'])
        today = datetime.fromtimestamp(now, timezone.utc).date()
        if end>filed:
            raise SourceError('future_filing_period')
        if not 0 <= (today-filed).days <= MAX_FILING_AGE or (filed-end).days>550:
            raise SourceError('stale_or_future_filing')
        if fact['concept'] == 'Assets':
            if fact['start'] != '':
                raise SourceError('invalid_instant_period')
        elif not 0 <= (end-date.fromisoformat(fact['start'])).days <= 400:
            raise SourceError('invalid_duration_period')
    except (TypeError, ValueError):
        raise SourceError('invalid_filing_date') from None


def extract(raw, issuer, concept, now):
    data = decode(raw)
    if (not isinstance(data, dict) or type(data.get('cik')) is not int or data['cik'] != int(issuer['cik'])
            or data.get('taxonomy') != 'us-gaap' or data.get('tag') != concept):
        raise SourceError('source_identity_mismatch')
    rows = data.get('units', {}).get('USD')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
        raise SourceError('bounded_usd_facts_required')
    candidates = []
    for row in rows:
        if not isinstance(row, dict) or row.get('form') not in {'10-K', '10-Q', '10-K/A', '10-Q/A'}:
            continue
        # Retain period boundaries, rather than calling every duration a quarter.
        value = row.get('val')
        if type(value) is not int and not isinstance(value, Decimal):
            raise SourceError('invalid_filing_value')
        fact = {**issuer, 'concept': concept, 'unit': 'USD', 'value': str(value),
                'start': row.get('start', ''), 'end': row.get('end'), 'filed': row.get('filed'),
                'form': row.get('form'), 'accession': row.get('accn')}
        # Historical records are expected. Invalid dates/values fail the source;
        # valid older observations are excluded by a separate freshness check.
        try:
            check_fact(fact, now)
        except SourceError as error:
            if str(error) == 'stale_or_future_filing':
                # Future filings are rejected, not silently ignored as historical.
                if date.fromisoformat(fact['filed']) > datetime.fromtimestamp(now, timezone.utc).date():
                    raise
                continue
            raise
        candidates.append(fact)
    if not candidates:
        raise SourceError('no_recent_filing_fact')
    latest = max(candidates, key=lambda f: (f['end'], f['filed'], f['start']))
    context = (latest['end'], latest['filed'], latest['start'])
    same = [f for f in candidates if (f['end'], f['filed'], f['start']) == context]
    if len({numeric(f['value']) for f in same}) != 1:
        raise SourceError('contradictory_source_facts')
    return max(same, key=lambda f: f['accession'])


def collect(config, getter=fetch, clock=time.time, sleeper=time.sleep):
    read_key(config.key_path)  # Reject bad/private-key permissions before network.
    started = int(clock())
    facts, sources = [], []
    def get(path):
        if int(clock())-started > 180:
            raise SourceError('collection_time_limit')
        return getter(path, config.user_agent)
    for issuer in config.issuers:
        path = source_path(issuer['cik'])
        raw = get(path)
        data = decode(raw)
        if (not isinstance(data, dict) or str(data.get('cik')).zfill(10) != issuer['cik']
                or not isinstance(data.get('tickers'), list) or issuer['symbol'] not in data['tickers']):
            raise SourceError('ticker_cik_mismatch')
        sources.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest()})
        for concept in CONCEPTS:
            sleeper(0.5)  # At most two serial requests/second in this process.
            path = source_path(issuer['cik'], concept)
            raw = get(path)
            facts.append(extract(raw, issuer, concept, int(clock())))
            sources.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest()})
        sleeper(0.5)
    received = int(clock())
    if received-started > 180:
        raise SourceError('collection_time_limit')
    payload = {'schema_version': 1, 'source': 'sec_companyconcept', 'retrieved_at': received,
               'expires_at': received+RECEIPT_TTL, 'issuers': [dict(i) for i in config.issuers], 'facts': facts, 'sources': sources}
    validate_receipt(payload, config, received)
    return payload


def validate_receipt(payload, config, now):
    if (not isinstance(payload, dict) or set(payload) != {'schema_version', 'source', 'retrieved_at', 'expires_at', 'issuers', 'facts', 'sources'}
            or type(payload['schema_version']) is not int or payload['schema_version'] != 1
            or payload['source'] != 'sec_companyconcept' or payload['issuers'] != config.issuers):
        raise SourceError('invalid_research_receipt')
    retrieved, expiry = payload['retrieved_at'], payload['expires_at']
    if (type(retrieved) is not int or type(expiry) is not int or retrieved > now+2
            or retrieved <= 0 or expiry != retrieved+RECEIPT_TTL or now >= expiry):
        raise SourceError('expired_research_receipt')
    facts = payload['facts']
    if not isinstance(facts, list) or len(facts) != len(config.issuers)*len(CONCEPTS):
        raise SourceError('incomplete_research_facts')
    required = {(i['symbol'], i['cik'], c) for i in config.issuers for c in CONCEPTS}
    for fact in facts:
        check_fact(fact, now)
    if {(f['symbol'], f['cik'], f['concept']) for f in facts} != required:
        raise SourceError('research_fact_identity_mismatch')
    expected_paths = {source_path(i['cik'], c) for i in config.issuers for c in (None, *CONCEPTS)}
    sources = payload['sources']
    if not isinstance(sources, list) or len(sources) != len(expected_paths):
        raise SourceError('incomplete_source_provenance')
    for source in sources:
        if (not isinstance(source, dict) or set(source) != {'path', 'sha256'} or source['path'] not in expected_paths
                or not isinstance(source['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', source['sha256'])):
            raise SourceError('invalid_source_provenance')
    if {s['path'] for s in sources} != expected_paths:
        raise SourceError('incomplete_source_provenance')


def run_source_check(config):
    payload = collect(config)
    signature = hmac.new(read_key(config.key_path), canonical(payload), hashlib.sha256).hexdigest()
    digest = save_snapshot(config.snapshot, {'payload': payload, 'signature': signature})
    return {'status': 'sec_filing_observations_collected', 'issuers': len(config.issuers),
            'facts': len(payload['facts']), 'snapshot_sha256': digest, 'execution_authorized': False}


def load_research_evidence(path, config, now=None):
    now = time.time() if now is None else now
    with path.open('rb') as f:
        raw = f.read(64001)
    if len(raw) > 64000:
        raise SourceError('research_receipt_size_limit')
    receipt = json.loads(raw)
    if not isinstance(receipt, dict) or set(receipt) != {'payload', 'signature'}:
        raise SourceError('unsigned_research_receipt')
    signature = hmac.new(read_key(config.key_path), canonical(receipt['payload']), hashlib.sha256).hexdigest()
    if not isinstance(receipt['signature'], str) or not hmac.compare_digest(signature, receipt['signature']):
        raise SourceError('research_signature_mismatch')
    payload = receipt['payload']
    validate_receipt(payload, config, now)
    hashes = {s['path']: s['sha256'] for s in payload['sources']}
    return [{'id': 'sec-' + hashlib.sha256(canonical(f)).hexdigest(),
             'source_url': 'https://' + HOST + source_path(f['cik'], f['concept']),
             'observed_at': f['filed'], 'summary': json.dumps(f, sort_keys=True), 'fact': f,
             'verification': 'verified_filing_observation', 'expires_at': payload['expires_at'],
             'raw_sha256': hashes[source_path(f['cik'], f['concept'])]} for f in payload['facts']]


def check_research_freshness(evidence, now=None):
    if not any(e.get('verification') == 'verified_filing_observation' for e in evidence):
        return
    now = time.time() if now is None else now
    for item in evidence:
        if item.get('verification') == 'verified_filing_observation':
            if type(item.get('expires_at')) is not int or now >= item['expires_at']:
                raise SourceError('research_expired_during_deliberation')
            check_fact(item['fact'], now)
