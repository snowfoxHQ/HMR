# HMR Memory Service

把 HMR 包成本地 HTTP 服务，供 OpenClaw 等 agent 通过 hmr-memory skill 调用。

## 前提

1. 已安装 HMR：在 HMR 项目目录（含 pyproject.toml）运行过：
   ```bash
   pip install -e .
   ```
2. 安装服务依赖：
   ```bash
   pip install fastapi uvicorn
   ```

## 启动

```bash
python server.py
```
- Windows 也可双击 `start_service.bat`
- Linux/Mac 也可运行 `./start_service.sh`

看到 `HMR vX.X.X 就绪` 和 `Uvicorn running on http://127.0.0.1:8077` 即成功。
这个窗口要一直开着，服务才在运行。

## 测试（不需要 OpenClaw）

另开一个终端：
```bash
python test_service.py
```
看到 `✅ HMR 服务工作正常` 说明服务端没问题。

## 接入 OpenClaw

```bash
openclaw skills install hmr-memory
openclaw agent --message "记住我喜欢用 Python"
openclaw agent --message "我喜欢什么编程语言？"
```
第二句能答出 Python 即对接成功。

## 配置（可选环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| `HMR_STORAGE_PATH` | `./hmr_data` | 数据存储路径 |
| `HMR_HOST` | `127.0.0.1` | 监听地址（勿改成 0.0.0.0） |
| `HMR_PORT` | `8077` | 端口 |
| `HMR_TOKEN` | （空） | 访问令牌，设了则 skill 端也要设相同值 |

## 排错

- `找不到 hmr 包` → 没装 HMR，在 HMR 项目目录运行 `pip install -e .`
- `缺少服务依赖` → 运行 `pip install fastapi uvicorn`

## 安全

- 服务只绑 `127.0.0.1`，不要改成 `0.0.0.0` 对外开放
- 不要让 agent 把不可信内容（抓取的网页等）存入长期记忆（memory poisoning）

## 接口列表

| 接口 | 方法 | 作用 |
|------|------|------|
| `/health` | GET | 健康检查（返回版本、provider、记忆数、同步状态） |
| `/ingest` | POST | 存入记忆 |
| `/recall` | POST | 召回记忆 |
| `/save_state` | POST | 保存认知状态 |
| `/restore_state` | GET | 恢复认知状态 |
| `/reindex` | POST | 重建向量索引（embedding 提供者切换后用） |
| `/status` | GET | 完整系统状态 |

## 故障自愈：embedding 提供者切换

如果你更换了 embedding 提供者（如从 sentence-transformers 换成 ollama），
旧的向量索引会与新提供者不匹配，导致语义搜索失效。HMR 服务会自动检测：

- 启动时在日志里警告：`⚠️ 检测到 Embedding 提供者切换：X → Y`
- `/health` 返回 `status: degraded` 并在 `warning` 里说明
- `/recall` 返回 409 错误，明确告知原因和修复方法

修复只需一个请求（无需停服务、无需手动 --force）：
```bash
curl -X POST http://127.0.0.1:8077/reindex
```

## 配置 Embedding 模型（中文支持）

本地模型默认 `all-MiniLM-L6-v2`（中文较弱）。中文/中英混排场景，
通过环境变量 `HMR_ST_MODEL` 换模型，无需改代码：

```bash
# Windows (PowerShell)
$env:HMR_ST_MODEL="BAAI/bge-m3"
python server.py

# Linux / macOS
export HMR_ST_MODEL="BAAI/bge-m3"
python server.py
```

推荐模型：
| 模型 | 大小 | 场景 |
|------|------|------|
| `all-MiniLM-L6-v2`（默认） | ~80MB | 英文为主 |
| `BAAI/bge-small-zh-v1.5` | ~100MB | 中文为主，轻量 |
| `BAAI/bge-m3` | ~2.2GB | 中英双语都强，混排首选 |

> 换模型后旧索引失效，需调用 `POST /reindex` 重建一次。

### 用 Ollama 本地模型（中文推荐）

如果你用 Ollama 在本地跑了 bge-m3 等模型，让 HMR 服务直接调用：

```bash
ollama pull bge-m3

# Windows (PowerShell)
$env:HMR_OLLAMA_MODEL="bge-m3"
python server.py

# Linux / macOS
export HMR_OLLAMA_MODEL="bge-m3"
python server.py
```

启动日志显示 `使用 Ollama (bge-m3, dim=1024)` 即成功。
切换后旧索引失效，调用一次 `POST /reindex` 重建。

完整优先级：OpenAI（设 OPENAI_API_KEY）> Ollama（设 HMR_OLLAMA_MODEL）
> sentence-transformers（设 HMR_ST_MODEL）> TF-IDF（兜底）。

### 按语言过滤召回（可选）

双语模型搜中文时可能混入英文结果。设 `HMR_LANG_FILTER` 控制：
- `off`（默认）不过滤；`auto` 按查询语言；`zh`/`en` 强制指定。

```bash
$env:HMR_LANG_FILTER="auto"   # 搜中文只出中文
python server.py
```
