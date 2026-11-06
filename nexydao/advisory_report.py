"""Read a saved AI advisory result and its recorded API costs."""

import argparse
from contextlib import closing
from decimal import Decimal, DecimalException, localcontext
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .store import _api_charge

MAX_RESULT_BYTES = 262144
MAX_COST_ROWS = 64
MAX_CITATION_COMPLETIONS = 16


def _recorded_evidence(db, run_id):
    rows = db.execute('SELECT CASE WHEN length(CAST(payload AS BLOB))<=? THEN payload END '
                      "FROM events WHERE run_id=? AND role='input' LIMIT 2",
                      (MAX_RESULT_BYTES, run_id)).fetchall()
    if len(rows) != 1 or rows[0][0] is None:
        return None
    evidence = json.loads(rows[0][0]).get('evidence', [])
    if not isinstance(evidence, list) or len(evidence) > 10:
        raise ValueError('Invalid recorded advisory evidence')
    snapshots = []
    for item in evidence:
        label = item.get('verification')
        if label not in ('verified_filing_observation', 'verified_quote'):
            continue
        snapshot = {name: item[name] for name in ('id', 'verification', 'source_url', 'observed_at', 'expires_at')}
        if label == 'verified_filing_observation':
            fact = item['fact']
            snapshot['fact'] = {name: fact[name] for name in
                                ('symbol', 'cik', 'concept', 'unit', 'value', 'start', 'end', 'filed', 'form', 'accession')}
        else:
            quote = json.loads(item['summary'])
            snapshot['quote'] = {name: quote['quote'][name] for name in ('bid', 'ask', 'event_time')}
            snapshot['quote']['symbol'] = quote['contract']['symbol']
        snapshots.append(snapshot)
    return snapshots


def _citation_completions(db, run_id):
    rows = db.execute("SELECT role,CASE WHEN length(CAST(payload AS BLOB))<=1024 THEN payload END "
                      "FROM events WHERE run_id=? AND role GLOB '*:evidence_completed' "
                      'ORDER BY sequence LIMIT ?', (run_id, MAX_CITATION_COMPLETIONS + 1)).fetchall()
    if len(rows) > MAX_CITATION_COMPLETIONS:
        raise ValueError('Oversized advisory citation audit')
    completions = []
    for role, raw in rows:
        if raw is None or not re.fullmatch(r'[a-z_]{1,32}:evidence_completed', role):
            raise ValueError('Invalid advisory citation audit')
        added = json.loads(raw).get('added_evidence_id', '')
        if not re.fullmatch(r'sec-[0-9a-f]{64}', added):
            raise ValueError('Invalid advisory citation ID')
        completions.append({'role': role.removesuffix(':evidence_completed'), 'added_evidence_id': added})
    return completions


def read_report(path, run_id=None):
    if run_id is not None and str(uuid.UUID(run_id)) != run_id:
        raise ValueError('Expected a canonical run UUID')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        deadline = time.monotonic() + 5
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('BEGIN')
        query = ('SELECT id,created,status,CASE WHEN length(CAST(result AS BLOB))<=? THEN result END '
                 "FROM runs WHERE mode='ai'")
        if run_id is None:
            row = db.execute(query + ' ORDER BY created DESC,id DESC LIMIT 1', (MAX_RESULT_BYTES,)).fetchone()
        else:
            row = db.execute(query + ' AND id=?', (MAX_RESULT_BYTES, run_id)).fetchone()
        if row is None:
            raise ValueError('AI advisory run not found')
        identifier, created, status, raw = row
        if status not in ('running', 'failed', 'completed') or (status != 'running' and raw is None):
            raise ValueError('Invalid or oversized advisory result')
        result = json.loads(raw) if raw is not None else None
        if status == 'completed' and (not isinstance(result, dict) or result.get('run_id') != identifier):
            raise ValueError('Invalid completed advisory record')
        costs = db.execute('SELECT CASE WHEN length(charged)<=80 THEN charged END,status '
                           'FROM costs WHERE run_id=? LIMIT ?',
                           (identifier, MAX_COST_ROWS + 1)).fetchall()
        if len(costs) > MAX_COST_ROWS or any(state not in ('reserved', 'reported') for _, state in costs):
            raise ValueError('Invalid or oversized advisory costs')
        with localcontext(prec=100):
            total = sum((_api_charge(amount) for amount, _ in costs), Decimal(0))
        evidence = _recorded_evidence(db, identifier)
        completions = _citation_completions(db, identifier)
    return {'run_id': identifier, 'created_at': created, 'status': status,
            'recorded_api_costs': {'estimated_or_reserved_usd': str(total), 'calls': len(costs),
                                   'unsettled_calls': sum(state == 'reserved' for _, state in costs)},
            'recorded_verified_evidence': evidence,
            'application_added_citations': completions, 'result': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    try:
        report = read_report(args.db, args.run_id)
        print(json.dumps(report, indent=2, allow_nan=False))
    except (OSError, sqlite3.Error, ValueError, DecimalException, AttributeError, KeyError, TypeError):
        parser.exit(1, 'Saved advisory report unavailable.\n')


if __name__ == '__main__':
    main()
