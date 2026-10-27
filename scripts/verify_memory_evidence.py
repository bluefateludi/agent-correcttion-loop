"""Exercise the running LoopLab API; records real requests, not simulated retries.

Use a dedicated OBSERVER_DATA_DIR: this creates acceptance-test memory fixtures.
Only accepts loopback URLs. A nonzero exit means at least one contract failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_observer import AgentTracer, observed_retry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8766')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    address = urlparse(args.url)
    if address.scheme != 'http' or address.hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Use a local HTTP observer')
    base = args.url.rstrip('/')
    tracer = AgentTracer('Memory evidence contract', url=base, source='acceptance-test').start()
    records = []

    def request(method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        req = Request(base + path, data=data, method=method,
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode('utf-8'))

    def check(name, method, path, payload, expected, predicate=None):
        code, body = request(method, path, payload)
        passed = code == expected and (predicate is None or predicate(body))
        row = {'case': name, 'method': method, 'path': path, 'request': payload,
               'expected_status': expected, 'actual_status': code, 'response': body, 'passed': passed}
        records.append(row)

        def assert_contract():
            if not passed:
                raise AssertionError(f'{name}: expected HTTP {expected}, got {code}')
        try:
            # One attempt only: these writes must not be automatically retried.
            observed_retry(assert_contract, tracer, name, max_attempts=1, retryable=())
        except AssertionError:
            pass
        return body

    fixture = {'title': 'ACCEPTANCE TEST: memory evidence', 'project': 'LoopLab acceptance tests',
               'layer': 'Codebase', 'status': 'verified', 'verification': ''}
    try:
        check('reject-empty-evidence', 'POST', '/api/memories', fixture, 400)
        check('reject-whitespace-evidence', 'POST', '/api/memories',
              {**fixture, 'verification': ' \n\t '}, 400)
        draft = check('allow-unverified-draft', 'POST', '/api/memories',
                      {**fixture, 'status': 'unverified'}, 201,
                      lambda body: body['status'] == 'unverified')
        evidence = ('Acceptance fixture, not a claim of business verification: '
                    f'POST /api/memories returned 201 with status=unverified; id={draft["id"]}.')
        saved = check('allow-evidence-backed-update', 'PUT', '/api/memories/' + draft['id'],
                      {**fixture, 'verification': evidence}, 200,
                      lambda body: body['verification'] == evidence and body['status'] == 'verified')
        check('reject-clearing-verified-evidence', 'PUT', '/api/memories/' + saved['id'], fixture, 400)
        check('failed-update-preserves-record', 'GET', '/api/memories', None, 200,
              lambda body: any(m['id'] == saved['id'] and m['verification'] == evidence
                               and m['status'] == 'verified' for m in body['memories']))
    finally:
        passed = bool(records) and len(records) == 6 and all(r['passed'] for r in records)
        tracer.finish('succeeded' if passed else 'failed')
        trace_code, trace = request('GET', '/api/runs/' + tracer.run_id)
        if trace_code != 200 or len(trace.get('events', [])) != 26:
            passed = False
        server_file = Path(__file__).resolve().parents[1] / 'server.py'
        result = {'recorded_at': datetime.now(timezone.utc).isoformat(),
                  'source': 'real local HTTP acceptance checks, not agent-internal telemetry',
                  'server_file_sha256': hashlib.sha256(server_file.read_bytes()).hexdigest(),
                  'run_id': tracer.run_id, 'passed': passed, 'checks': records, 'trace': trace}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'run_id': tracer.run_id, 'passed': passed,
                          'cases_passed': sum(r['passed'] for r in records), 'cases': len(records),
                          'trace_events': len(trace.get('events', [])), 'output': str(args.output)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
