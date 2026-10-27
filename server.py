"""Retry Observer: localhost-only event ingestion, timeline viewer and repo memory.

Run: python server.py
All dependencies are in the Python standard library.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('OBSERVER_DATA_DIR', str(ROOT / 'data'))).resolve()
DB = DATA / 'traces.sqlite3'
MEMORY = DATA / 'memory'
LOCK = threading.RLock()
EVENT_KINDS = {'run_started','step_started','attempt_started','attempt_failed','attempt_succeeded','step_finished','run_finished'}
STATUSES = {'running','succeeded','failed','cancelled'}
LAYERS = {'Codebase','Static Analysis','Rules / BugBot','Skills','Style Guide'}


def init():
    DATA.mkdir(parents=True, exist_ok=True)
    MEMORY.mkdir(parents=True, exist_ok=True)
    with dbconnect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
            status TEXT NOT NULL, started REAL, updated REAL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            ts REAL NOT NULL, kind TEXT NOT NULL, step TEXT NOT NULL,
            attempt INTEGER NOT NULL, note TEXT NOT NULL,
            duration_ms INTEGER, status TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq)')


@contextmanager
def dbconnect():
    db = sqlite3.connect(DB, timeout=4)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def safe_text(value, limit=200):
    return str(value or '')[:limit]


def insert_event(event):
    kind = event.get('kind')
    if kind not in EVENT_KINDS:
        raise ValueError('Invalid event kind')
    run_id = safe_text(event.get('run_id'), 80)
    if not run_id:
        raise ValueError('run_id required')
    raw_attempt = event.get('attempt', 0)
    if isinstance(raw_attempt, bool):
        raise ValueError('Invalid attempt')
    attempt = int(raw_attempt)
    if attempt < 0 or attempt > 500:
        raise ValueError('Invalid attempt')
    ts = float(event.get('ts') or time.time())
    if abs(ts-time.time()) > 86400 * 365:
        raise ValueError('Invalid timestamp')
    source = safe_text(event.get('source') or 'instrumented', 40)
    name = safe_text(event.get('run_name') or 'Untitled agent', 100)
    status = safe_text(event.get('status'), 30)
    if status and status not in STATUSES:
        raise ValueError('Invalid status')
    ms = event.get('duration_ms')
    if ms is not None:
        ms = int(ms)
        if not 0 <= ms <= 3600000:
            raise ValueError('Invalid duration')
    with LOCK, dbconnect() as db:
        db.execute('''INSERT OR IGNORE INTO runs(id,name,source,status,started,updated)
                      VALUES(?,?,?,?,?,?)''', (run_id,name,source,'running',ts,ts))
        if kind == 'run_started':
            db.execute("UPDATE runs SET status='running',updated=? WHERE id=?",(ts,run_id))
        elif kind == 'run_finished':
            db.execute('UPDATE runs SET status=?,updated=? WHERE id=?', (status or 'succeeded',ts,run_id))
        else:
            db.execute('UPDATE runs SET updated=? WHERE id=?', (ts,run_id))
        db.execute('''INSERT INTO events(run_id,ts,kind,step,attempt,note,duration_ms,status)
                      VALUES (?,?,?,?,?,?,?,?)''', (run_id,ts,kind,safe_text(event.get('step'),120),attempt,
                                                    safe_text(event.get('note'),500),ms,status))


def list_runs():
    with dbconnect() as db:
        rows = db.execute('''SELECT r.*, COUNT(e.seq) AS event_count,
          SUM(CASE WHEN e.kind='attempt_failed' THEN 1 ELSE 0 END) AS failures,
          SUM(CASE WHEN e.kind='attempt_started' THEN 1 ELSE 0 END) AS attempts
          FROM runs r LEFT JOIN events e ON e.run_id=r.id
          GROUP BY r.id ORDER BY r.updated DESC LIMIT 120''').fetchall()
    return [dict(row) for row in rows]


def get_run(run_id):
    with dbconnect() as db:
        row=db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            return None
        events=db.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq LIMIT 1000',(run_id,)).fetchall()
    return {'run':dict(row),'events':[dict(e) for e in events]}


def list_memories():
    entries=[]
    for p in MEMORY.glob('*.json'):
        try:
            d=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(d,dict) and 'id' in d:
                entries.append(d)
        except (OSError,json.JSONDecodeError):
            continue
    return sorted(entries,key=lambda x:x.get('updated_at',''),reverse=True)


def create_memory(raw, memory_id=None):
    if not isinstance(raw,dict):
        raise ValueError('Expected object')
    title=safe_text(raw.get('title'),120).strip()
    if not title:
        raise ValueError('Title required')
    layer=safe_text(raw.get('layer'),60)
    if layer not in LAYERS:
        raise ValueError('Invalid layer')
    verification=safe_text(raw.get('verification'),3000).strip()
    status='verified' if raw.get('status')=='verified' else 'unverified'
    if status == 'verified' and not verification:
        raise ValueError('标记已验证前必须填写验证证据；未执行检查请保留待验证。')
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    if memory_id is None:
        memory_id=uuid.uuid4().hex[:12]
        created=now
    else:
        if not memory_id.isalnum() or len(memory_id)>32:
            raise ValueError('Invalid id')
        old=MEMORY/(memory_id+'.json')
        if not old.exists():
            raise FileNotFoundError(memory_id)
        try:
            created=json.loads(old.read_text(encoding='utf-8')).get('created_at',now)
        except json.JSONDecodeError:
            created=now
    d={'id':memory_id,'title':title,'project':safe_text(raw.get('project'),100),
       'layer':layer,'symptom':safe_text(raw.get('symptom'),3000),
       'root_cause':safe_text(raw.get('root_cause'),3000),
       'enforcement':safe_text(raw.get('enforcement'),3000),
       'code_path':safe_text(raw.get('code_path'),350),
       'verification':verification,
       'status':status,
       'created_at':created,'updated_at':now}
    path=MEMORY/(memory_id+'.json')
    temp=MEMORY/(memory_id+'.tmp')
    with LOCK:
        temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(temp,path)
    return d


def to_markdown(d):
    def clean(v):
        return str(v or '').replace('\r','').strip()
    return ('# '+clean(d['title'])+'\n\n'
            + '- 项目：'+clean(d['project'])+'\n'
            + '- 约束层：'+clean(d['layer'])+'\n'
            + '- 状态：'+('已验证' if d['status']=='verified' else '待验证')+'\n'
            + '- 关联代码/测试：`'+clean(d['code_path']).replace('`','')+'`\n\n'
            + '## 问题现象\n'+clean(d['symptom'])+'\n\n'
            + '## 根因\n'+clean(d['root_cause'])+'\n\n'
            + '## 防复发约束\n'+clean(d['enforcement'])+'\n\n'
            + '## 实际验证证据\n'+clean(d['verification'])+'\n')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def reply(self, code, payload, content_type='application/json; charset=utf-8'):
        body=(json.dumps(payload,ensure_ascii=False).encode('utf-8') if not isinstance(payload,bytes) else payload)
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def data(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
        except ValueError:
            raise ValueError('Content-Length invalid')
        if size<1 or size>65536:
            raise ValueError('Body must be between 1 and 65536 bytes')
        return json.loads(self.rfile.read(size))

    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=='/':
                self.reply(200,(ROOT/'static/index.html').read_bytes(),'text/html; charset=utf-8')
            elif path=='/static/app.js':
                self.reply(200,(ROOT/'static/app.js').read_bytes(),'text/javascript; charset=utf-8')
            elif path=='/static/style.css':
                self.reply(200,(ROOT/'static/style.css').read_bytes(),'text/css; charset=utf-8')
            elif path=='/api/runs':
                self.reply(200,{'runs':list_runs()})
            elif path.startswith('/api/runs/'):
                result=get_run(path[len('/api/runs/'):]); self.reply(200,result) if result else self.reply(404,{'error':'Run not found'})
            elif path=='/api/memories':
                self.reply(200,{'memories':list_memories()})
            elif path.startswith('/api/memories/') and path.endswith('/markdown'):
                mid=path.split('/')[-2]
                found=next((m for m in list_memories() if m['id']==mid),None)
                if not found: return self.reply(404,{'error':'Memory not found'})
                self.reply(200,to_markdown(found).encode('utf-8'),'text/markdown; charset=utf-8')
            else:
                self.reply(404,{'error':'Not found'})
        except Exception as exc:
            self.reply(500,{'error':type(exc).__name__})

    def do_POST(self):
        path=urlparse(self.path).path
        try:
            body=self.data()
            if path=='/api/events':
                insert_event(body)
                return self.reply(201,{'ok':True})
            if path=='/api/memories':
                return self.reply(201,create_memory(body))
            self.reply(404,{'error':'Not found'})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            self.reply(400,{'error':str(exc)[:180]})
        except Exception as exc:
            self.reply(500,{'error':type(exc).__name__})

    def do_PUT(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/memories/'):
            return self.reply(404,{'error':'Not found'})
        try:
            item=create_memory(self.data(),memory_id=path.split('/')[-1]); self.reply(200,item)
        except FileNotFoundError:
            self.reply(404,{'error':'Memory not found'})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            self.reply(400,{'error':str(exc)[:180]})

    def do_DELETE(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/memories/'):
            return self.reply(404,{'error':'Not found'})
        mid=path.split('/')[-1]
        if not mid.isalnum() or len(mid)>32:
            return self.reply(400,{'error':'Invalid id'})
        target=MEMORY/(mid+'.json')
        try:
            target.unlink()
            self.reply(200,{'ok':True})
        except FileNotFoundError:
            self.reply(404,{'error':'Memory not found'})


def main():
    init()
    port=int(os.environ.get('OBSERVER_PORT',8765))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Retry Observer running at http://127.0.0.1:{port}',flush=True)
    print('Memory location:',MEMORY,flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
