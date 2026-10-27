# agent-correcttion-loop

**LoopLab · Agent Retry Observer**

[English](README.md) · **简体中文**

一个让 Agent 重试过程可见的本地面板，将每次纠正转化为有验证证据的工程改进。

![LoopLab 重试追踪面板](docs/screenshots/retry-trace.png)

*演示流程：两次模拟失败后重试成功。面板显示实际记录的本地事件，不代表生产业务流量。*

## 能做什么

- **观察重试**：查看执行步骤、每次尝试、错误、耗时和最终结果。
- **沉淀工程经验**：关联问题、根因、代码改动、防复发机制和验证证据。
- **形成纠错闭环**：执行 → 失败 → 纠正 → 工程约束 → 验证。

## 本地启动

需要 **Python 3.10+**。下载或克隆仓库，在项目根目录打开终端，运行：

```bash
python server.py
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。无需第三方依赖、API Key 或前端构建。

如需查看演示数据，在第二个终端运行 `python demo.py`。限流错误由演示主动模拟，记录带有 **DEMO** 标识。当前界面为简体中文。

## 工程记忆

在一条记录中串起 **问题 → 根因 → 防复发层 → 代码 → 验证证据**，支持编辑、搜索、筛选和复制 Markdown。

![包含两条已验证纠错记录的工程记忆面板](docs/screenshots/engineering-memory.png)

后端拒绝把空证据记录标为“已验证”。非空文本仍需核实真实性；保存一条笔记，也不代表代码约束已经落实。

## 项目背后的思路

受到 [@poteto 分享的原视频](https://x.com/poteto/status/2102050467505430555) 启发：每次纠正 Agent 时，按下面的顺序考虑如何改进环境。

| 优先级 | 关注点 |
| --- | --- |
| **1. Codebase** | 用安全的 API、数据结构和边界，让正确路径更容易走。 |
| **2. Static Analysis** | 通过 lint、编译器和依赖检查落实可机械识别的约束。 |
| **3. Rules / BugBot** | 补充行为指导与自动审查。 |
| **4. Skills** | 让应用控制和验证流程可重复执行。 |
| **5. Style Guide** | 保存团队约定，避免仅靠审查者的记忆。 |

LoopLab 是基于这些思想的独立实践，不是演讲者的原版产品，也不代表官方关联。详见[视频总结](docs/video-notes.md)。

## 一次实际纠错

本地实践发现：没有验证证据的记忆也能被标为已验证。将校验放到后端共享入口后，新建和编辑都受到约束；同一套 HTTP 检查从 **2/6 提升到 6/6**，扩展后的单元测试 **9/9 通过**。具体范围与局限见[验证说明](docs/verification.md)。

<details>
<summary>查看面板内的接入指南</summary>

![LoopLab 接入指南](docs/screenshots/integration-guide.png)

</details>

## 更多说明与能力边界

- [功能地图](docs/feature-map.md) · [验证说明](docs/verification.md) · [视频总结](docs/video-notes.md)
- 只能观察显式接入事件的调用，不能自动捕获隐藏重试、完整 Agent 树或逐行代码归属。
- 服务仅供本地使用，没有身份认证；不要把密钥或业务隐私写入记录与共享导出。
- 看见 trace 不等于功能或性能已验证。事件发送错误可能被忽略，因此不是完整审计日志。
- 运行数据默认保存在 `data/`，不上传 Git；可用 `OBSERVER_DATA_DIR` 和 `OBSERVER_PORT` 配置目录与端口。
