# Verification / 验证

## Repeatable checks / 可重复检查

From the repository root / 在仓库根目录：

```bash
python -X utf8 -m unittest discover -s tests -v
```

The suite covers sync/async retries, non-retryable errors, event storage, memory roundtrips, evidence validation, failed-update preservation, connection closure and transaction rollback.

单元测试覆盖同步 / 异步重试、不可重试错误、事件存储、记忆读写、证据约束、失败更新不破坏数据、连接关闭与事务回滚。

Start an isolated instance / 启动独立实例（PowerShell）：

```powershell
$env:OBSERVER_DATA_DIR = Join-Path (Get-Location).Path '.local/verification-data'
$env:OBSERVER_PORT = '8766'
python -X utf8 server.py
```

In a second terminal / 在第二个终端：

```bash
python -X utf8 scripts/verify_memory_evidence.py --url http://127.0.0.1:8766 --output .local/verification/http.json
```

The output contains real requests, responses, a trace run ID and the local server source-file hash. The hash identifies the file on disk, not an independently attested version of a remote process. Each check executes once; it does not automatically retry memory writes. Test records are labelled ACCEPTANCE TEST and remain in the chosen data directory.

输出包含真实请求、响应、trace run ID 与本地服务端源文件哈希。哈希指向磁盘文件，不是对其他服务进程版本的独立认证。每项检查只执行一次，不自动重试记忆写入。验收数据带 ACCEPTANCE TEST 标识，保留在指定目录。

## Six HTTP contracts / 六项 HTTP 契约

| Check / 检查 | Expected / 预期 |
| --- | --- |
| Create verified with empty evidence / 已验证但证据为空 | 400 |
| Create verified with whitespace evidence / 证据仅有空白 | 400 |
| Create an unverified draft / 创建待验证草稿 | 201 |
| Update with evidence / 有证据时升级状态 | 200 |
| Clear verified evidence / 清空已验证证据 | 400 |
| Read back the rejected update / 读取被拒编辑后的记录 | Original valid record preserved / 原有效记录保持 |

The checker also expects 26 trace events: run start/end plus four events per check. Exit 0 requires all six checks and this event count to pass.

另检查26条预期事件：运行开始 / 结束，加每项检查的四条事件。只有六项契约与事件数量均满足时才退出0。

## Observed local results / 本地实测结果

On 2026-10-27, a Windows local run demonstrated:

| Item / 项目 | Before / 修复前 | After / 修复后 |
| --- | --- | --- |
| HTTP contracts / HTTP契约 | 2/6 | 6/6 |
| Original unit suite / 原始单元用例 | 3 passed, 3 cleanup errors / 3通过、3清理错误 | Expanded suite: 9/9 / 扩展后9项通过 |

Two changes produced these results: centralized evidence validation in `create_memory`, and explicit connection closure in `dbconnect` with initialization using the same entrypoint. The Windows errors were database-file locks during temporary-directory cleanup.

对应改动是 `create_memory` 的共享证据校验，以及由 `dbconnect` 统一关闭数据库连接、初始化复用该入口。Windows错误来自清理临时目录时数据库文件仍被占用。

These are observed results for a specific environment, not a CI badge or evidence of universal agent reliability. Raw local traces, paths and draft reports are kept outside the publication surface in ignored directories.

这些结果来自具体环境，不代表已经配置CI，也不证明所有Agent可靠。原始本地轨迹、路径与草稿报告保留在忽略目录，不随发布内容上传。

## Not established / 尚未证明

- Automated truth checking of evidence text / 自动判断证据内容是否真实。
- Browser clicks, clipboard permissions or visual layout / 浏览器点击、剪贴板权限与视觉布局。
- Before/after performance, production correctness or concurrent agent attribution / 性能前后比较、生产业务正确性、多Agent归属。
- CI enforcement or dedicated architecture lint / CI阻断或专用架构lint。
