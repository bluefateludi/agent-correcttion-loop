# LoopLab 功能地图

运行与检查命令均从仓库根目录执行。API 已做本地验证；DOM 定位来自源码，浏览器点击与视觉验证仍待补充。

## 运行与边界

- 启动：`python server.py`，默认 `http://127.0.0.1:8765`。
- Python 后端：HTTP、SQLite trace、JSON 记忆、输入校验。
- 浏览器前端：`static/index.html`、`static/app.js`、`static/style.css`，不执行数据库或 Agent 任务。
- 默认数据：`data/traces.sqlite3`、`data/memory/*.json`；通过 `OBSERVER_DATA_DIR` 指定独立目录。
- 追踪每四秒轮询，最多列出120个运行；单个运行详情当前最多返回1000条事件。

## 功能入口

| 功能 | 页面 / DOM | API 与实现入口 | 预期行为 |
| --- | --- | --- | --- |
| 执行记录 | 默认页，`#runList`、`#eventList`、`#refreshBtn` | GET /api/runs、GET /api/runs/<id> | 查看已捕获运行、尝试、失败与结果 |
| 工程记忆 | `[data-tab="memory"]`、`#memoryList` | GET /api/memories | 查看已保存的 JSON 记忆 |
| 新建 | `#newMemoryBtn` → `#memoryForm` | POST /api/memories → create_memory | 待验证草稿可无证据；已验证但证据空白返回400 |
| 编辑 | `[data-edit]` → 同一表单，`#formError` 显示错误 | PUT /api/memories/<id> → create_memory | 有证据可升级；清空已验证证据被拒且旧记录保持 |
| 搜索 / 筛选 | `#memorySearch`、`#layerFilter` | 前端过滤已加载记录 | 按关键字和约束层筛选 |
| 复制 Markdown | `[data-md]` | GET /api/memories/<id>/markdown | 导出内容，前端请求剪贴板权限 |
| 删除 | `[data-delete]` | DELETE /api/memories/<id> | 确认后删除对应记忆；不用于验收正常数据 |

## 验证命令

```text
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/verify_memory_evidence.py --url http://127.0.0.1:8766 --output .local/verification/http.json
```

第二条要求先启动8766端口的独立实例，详见[验证说明](verification.md)。它会创建验收记录，不自动操作现有日常记忆。

## 状态解释

- 错误输入返回 HTTP 400 是对应反例用例的成功条件，不意味着检查失败。
- verified 表示使用者标记了状态且证据内容非空，不代表后端独立验证了内容。
- demo 表示模拟场景；acceptance-test 表示真实HTTP验收步骤，不是AI内部执行历史。
- 既有记录不自动迁移。完整主 / 子 Agent 树、代码行归属和自动影响分析不在当前实现中。
- 事件发送失败可能被忽略，因此不能将列表当作完整审计历史。
