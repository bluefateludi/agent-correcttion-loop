import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_observer import AgentTracer, observed_retry, observed_retry_async
import server


class RetryTests(unittest.TestCase):
    def test_two_failed_attempts_then_success(self):
        ev=[]
        t=AgentTracer('test',sender=lambda e:ev.append(e))
        x={'n':0}
        def fn():
            x['n']+=1
            if x['n']<=2: raise TimeoutError('synthetic')
            return 'ok'
        self.assertEqual(observed_retry(fn,t,'call',max_attempts=3,retryable=(TimeoutError,)),'ok')
        self.assertEqual([e['kind'] for e in ev].count('attempt_failed'),2)
        self.assertEqual([e['kind'] for e in ev].count('attempt_succeeded'),1)
        self.assertEqual(ev[-1]['status'],'succeeded')

    def test_no_retry_for_unlisted_error(self):
        ev=[]
        t=AgentTracer('test',sender=lambda e:ev.append(e))
        def fn(): raise ValueError('not retryable')
        with self.assertRaises(ValueError):
            observed_retry(fn,t,'call',max_attempts=3,retryable=(TimeoutError,))
        self.assertEqual([e['kind'] for e in ev].count('attempt_started'),1)

    def test_async_retries(self):
        ev=[]
        t=AgentTracer('async',sender=lambda e:ev.append(e))
        async def work():
            if len([e for e in ev if e['kind']=='attempt_started'])==1:
                raise TimeoutError('retry')
            return 42
        self.assertEqual(asyncio.run(observed_retry_async(work,t,'step',max_attempts=2,retryable=(TimeoutError,))),42)
        self.assertEqual([e['kind'] for e in ev].count('attempt_failed'),1)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=Path(self.tmp.name)
        self._old=(server.DATA,server.MEMORY,server.DB)
        server.DATA=self.p
        server.MEMORY=self.p/'memory'
        server.DB=self.p/'traces.sqlite3'
        server.init()

    def tearDown(self):
        server.DATA,server.MEMORY,server.DB=self._old
        self.tmp.cleanup()

    def test_event_storage(self):
        base={'run_id':'abc','run_name':'test','source':'instrumented','ts':1730000000}
        # Timestamp validation rejects artificially old timestamps; use current.
        import time
        base['ts']=time.time()
        server.insert_event({**base,'kind':'run_started'})
        server.insert_event({**base,'kind':'step_started','step':'tool'})
        server.insert_event({**base,'kind':'attempt_started','step':'tool','attempt':1})
        server.insert_event({**base,'kind':'attempt_failed','step':'tool','attempt':1,'note':'429'})
        server.insert_event({**base,'kind':'run_finished','status':'failed'})
        record=server.get_run('abc')
        self.assertEqual(record['run']['status'],'failed')
        self.assertEqual(len(record['events']),5)
        self.assertEqual(server.list_runs()[0]['failures'],1)

    def test_memory_roundtrip(self):
        m=server.create_memory({'title':'test','project':'SlideForge','layer':'Codebase','symptom':'oops','status':'unverified'})
        self.assertEqual(server.list_memories()[0]['title'],'test')
        self.assertTrue((server.MEMORY/(m['id']+'.json')).is_file())
        self.assertIn('待验证',server.to_markdown(m))
        edited=server.create_memory({**m,'title':'updated','status':'verified',
                                     'verification':'Fixture: memory file and draft roundtrip assertions passed.'},memory_id=m['id'])
        self.assertEqual(edited['title'],'updated')
        self.assertEqual(server.list_memories()[0]['status'],'verified')

    def test_reject_invalid(self):
        with self.assertRaises(ValueError):
            server.insert_event({'run_id':'x','kind':'invalid'})
        with self.assertRaises(ValueError):
            server.create_memory({'title':'hello','layer':'unknown'})

    def test_verified_memory_requires_evidence(self):
        for evidence in (None, '', ' \n\t '):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(ValueError, '验证证据'):
                    server.create_memory({'title':'missing evidence','layer':'Codebase',
                                          'status':'verified','verification':evidence})
        self.assertEqual(server.list_memories(), [])

    def test_failed_evidence_update_preserves_memory(self):
        memory=server.create_memory({'title':'verified fixture','layer':'Codebase',
                                    'status':'verified','verification':'Fixture evidence text'})
        with self.assertRaisesRegex(ValueError, '验证证据'):
            server.create_memory({**memory,'verification':'   '},memory_id=memory['id'])
        self.assertEqual(server.list_memories()[0], memory)

    def test_connection_context_closes_and_rolls_back(self):
        import sqlite3
        with server.dbconnect() as db:
            db.execute('SELECT 1')
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')
        with self.assertRaisesRegex(RuntimeError, 'rollback probe'):
            with server.dbconnect() as db:
                db.execute("INSERT INTO runs VALUES ('rollback','fixture','test','running',0,0)")
                raise RuntimeError('rollback probe')
        with server.dbconnect() as db:
            self.assertIsNone(db.execute("SELECT id FROM runs WHERE id='rollback'").fetchone())


if __name__=='__main__':
    unittest.main()
