"""Bounded historical links; past decisions never become current evidence or votes."""
import hashlib
import json
import uuid

from .records import PROPOSAL, REVIEW, VOTE, validate

MAX_REVISIONS = 3
MAX_PARENT_BYTES = 262144
FIELDS = {'parent_run_id', 'parent_result_sha256', 'root_run_id', 'depth'}


def _load(store, identifier):
    if not isinstance(identifier, str):
        raise ValueError('Revision parent requires a canonical run UUID')
    try:
        if str(uuid.UUID(identifier)) != identifier:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('Revision parent requires a canonical run UUID') from None
    row = store.db.execute(
        'SELECT status,mode,CASE WHEN length(CAST(result AS BLOB))<=? THEN result END '
        'FROM runs WHERE id=?', (MAX_PARENT_BYTES, identifier)).fetchone()
    if row is None or row[:2] != ('completed', 'ai') or row[2] is None:
        raise ValueError('Revision requires a bounded completed AI run')
    result = json.loads(row[2])
    if (not isinstance(result, dict) or result.get('run_id') != identifier
            or result.get('mode') != 'ai' or type(result.get('schema_version')) is not int
            or result['schema_version'] != 1):
        raise ValueError('Invalid revision parent record')
    validate(result.get('proposal'), PROPOSAL)
    if (not isinstance(result.get('risk_reviews'), list) or len(result['risk_reviews']) != 2
            or not isinstance(result.get('committee_votes'), list) or len(result['committee_votes']) != 3):
        raise ValueError('Incomplete revision parent reviews')
    for review in result['risk_reviews']:
        validate(review, REVIEW)
    for vote in result['committee_votes']:
        validate(vote, VOTE)
    raw = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    digest = hashlib.sha256(raw).hexdigest()
    link = store.db.execute('SELECT metadata FROM run_revisions WHERE child_run_id=?', (identifier,)).fetchone()
    relation = result.get('revision')
    if (relation is None) != (link is None) or (link and json.loads(link[0]) != relation):
        raise ValueError('Revision audit link mismatch')
    if relation is not None and (not isinstance(relation, dict) or set(relation) != FIELDS):
        raise ValueError('Invalid revision lineage')
    return result, digest, relation


def prepare_revision(store, parent_id):
    nodes = []
    seen = set()
    identifier = parent_id
    while True:
        if identifier in seen or len(nodes) >= MAX_REVISIONS:
            raise ValueError('Revision depth limit or cycle')
        seen.add(identifier)
        result, digest, relation = _load(store, identifier)
        nodes.append((identifier, result, digest, relation))
        if relation is None:
            break
        identifier = relation['parent_run_id']
    root = nodes[-1][0]
    for index, (_, _, _, relation) in enumerate(nodes[:-1]):
        if (type(relation['depth']) is not int or relation['depth'] != len(nodes)-index-1
                or relation['root_run_id'] != root
                or relation['parent_result_sha256'] != nodes[index+1][2]):
            raise ValueError('Revision ancestry changed')
    parent = nodes[0][1]
    metadata = {'parent_run_id': parent_id, 'parent_result_sha256': nodes[0][2],
                'root_run_id': root, 'depth': len(nodes)}
    history = {'verification': 'unverified_historical_decision', 'lineage': metadata,
               'previous_proposal': parent['proposal'], 'previous_risk_reviews': parent['risk_reviews'],
               'previous_committee_votes': parent['committee_votes']}
    return metadata, history, 'research_reports' in parent, 'portfolio_plan' in parent


def assert_parent_current(store, metadata):
    if prepare_revision(store, metadata['parent_run_id'])[0] != metadata:
        raise ValueError('Revision parent changed during cycle')
