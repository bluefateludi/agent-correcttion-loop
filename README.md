# LoopLab · Agent Retry Observer

**English** · [简体中文](README.zh-CN.md)

A local dashboard for observing instrumented agent retries and turning corrections into engineering improvements backed by evidence.

LoopLab connects **execution → failure → retry → outcome → correction → verification**. It helps you inspect what happened and record the code or checks that prevent the same mistake from spreading.

Built with Python's standard library and a plain HTML/CSS/JavaScript frontend. Python 3.10+; no third-party packages, API keys or frontend build step required. The dashboard interface is currently in Simplified Chinese.

<!-- Add your screenshot here when ready:
![LoopLab dashboard](docs/screenshots/overview.png)
-->

## Why this exists

An agent saying “fixed” is not verification. A note saying “add a timeout” does not enforce one.

LoopLab combines two tools:

- **Retry traces:** inspect instrumented steps, attempts, failures, timings and final status.
- **Engineering memory:** record the symptom, root cause, prevention layer, affected code and actual verification evidence.

The goal is to improve the environment in which agents work. Recording a lesson is useful; enforcing it through code and checks is what makes it durable.

## Quick start

Open a terminal in the repository root:

```bash
python server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), then run the demo in a second terminal:

```bash
python demo.py
```

The demo executes real asynchronous functions, deliberately raises two **simulated** rate-limit errors, then succeeds on the third attempt. It sends real events to the local server. Runs are labelled `DEMO`; they are not production evidence. The trace view polls every four seconds.

## Instrument your own calls

Use the retry helpers only for operations that are safe to retry:

```python
from agent_observer import AgentTracer, observed_retry

tracer = AgentTracer("my-workflow").start()
try:
    result = observed_retry(
        call_tool,  # Your callable; define it before this snippet.
        tracer,
        "tool:search",
        max_attempts=3,
        delay_s=0.3,
        retryable=(TimeoutError,),
    )
except Exception:
    tracer.finish("failed")
    raise
else:
    tracer.finish("succeeded")
```

`observed_retry_async` supports asynchronous callables. The helpers really retry: choose retryable exceptions, delays and idempotency requirements explicitly.

If your framework already manages retries, emit events at each existing attempt boundary instead of adding another retry loop:

```python
tracer = AgentTracer("existing-workflow").start()
tracer.emit("step_started", step="tool:search")
tracer.emit("attempt_started", step="tool:search", attempt=1)
# Execute the existing attempt, then emit its actual result:
# attempt_failed / attempt_succeeded, followed by step_finished.
# Finish the run with tracer.finish("succeeded") or tracer.finish("failed").
```

## Engineering memory

Open **工程记忆** in the dashboard to create, edit, search, filter or export a record as Markdown. Each record contains:

- The observed problem and root cause.
- A prevention layer: Codebase, Static Analysis, Rules / BugBot, Skills or Style Guide.
- The implemented constraint, related code and verification evidence.
- An unverified or verified status.

The backend rejects new or updated records marked verified when their evidence is empty. **Nonempty evidence is not proof that the evidence is true.** LoopLab does not independently run commands entered in a record, and existing records are not automatically migrated.

## From corrections to constraints

The project is inspired by [the source video shared by @poteto](https://x.com/poteto/status/2102050467505430555). The main idea is to consider improvements in this order:

| Layer | What it contributes |
| --- | --- |
| **1. Codebase** | Safer APIs, data structures and module boundaries make the correct path easy to follow. |
| **2. Static Analysis** | Lint, compiler and dependency checks make mechanically detectable constraints enforceable. CI can run these checks. |
| **3. Rules / BugBot** | Instructions and review automation guide semantic decisions, with imperfect enforcement. |
| **4. Skills** | Repeatable workflows, application controls and feature maps support verification. |
| **5. Style Guide** | Shared design conventions help reviewers, but are weak when they rely only on human memory. |

This is a priority for choosing the most effective improvement, not a requirement to add all five layers to every task. Runtime tests complement static analysis; they are not the same thing.

Read the [video notes](docs/video-notes.md) and [feature map](docs/feature-map.md). LoopLab is an independent experiment inspired by the video, not the speaker's original implementation or an official affiliated project. The repository is distributed as a local application, not an installable agent skill.

## Verification

Run the unit tests from the repository root:

```bash
python -X utf8 -m unittest discover -s tests -v
```

To exercise the HTTP contract, start a separate instance with a dedicated data directory. In PowerShell:

```powershell
# Terminal A, repository root
$env:OBSERVER_DATA_DIR = Join-Path (Get-Location).Path '.local/verification-data'
$env:OBSERVER_PORT = '8766'
python -X utf8 server.py

# Terminal B, repository root
python -X utf8 scripts/verify_memory_evidence.py --url http://127.0.0.1:8766 --output .local/verification/http.json
```

On macOS/Linux, start the isolated instance with:

```bash
OBSERVER_DATA_DIR=.local/verification-data OBSERVER_PORT=8766 python server.py
```

The HTTP checker creates acceptance-test records, verifies six contracts and saves the actual responses and trace. Use a dedicated instance, not a directory containing your normal notes. See [verification details and observed results](docs/verification.md).

## Repository layout

```text
.
├── server.py                       # Local HTTP API and static file server
├── demo.py                         # Explicitly simulated retry scenario
├── agent_observer/                 # Tracer and sync/async retry helpers
├── static/                         # Dashboard HTML, CSS and JavaScript
├── scripts/verify_memory_evidence.py
├── tests/test_core.py
├── examples/                       # Hypothetical, unverified memory example
├── docs/
│   ├── video-notes.md
│   ├── feature-map.md
│   ├── verification.md
│   └── screenshots/                # Add your screenshots here
├── README.md
└── README.zh-CN.md
```

Runtime traces and memories are written to `data/` by default. Set `OBSERVER_DATA_DIR` to separate projects and `OBSERVER_PORT` to change the port. Relative data paths resolve from your working directory. `data/`, `.local/`, `work/` and local environment files are excluded by `.gitignore`. If you want to version a memory, review and export it to a deliberately shared location first.

## Scope and limitations

- Only explicitly instrumented calls are visible. LoopLab does not automatically capture hidden Codex, Claude or third-party framework retries.
- Runs and events do not currently provide a full parent/child-agent tree, line-level code attribution or automatic impact analysis.
- The server binds to `127.0.0.1` and has no authentication. Keep it local.
- Event delivery uses a short timeout and ignores delivery errors. This is not a complete or tamper-evident audit log.
- Keep secrets, full prompts and private business data out of event notes and shared exports.
- Trace visibility does not establish business correctness, performance or code quality. Those need appropriate checks.

Screenshots can be added to `docs/screenshots/`; uncomment the image block near the top once `overview.png` is available.
