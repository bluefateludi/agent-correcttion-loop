"""Push trace events to local Retry Observer. Keep business payloads out of logs.

This module does NOT hook/intercept hidden retries in third-party agents.
Integrate it explicitly around the calls or node logic that you own.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Awaitable, Callable, Optional, Tuple, TypeVar
from urllib.request import Request, urlopen

T = TypeVar('T')


class AgentTracer:
    def __init__(self, name: str, *, url: str = 'http://127.0.0.1:8765',
                 run_id: Optional[str] = None, sender: Optional[Callable[[dict], None]] = None,
                 source: str = 'instrumented'):
        self.name = name
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.url = url.rstrip('/')
        self.source = source
        self._sender = sender or self._http_send

    def _http_send(self, event: dict) -> None:
        request = Request(self.url + '/api/events', data=json.dumps(event).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=0.65):
            pass

    def emit(self, kind: str, *, step: str = '', attempt: int = 0,
             note: str = '', duration_ms: Optional[int] = None,
             status: str = '') -> None:
        event = {'run_id': self.run_id, 'run_name': self.name, 'source': self.source,
                 'kind': kind, 'step': step, 'attempt': attempt,
                 'note': (note or '')[:500], 'status': status,
                 'duration_ms': duration_ms,
                 'ts': time.time()}
        try:
            self._sender(event)
        except (OSError, ValueError):
            # Observation should not break the actual agent if the viewer is down.
            # For production, replace with a bounded queue and observable drop metrics.
            pass

    def start(self) -> 'AgentTracer':
        self.emit('run_started')
        return self

    def finish(self, status: str = 'succeeded') -> None:
        self.emit('run_finished', status=status)


def observed_retry(fn: Callable[[], T], tracer: AgentTracer, step: str, *,
                   max_attempts: int = 3, delay_s: float = 0.0,
                   retryable: Tuple[type[Exception], ...] = (Exception,)) -> T:
    """Explicit opt-in retry helper. For idempotent/retry-safe operations only."""
    if max_attempts < 1:
        raise ValueError('max_attempts must be >= 1')
    if delay_s < 0:
        raise ValueError('delay_s must be >= 0')
    tracer.emit('step_started', step=step)
    for attempt in range(1, max_attempts + 1):
        tracer.emit('attempt_started', step=step, attempt=attempt)
        start = time.perf_counter()
        try:
            result = fn()
        except retryable as exc:
            elapsed = round((time.perf_counter() - start) * 1000)
            tracer.emit('attempt_failed', step=step, attempt=attempt,
                        note=type(exc).__name__ + ': ' + str(exc)[:200], duration_ms=elapsed)
            if attempt == max_attempts:
                tracer.emit('step_finished', step=step, status='failed')
                raise
            if delay_s:
                time.sleep(delay_s)
        except Exception as exc:
            tracer.emit('attempt_failed', step=step, attempt=attempt,
                        note=type(exc).__name__, duration_ms=round((time.perf_counter()-start)*1000))
            tracer.emit('step_finished', step=step, status='failed')
            raise
        else:
            elapsed = round((time.perf_counter() - start) * 1000)
            tracer.emit('attempt_succeeded', step=step, attempt=attempt, duration_ms=elapsed)
            tracer.emit('step_finished', step=step, status='succeeded')
            return result
    raise AssertionError('unreachable')


async def observed_retry_async(fn: Callable[[], Awaitable[T]], tracer: AgentTracer, step: str, *,
                               max_attempts: int = 3, delay_s: float = 0.0,
                               retryable: Tuple[type[Exception], ...] = (Exception,)) -> T:
    """Async variant. Network tracing uses a thread to avoid blocking the event loop."""
    if max_attempts < 1:
        raise ValueError('max_attempts must be >= 1')
    if delay_s < 0:
        raise ValueError('delay_s must be >= 0')
    async def emit(kind: str, **kw: Any) -> None:
        await asyncio.to_thread(tracer.emit, kind, **kw)
    await emit('step_started', step=step)
    for attempt in range(1, max_attempts + 1):
        await emit('attempt_started', step=step, attempt=attempt)
        start = time.perf_counter()
        try:
            result = await fn()
        except retryable as exc:
            elapsed = round((time.perf_counter() - start) * 1000)
            await emit('attempt_failed', step=step, attempt=attempt,
                       note=type(exc).__name__ + ': ' + str(exc)[:200], duration_ms=elapsed)
            if attempt == max_attempts:
                await emit('step_finished', step=step, status='failed')
                raise
            if delay_s:
                await asyncio.sleep(delay_s)
        except Exception as exc:
            await emit('attempt_failed', step=step, attempt=attempt,
                       note=type(exc).__name__, duration_ms=round((time.perf_counter()-start)*1000))
            await emit('step_finished', step=step, status='failed')
            raise
        else:
            elapsed = round((time.perf_counter()-start)*1000)
            await emit('attempt_succeeded', step=step, attempt=attempt, duration_ms=elapsed)
            await emit('step_finished', step=step, status='succeeded')
            return result
    raise AssertionError('unreachable')
