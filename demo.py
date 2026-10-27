"""Run a deterministic REAL retry workflow and emit observed events."""
import asyncio
import time
from agent_observer import AgentTracer, observed_retry_async


class RateLimited(Exception):
    pass


async def main():
    tracer=AgentTracer('LoopLab · Example workflow (DEMO)',source='demo')
    tracer.start()
    print('Demo run id:',tracer.run_id)
    try:
        async def plan():
            await asyncio.sleep(.09)
            return {'outline':'3 slides'}
        await observed_retry_async(plan,tracer,'01 / Create outline',max_attempts=1)
        attempts=0
        async def tool():
            nonlocal attempts
            attempts+=1
            await asyncio.sleep(.15)
            if attempts<=2:
                raise RateLimited('Simulated 429 (safe synthetic error)')
            return 'ok'
        await observed_retry_async(tool,tracer,'02 / Render slides',max_attempts=3,delay_s=.12,retryable=(RateLimited,))
        async def quality_check():
            await asyncio.sleep(.08)
            return True
        await observed_retry_async(quality_check,tracer,'03 / Verify output',max_attempts=1)
    except Exception:
        tracer.finish('failed')
        raise
    else:
        tracer.finish('succeeded')
        print('Open http://127.0.0.1:8765 to see attempts and recovery.')


if __name__=='__main__':
    asyncio.run(main())
