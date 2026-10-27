# LoopLab · Agent Retry Observer

[English](README.md) · **简体中文**

一个本地运行的 Agent 重试观察面板，把每次纠正转化为有实际验证证据的工程改进。

LoopLab 将 **执行 → 失败 → 重试 → 结果 → 纠正 → 验证** 串起来：既能检查执行中发生了什么，也能记录哪些代码或检查能够防止同类错误继续传播。

使用 Python 标准库和原生 HTML / CSS / JavaScript。需要 Python 3.10+，无需第三方依赖、API Key 或前端构建。当前面板为简体中文。

<!-- 截图添加后取消下方注释：
![LoopLab 面板](docs/screenshots/overview.png)
-->

## 为什么做这个项目

Agent 说“修好了”不能代替验证，记录一句“记得加超时”也不会自动形成约束。

LoopLab 提供两个模块：

- **重试追踪**：查看已接入观测的步骤、每次尝试、错误、耗时和最终状态。
- **工程记忆**：记录现象、根因、防复发层、关联代码与实际验证证据。

目标是持续改进 Agent 工作的工程环境。笔记能保存经验，代码结构和自动检查才能让经验真正生效。

## 快速开始

在项目根目录打开终端：

```bash
python server.py
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)，再在第二个终端运行：

```bash
python demo.py
```

演示会实际执行异步函数，前两次主动抛出**模拟的限流错误**，第三次成功，并向本地服务发送真实事件。记录带有 `DEMO` 标识，不代表生产业务证据。追踪页面每 4 秒刷新一次。

## 接入自己的调用

仅对适合安全重试的操作使用包装器：

```python
from agent_observer import AgentTracer, observed_retry

tracer = AgentTracer("my-workflow").start()
try:
    result = observed_retry(
        call_tool,  # 你的可调用函数，需在此之前定义。
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

异步调用使用 `observed_retry_async`。这些包装器会真的执行重试，需要明确可重试异常、间隔以及操作的幂等性。

如果框架已有重试策略，请在现有的每次尝试前后接入事件，避免增加第二层重试：

```python
tracer = AgentTracer("existing-workflow").start()
tracer.emit("step_started", step="tool:search")
tracer.emit("attempt_started", step="tool:search", attempt=1)
# 在这里执行现有调用，再根据实际结果发送：
# attempt_failed / attempt_succeeded，最后发送 step_finished。
# 结束时调用 tracer.finish("succeeded") 或 tracer.finish("failed")。
```

## 工程记忆

打开面板中的 **工程记忆**，可以新增、编辑、搜索、筛选记录，以及复制 Markdown。每条记忆包含：

- 具体问题和根因。
- 防复发层：Codebase、Static Analysis、Rules / BugBot、Skills 或 Style Guide。
- 实际实现的约束、关联代码与验证证据。
- 待验证或已验证状态。

后端会拒绝将空证据的新建或编辑记录标为“已验证”。**证据非空不等于证据真实**：LoopLab 不会自动执行记录中填写的命令，也不会自动迁移历史记录。

## 从纠正走向工程约束

项目受到 [@poteto 分享的原视频](https://x.com/poteto/status/2102050467505430555) 启发。核心是按下面的顺序思考改进：

| 层次 | 主要作用 |
| --- | --- |
| **1. Codebase** | 用更安全的 API、数据结构与模块边界，让正确路径更容易被采用。 |
| **2. Static Analysis** | 用 lint、编译器与依赖检查落实可机械识别的约束；CI 可以负责运行这些检查。 |
| **3. Rules / BugBot** | 通过行为指导与自动审查辅助语义判断，但执行与覆盖并不绝对可靠。 |
| **4. Skills** | 沉淀可重复流程、应用控制工具与功能地图，支持实际验证。 |
| **5. Style Guide** | 保存设计约定；如果仅靠人工记忆和审查落实，约束较弱。 |

这是选择有效改进的优先级，不是要求每个任务都新增五层配置。运行时测试可以补充静态分析，但两者不能混为一谈。

详见 [视频总结](docs/video-notes.md) 和 [功能地图](docs/feature-map.md)。LoopLab 是基于视频思想的独立实验，不是演讲者的原版实现，也不代表官方关联。本仓库以本地应用的形式发布，不再作为可安装的 Agent skill 分发。

## 验证

在根目录运行单元测试：

```bash
python -X utf8 -m unittest discover -s tests -v
```

HTTP 验证需要使用独立数据目录启动另一份实例。PowerShell 示例：

```powershell
# 终端 A，项目根目录
$env:OBSERVER_DATA_DIR = Join-Path (Get-Location).Path '.local/verification-data'
$env:OBSERVER_PORT = '8766'
python -X utf8 server.py

# 终端 B，项目根目录
python -X utf8 scripts/verify_memory_evidence.py --url http://127.0.0.1:8766 --output .local/verification/http.json
```

macOS / Linux 的独立实例启动命令：

```bash
OBSERVER_DATA_DIR=.local/verification-data OBSERVER_PORT=8766 python server.py
```

HTTP 检查会创建验收专用记忆，验证六项契约，并保存真实响应与追踪。请使用专用实例，不要指向保存日常笔记的目录。详见 [验证方法与实测结果](docs/verification.md)。

## 目录

```text
.
├── server.py                       # 本地 HTTP 接口与静态页面服务
├── demo.py                         # 明确标记的模拟重试场景
├── agent_observer/                 # Tracer 与同步 / 异步重试包装器
├── static/                         # 面板 HTML、CSS、JavaScript
├── scripts/verify_memory_evidence.py
├── tests/test_core.py
├── examples/                       # 假设性、待验证的记忆示例
├── docs/
│   ├── video-notes.md
│   ├── feature-map.md
│   ├── verification.md
│   └── screenshots/                # 可在此补充截图
├── README.md
└── README.zh-CN.md
```

运行后默认将追踪与记忆写入 `data/`。通过 `OBSERVER_DATA_DIR` 隔离不同项目，通过 `OBSERVER_PORT` 更改端口；相对数据路径从当前工作目录解析。`.gitignore` 默认排除 `data/`、`.local/`、`work/` 和本地环境文件。如需版本管理某条记忆，请先检查内容，再导出到明确用于共享的位置。

## 能力边界

- 只能观察显式接入事件的调用，不能自动捕获 Codex、Claude 或其他框架隐藏的内部重试。
- 当前没有完整主 / 子 Agent 树、逐行代码归属或自动影响分析。
- 服务仅监听 `127.0.0.1`，没有身份认证，应保持本地使用。
- 事件发送采用短超时，并忽略发送错误，不属于完整、防篡改的审计日志。
- 不要将密钥、完整 Prompt 和业务隐私放入事件或共享导出内容。
- 执行可见不代表功能、性能和代码质量已经验证，需要对应的检查证据。

截图可放入 `docs/screenshots/`；添加 `overview.png` 后，取消本文开头图片块的注释即可展示。
