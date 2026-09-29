"""S5-06: isolated, repeatable policy replacement validation.

Uses captured authoritative HTML and the existing processor, chunker, indexer
CLI and retriever. Only HTTP responses are replayed. Real BGE-M3 and embedded
Qdrant are the default. --controls-only uses fixed vectors and is NOT semantic
embedding evidence. Never opens the application's qdrant_storage directory.
"""

import argparse
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import tempfile
from unittest.mock import patch

from bs4 import BeautifulSoup
import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from ingestion import qdrant_indexer as indexer
from ingestion.embedding_config import get_config
from ingestion.policy_chunker import chunk_policy
from ingestion.policy_processor import process_policy
from ingestion.embedder import embed_text
from retrieval.policy_retriever import PolicyRetriever

FIXTURES = Path(__file__).parent / 'tests/fixtures/policy_currency'
OLD = 'feedback on assessment tasks is timely, constructive, and formative;'
NEW = ('S5-06 TEST REVISION ONLY: feedback on assessment tasks is provided '
       'within twelve working days through the subject learning platform;')
QUESTION = 'What does the Assessment Policy say about feedback on assessment tasks?'


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def controlled_revision(html):
    """Change one clause and remove the last section to expose orphan chunks."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', id='sliph-document-content')
    matches = content.find_all(string=lambda text: text and OLD in text)
    if len(matches) != 1:
        raise ValueError('Expected exactly one baseline feedback clause.')
    matches[0].replace_with(matches[0].replace(OLD, NEW))
    heading = content.find(['h1', 'h2', 'h3', 'h4'], string=lambda text: text and
                           'Section 8 - Authority and Associated Information' in text)
    if heading is None:
        raise ValueError('Expected final section heading.')
    for sibling in list(heading.next_siblings):
        sibling.extract()
    heading.extract()
    return str(soup)


def run(output, controls_only=False):
    # Refuse to overwrite an earlier evidence run.
    output.mkdir(parents=True, exist_ok=False)
    report = {
        'task': 'S5-06', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'fixed-vector-controls-only' if controls_only else 'real-BGE-M3',
        'http_mode': 'replayed captured authoritative HTML; synthetic revision',
        'synthetic_revision_is_not_university_policy': True,
        'configuration': get_config(), 'python': platform.python_version(),
        'storage': 'isolated TemporaryDirectory, embedded Qdrant, deleted after run',
        'base_commit': '92d4647445d42301f7ab44925da23a73008ab354',
        'pipeline_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path('ingestion').glob('*.py'))
            + sorted(Path('retrieval').glob('*.py'))},
        'packages': {p: version(p) for p in ['qdrant-client', 'beautifulsoup4', 'requests']},
        'question': QUESTION, 'checks': [],
    }

    def check(name, condition):
        report['checks'].append({'check': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)

    try:
        source = json.loads((FIXTURES / 'source.json').read_text())
        baseline_html = (FIXTURES / 'baseline.html').read_bytes().decode('utf-8')
        status_html = (FIXTURES / 'status.html').read_bytes().decode('utf-8')
        report['source'] = source
        for name, text in [('baseline.html', baseline_html), ('status.html', status_html)]:
            check(f'{name} source hash verified', digest(text) == source['files'][name]['sha256'])
        revised_html = controlled_revision(baseline_html)
        (output / 'revision.html').write_text(revised_html, encoding='utf-8')
        report['revision'] = {'old_clause': OLD, 'new_clause': NEW,
                              'removed_section': 'Section 8 - Authority and Associated Information',
                              'html_sha256': digest(revised_html)}

        def process(html, filename):
            def response(url, **kwargs):
                r = requests.Response()
                r.status_code = 200
                r.url = url
                r.encoding = 'utf-8'
                if url == source['files']['baseline.html']['url']:
                    r._content = html.encode('utf-8')
                elif url == source['files']['status.html']['url']:
                    r._content = status_html.encode('utf-8')
                else:
                    raise AssertionError(f'Unexpected HTTP request: {url}')
                return r
            with patch('ingestion.policy_processor.requests.get', side_effect=response):
                return process_policy('216', source['files']['baseline.html']['url'],
                                      str(output / filename), document_type='Policy',
                                      discovery_source_url='https://policies.latrobe.edu.au/browse')

        baseline = process(baseline_html, 'baseline.json')
        revised = process(revised_html, 'revised.json')
        check('baseline status is Current', baseline['status'] == 'Current')
        old_chunks, new_chunks = chunk_policy(baseline), chunk_policy(revised)
        save(output / 'baseline_chunks.json', old_chunks)
        save(output / 'revised_chunks.json', new_chunks)
        check('revision changes content hash', digest(baseline['content']) != digest(revised['content']))
        check('revision has fewer chunks', 0 < len(new_chunks) < len(old_chunks))
        check('changed clause reaches chunker output', any(NEW in c['text'] for c in new_chunks))
        check('old clause absent from revised chunks', all(OLD not in c['text'] for c in new_chunks))
        report['baseline'] = {'chunk_count': len(old_chunks), 'content_sha256': digest(baseline['content']),
                              'status': baseline['status'], 'version': baseline['version']}
        report['revised'] = {'chunk_count': len(new_chunks), 'content_sha256': digest(revised['content'])}
        if not controls_only:
            report['packages'].update({p: version(p) for p in ['sentence-transformers', 'torch', 'transformers']})

        with tempfile.TemporaryDirectory(prefix='lex-s5-06-') as tmp, ExitStack() as stack:
            client = QdrantClient(path=tmp)
            stack.callback(lambda: client.close())
            stack.enter_context(patch.object(indexer, 'get_client', return_value=client))
            stack.enter_context(patch.object(indexer, 'record_config',
                                           return_value=output / 'result.json'))
            fixed = [1.0] + [0.0] * 1023
            if controls_only:
                stack.enter_context(patch.object(indexer, 'embed_texts',
                    side_effect=lambda texts, **kw: [[1.0, 0.2] + [0.0] * 1022
                        if OLD in text or NEW in text else [0.0, 1.0] + [0.0] * 1022
                        for text in texts]))
            query_embedder = (lambda question: fixed[:]) if controls_only else embed_text

            def index(filename, replace=False):
                args = ['qdrant_indexer', '--file', str(output / filename)]
                if replace:
                    args += ['--replace-document', '216']
                with patch('sys.argv', args):
                    indexer.main()

            def records():
                items, offset = client.scroll(indexer.QDRANT_COLLECTION_NAME, limit=1000,
                                               with_payload=True, with_vectors=True)
                check('all test points inspected without pagination', offset is None)
                return items

            def retrieve(label):
                # New instance mirrors documented backend restart/catalogue refresh.
                result = PolicyRetriever(client=client, embedder=query_embedder).retrieve(QUESTION)
                report[label] = result
                return result

            index('baseline_chunks.json')
            initial = records()
            result = retrieve('baseline_retrieval')
            check('baseline feedback clause retrieved', any(OLD in e['policy_text'] for e in result['evidence']))

            # A distinct document checks that --replace-document does not delete neighbours.
            sentinel = deepcopy(initial[0])
            sentinel_id = indexer.chunk_point_id('s5-06-control-1')
            sentinel_payload = {**sentinel.payload, 'document_id': 's5-06-control',
                                'chunk_id': 's5-06-control-1', 'policy_title': 'S5-06 Control Fixture'}
            client.upsert(indexer.QDRANT_COLLECTION_NAME, [qm.PointStruct(
                id=sentinel_id, vector=sentinel.vector, payload=sentinel_payload)])
            index('revised_chunks.json', replace=True)
            updated = records()
            target = [r for r in updated if r.payload['document_id'] == '216']
            expected = {indexer.chunk_point_id(c['chunk_id']): c['text'] for c in new_chunks}
            check('stored replacement exactly matches revised chunk IDs and text',
                  {str(r.id): r.payload['text'] for r in target} == expected)
            removed_ids = {str(r.id) for r in initial} - set(expected)
            check('obsolete orphan IDs removed', bool(removed_ids) and
                  removed_ids.isdisjoint({str(r.id) for r in updated}))
            check('other document preserved', any(str(r.id) == sentinel_id and
                  r.payload == sentinel_payload and r.vector == sentinel.vector for r in updated))
            result = retrieve('revised_retrieval')
            check('revised feedback clause retrieved', any(NEW in e['policy_text'] for e in result['evidence']))
            check('old feedback clause excluded', all(OLD not in e['policy_text'] for e in result['evidence']))
            check('returned revised evidence is Current', all(e['status'] == 'Current' for e in result['evidence']))
            check('authoritative URL retained', all(e['source_url'] == baseline['source_url'] for e in result['evidence']))

            index('revised_chunks.json', replace=True)
            repeated = records()
            check('repeated replacement creates no duplicates or payload drift',
                  {str(r.id): r.payload for r in repeated} == {str(r.id): r.payload for r in updated})
            index('revised_chunks.json')
            check('plain rerun of unchanged revision is idempotent',
                  {str(r.id): r.payload for r in records()} == {str(r.id): r.payload for r in updated})

            # Deliberately inject obsolete records with the exact query vector. They
            # would rank first without the status filter, independently of semantics.
            obsolete_ids = []
            qvector = query_embedder(QUESTION)
            old_feedback = next(c for c in old_chunks if OLD in c['text'])
            for status in ['Superseded', 'Archived', None]:
                obsolete_id = indexer.chunk_point_id(f's5-06-obsolete-{status}')
                obsolete_ids.append(obsolete_id)
                client.upsert(indexer.QDRANT_COLLECTION_NAME, [qm.PointStruct(
                    id=obsolete_id, vector=qvector,
                    payload={**old_feedback, 'chunk_id': f's5-06-obsolete-{status}', 'status': status})])
            raw = client.query_points(indexer.QDRANT_COLLECTION_NAME, query=qvector,
                                      limit=3, with_payload=True).points
            check('unfiltered query exposes obsolete competition',
                  set(obsolete_ids).issubset({str(p.id) for p in raw}))
            result = retrieve('obsolete_competition_retrieval')
            check('all obsolete statuses excluded from retrieval candidates',
                  set(obsolete_ids).isdisjoint({c['point_id'] for c in result['_trace']['candidates']}))
            check('revised clause still retrievable with obsolete competitors',
                  any(NEW in e['policy_text'] for e in result['evidence']))
            report['obsolete_probe'] = {'ids': obsolete_ids,
                'unfiltered': [{'id': str(p.id), 'status': p.payload['status'], 'score': p.score} for p in raw]}

            client.close()
            client = QdrantClient(path=tmp)
            result = retrieve('reopened_retrieval')
            check('revision and currency controls survive reopening storage',
                  any(NEW in e['policy_text'] for e in result['evidence']) and
                  all(e['status'] == 'Current' and OLD not in e['policy_text'] for e in result['evidence']))
            report['counts'] = {'baseline': len(initial), 'after_replacement_with_control': len(updated),
                                'after_repeat_with_control': len(repeated), 'removed_orphan_ids': sorted(removed_ids)}
        report['outcome'] = 'PASS_CONTROLS_ONLY' if controls_only else 'PASS'
    except Exception as error:
        report['outcome'] = 'FAIL'
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(output / 'result.json', report)
    print(f"S5-06 {report['outcome']}: {len(report['checks'])} checks. Evidence: {output / 'result.json'}")
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory')
    parser.add_argument('--controls-only', action='store_true', help='Fixed vectors, not BGE-M3 validation')
    args = parser.parse_args()
    run(args.output, args.controls_only)
