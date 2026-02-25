# VMware AIops

AI-powered VMware vCenter/ESXi monitoring and operations tool.

AI 驱动的 VMware vCenter/ESXi 监控与运维工具。

Supports multiple AI coding CLI tools / 支持多种 AI 编程 CLI 工具:

| Platform / 平台 | Status / 状态 | Instructions File / 指令文件 |
|---------|--------|----------|
| **Claude Code** | ✅ Native Skill / 原生技能 | `skill/SKILL.md` |
| **Gemini CLI** | ✅ Extension / 扩展 | `gemini-extension/GEMINI.md` |
| **OpenAI Codex CLI** | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` |
| **Aider** | ✅ Conventions / 约定文件 | `codex-skill/AGENTS.md` (as conventions) |
| **Continue CLI** | ✅ Rules / 规则文件 | `codex-skill/AGENTS.md` (as rules) |
| **Python CLI** | ✅ Standalone / 独立运行 | N/A |

## Features / 功能特性

- **Multi-target / 多目标**: Connect to multiple vCenter Servers and standalone ESXi hosts / 连接多个 vCenter 和独立 ESXi 主机
- **Inventory / 资源清单**: List VMs, hosts, datastores, clusters, networks / 列出虚拟机、主机、存储、集群、网络
- **Health checks / 健康检查**: Active alarms, recent events, hardware sensor status / 活跃告警、近期事件、硬件传感器状态
- **VM lifecycle / 虚拟机生命周期**: Create, delete, power on/off, reset, suspend, reconfigure / 创建、删除、开关机、重置、挂起、调整配置
- **Snapshots / 快照**: Create, list, revert, delete / 创建、列出、恢复、删除
- **Clone & Migrate / 克隆与迁移**: VM cloning and vMotion / 虚拟机克隆和 vMotion 迁移
- **Double confirmation / 双重确认**: Destructive operations (power-off, delete, reconfigure) require two confirmations / 危险操作（关机、删除、调整配置）需要两次确认
- **Scheduled scanning / 定时扫描**: APScheduler daemon scans logs and alarms at configurable intervals / APScheduler 守护进程按配置间隔扫描日志和告警
- **Notifications / 通知**: Structured JSON log files + generic webhook (Slack, Discord, etc.) / 结构化 JSON 日志 + 通用 Webhook（Slack、Discord 等）

---

## Installation / 安装

### Step 0: Prerequisites / 前置条件

```bash
# Python 3.10+ required / 需要 Python 3.10+
python3 --version

# Node.js 18+ required for Gemini CLI and Codex CLI / Gemini CLI 和 Codex CLI 需要 Node.js 18+
node --version
```

### Step 1: Clone & Install Python Backend / 克隆并安装 Python 后端

All platforms share the same Python backend. / 所有平台共用同一个 Python 后端。

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2: Configure / 配置

```bash
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
# Edit config.yaml with your vCenter/ESXi targets
# 编辑 config.yaml，填入你的 vCenter/ESXi 目标信息
```

Set passwords via `.env` file (recommended) / 通过 `.env` 文件设置密码（推荐）:
```bash
cat > ~/.vmware-aiops/.env << 'EOF'
VMWARE_PROD_VCENTER_PASSWORD=your-password
VMWARE_LAB_ESXI_PASSWORD=your-password
EOF
chmod 600 ~/.vmware-aiops/.env
```

> **Security note / 安全提示**: Prefer `.env` file over command-line `export` to avoid passwords appearing in shell history. / 推荐使用 `.env` 文件而非命令行 `export`，避免密码出现在 shell 历史记录中。

### Step 3: Connect Your AI Tool / 连接你的 AI 工具

Choose one (or more) of the following: / 选择以下一种（或多种）：

---

#### Option A: Claude Code / 方式 A：Claude Code

```bash
# Register and enable the plugin / 注册并启用插件
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/plugins/known_marketplaces.json'
d = json.loads(f.read_text()) if f.exists() else {}
d['vmware-aiops'] = {
    'source': {'source': 'github', 'repo': 'zw008/VMware-AIops'},
    'installLocation': str(pathlib.Path.home() / '.claude/plugins/marketplaces/vmware-aiops')
}
f.write_text(json.dumps(d, indent=2))
print('Marketplace registered.')
"

python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/settings.json'
d = json.loads(f.read_text()) if f.exists() else {}
d.setdefault('enabledPlugins', {})['vmware-ops@vmware-aiops'] = True
f.write_text(json.dumps(d, indent=2))
print('Plugin enabled.')
"

# Symlink the plugin source / 创建插件源链接
ln -sf $(pwd) ~/.claude/plugins/marketplaces/vmware-aiops
```

Restart Claude Code, then / 重启 Claude Code，然后：
```
You: /vmware-ops:vmware-aiops
You: "192.168.1.100 是 ESXi 主机，用户名 root"
```

---

#### Option B: Gemini CLI / 方式 B：Gemini CLI

```bash
# Install Gemini CLI / 安装 Gemini CLI
npm install -g @google/gemini-cli

# Install the extension from the cloned repo / 从克隆的仓库安装扩展
gemini extensions install ./gemini-extension

# Or install directly from GitHub / 或直接从 GitHub 安装
# gemini extensions install https://github.com/zw008/VMware-AIops
```

Then start Gemini CLI / 然后启动 Gemini CLI：
```
gemini
> Show me all VMs on my ESXi host
> 显示 ESXi 上所有虚拟机
```

---

#### Option C: OpenAI Codex CLI / 方式 C：OpenAI Codex CLI

```bash
# Install Codex CLI / 安装 Codex CLI
npm i -g @openai/codex
# Or on macOS / 或 macOS 上：
# brew install --cask codex

# Copy skill to Codex skills directory / 复制技能到 Codex 技能目录
mkdir -p ~/.codex/skills/vmware-aiops
cp codex-skill/SKILL.md ~/.codex/skills/vmware-aiops/SKILL.md

# Copy AGENTS.md to project root / 复制 AGENTS.md 到项目根目录
cp codex-skill/AGENTS.md ./AGENTS.md
```

Then start Codex CLI / 然后启动 Codex CLI：
```bash
codex --enable skills
> List all VMs on my ESXi
> 列出 ESXi 上的所有虚拟机
```

---

#### Option D: Aider (supports local models) / 方式 D：Aider（支持本地模型）

```bash
# Install Aider / 安装 Aider
pip install aider-chat

# Install Ollama for local models (optional) / 安装 Ollama 运行本地模型（可选）
# macOS:
brew install ollama
ollama pull qwen2.5-coder:32b

# Run with cloud API / 使用云端 API 运行
aider --conventions codex-skill/AGENTS.md

# Or with local model via Ollama / 或使用 Ollama 本地模型运行
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b
```

---

#### Option E: Continue CLI (supports local models) / 方式 E：Continue CLI（支持本地模型）

```bash
# Install Continue CLI / 安装 Continue CLI
npm i -g @continuedev/cli

# Copy rules file / 复制规则文件
mkdir -p .continue/rules
cp codex-skill/AGENTS.md .continue/rules/vmware-aiops.md
```

Configure `~/.continue/config.yaml` for local model / 配置本地模型：
```yaml
models:
  - name: local-coder
    provider: ollama
    model: qwen2.5-coder:32b
```

Then / 然后：
```bash
cn
> Check ESXi health and alarms
> 检查 ESXi 健康状态和告警
```

---

#### Option F: Standalone CLI (no AI) / 方式 F：独立 CLI（无需 AI）

```bash
# Already installed in Step 1 / 在第 1 步已安装
source .venv/bin/activate

vmware-aiops inventory vms --target home-esxi
vmware-aiops health alarms --target home-esxi
vmware-aiops vm power-on my-vm --target home-esxi
```

---

## Chinese Cloud Models / 国内模型推荐

For users in China who prefer domestic cloud APIs or have limited access to overseas services: / 国内用户推荐使用国产云端 API，无需翻墙：

### DeepSeek（深度求索）

Cost-effective, strong coding capability. / 性价比高，编程能力强。

```bash
# Install Aider / 安装 Aider
pip install aider-chat

# Set DeepSeek API key (get from https://platform.deepseek.com)
# 设置 DeepSeek API 密钥（从 https://platform.deepseek.com 获取）
export DEEPSEEK_API_KEY="your-key"

# Run / 运行
aider --conventions codex-skill/AGENTS.md \
  --model deepseek/deepseek-coder
```

Or configure in `~/.aider.conf.yml` for persistent settings / 或写入配置文件持久化：
```yaml
model: deepseek/deepseek-coder
conventions: codex-skill/AGENTS.md
```

### Qwen（通义千问）

Alibaba Cloud's coding model, free tier available. / 阿里云编程模型，有免费额度。

```bash
# Set DashScope API key (get from https://dashscope.console.aliyun.com)
# 设置灵积 API 密钥（从 https://dashscope.console.aliyun.com 获取）
export DASHSCOPE_API_KEY="your-key"

# Use with Aider / 配合 Aider 使用
aider --conventions codex-skill/AGENTS.md \
  --model qwen/qwen-coder-plus
```

Or via OpenAI-compatible endpoint / 或通过 OpenAI 兼容接口：
```bash
export OPENAI_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="your-dashscope-key"

aider --conventions codex-skill/AGENTS.md \
  --model qwen-coder-plus-latest
```

### Doubao（豆包 / 字节跳动）

```bash
export OPENAI_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
export OPENAI_API_KEY="your-ark-key"

aider --conventions codex-skill/AGENTS.md \
  --model your-doubao-endpoint-id
```

### With Continue CLI / 配合 Continue CLI 使用

Configure `~/.continue/config.yaml` / 配置文件：

```yaml
# DeepSeek
models:
  - name: deepseek-coder
    provider: openai-compatible
    apiBase: https://api.deepseek.com/v1
    apiKey: your-deepseek-key
    model: deepseek-coder

# Qwen / 通义千问
models:
  - name: qwen-coder
    provider: openai-compatible
    apiBase: https://dashscope.aliyuncs.com/compatible-mode/v1
    apiKey: your-dashscope-key
    model: qwen-coder-plus-latest
```

### Architecture / 架构原理

```
用户 → AI CLI 工具 (Aider / Continue) → 云端模型 (DeepSeek / Qwen / 豆包)
  │                                           ↓
  │                                    读取 AGENTS.md 指令
  │                                           ↓
  └──────────────────────────────→ vmware-aiops CLI ──→ ESXi / vCenter
```

The AI model reads `AGENTS.md` instructions to understand how to use `vmware-aiops` CLI, then generates and executes commands on your behalf. / AI 模型读取 `AGENTS.md` 指令，了解如何使用 `vmware-aiops` CLI，然后代你生成并执行命令。

---

## Local Models / 本地模型（Aider + Ollama 推荐方案）

For users who prefer running models locally — no cloud API, no internet, full privacy. **Aider + Ollama + local Qwen/DeepSeek** is a great combination for Chinese users. / 如果你更喜欢本地运行模型 — 无需云端 API，无需联网，完全隐私。**Aider + Ollama + 本地 Qwen/DeepSeek** 是国内用户的最佳组合。

### Step 1: Install Ollama / 安装 Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull a model / 下载模型

| Model / 模型 | Command / 命令 | Size / 大小 | Note / 说明 |
|------|--------|---------|---------|
| **Qwen 2.5 Coder 32B** | `ollama pull qwen2.5-coder:32b` | ~20GB | Best local coding model / 最佳本地编程模型 |
| **Qwen 2.5 Coder 7B** | `ollama pull qwen2.5-coder:7b` | ~4.5GB | Low-memory option / 低内存选择 |
| **DeepSeek Coder V2** | `ollama pull deepseek-coder-v2` | ~8.9GB | Strong reasoning / 推理能力强 |
| **CodeLlama 34B** | `ollama pull codellama:34b` | ~19GB | Meta's coding model / Meta 编程模型 |

> **Hardware note / 硬件要求**: 32B models need ~20GB VRAM (or 32GB RAM for CPU). 7B models work on 8GB RAM. / 32B 模型需要约 20GB 显存（或 32GB 内存用 CPU 跑）。7B 模型 8GB 内存即可。

### Step 3: Run with Aider / 用 Aider 运行

```bash
# Install Aider / 安装 Aider
pip install aider-chat

# Start Ollama server / 启动 Ollama 服务
ollama serve

# Aider + local Qwen (recommended / 推荐)
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b

# Aider + local DeepSeek
aider --conventions codex-skill/AGENTS.md \
  --model ollama/deepseek-coder-v2

# Smaller model for low-memory machines / 低内存机器用小模型
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:7b
```

### Persistent config / 持久化配置

Create `~/.aider.conf.yml` to avoid typing flags every time / 创建配置文件避免每次输入参数：

```yaml
# Local Qwen model / 本地通义千问模型
model: ollama/qwen2.5-coder:32b
conventions: codex-skill/AGENTS.md

# Or DeepSeek / 或深度求索
# model: ollama/deepseek-coder-v2
```

### Architecture / 本地模型架构

```
用户 → Aider CLI → Ollama (localhost:11434) → Qwen / DeepSeek 本地模型
  │                                                    ↓
  │                                          读取 AGENTS.md 指令
  │                                                    ↓
  └──────────────────────────────→ vmware-aiops CLI ──→ ESXi / vCenter
```

> **Tip / 提示**: Local models are fully offline — perfect for air-gapped environments or strict data compliance. / 本地模型完全离线运行 — 适合隔离网络或严格数据合规环境。

## CLI Usage / CLI 使用

```bash
# Inventory / 资源清单
vmware-aiops inventory vms                          # List VMs / 列出虚拟机
vmware-aiops inventory hosts --target prod-vcenter  # List hosts / 列出主机
vmware-aiops inventory datastores                   # List datastores / 列出存储
vmware-aiops inventory clusters                     # List clusters / 列出集群

# Health / 健康检查
vmware-aiops health alarms                                # Active alarms / 活跃告警
vmware-aiops health events --hours 24 --severity warning  # Recent events / 近期事件

# VM operations / 虚拟机操作
vmware-aiops vm info my-vm                                     # VM details / 虚拟机详情
vmware-aiops vm power-on my-vm                                 # Power on / 开机
vmware-aiops vm power-off my-vm                                # Graceful shutdown (2x confirm) / 优雅关机（双重确认）
vmware-aiops vm power-off my-vm --force                        # Force power off (2x confirm) / 强制关机（双重确认）
vmware-aiops vm create my-new-vm --cpu 4 --memory 8192 --disk 100  # Create VM / 创建虚拟机
vmware-aiops vm delete my-vm --confirm                         # Delete VM (2x confirm) / 删除虚拟机（双重确认）
vmware-aiops vm reconfigure my-vm --cpu 4 --memory 8192        # Reconfigure (2x confirm) / 调整配置（双重确认）
vmware-aiops vm snapshot-create my-vm --name "before-upgrade"  # Create snapshot / 创建快照
vmware-aiops vm snapshot-list my-vm                            # List snapshots / 列出快照
vmware-aiops vm snapshot-revert my-vm --name "before-upgrade"  # Revert snapshot / 恢复快照
vmware-aiops vm clone my-vm --new-name my-vm-clone             # Clone VM / 克隆虚拟机
vmware-aiops vm migrate my-vm --to-host esxi-02                # vMotion / 迁移虚拟机

# Scan / 扫描
vmware-aiops scan now              # One-time scan / 一次性扫描

# Daemon / 守护进程
vmware-aiops daemon start          # Start scanner daemon / 启动扫描守护进程
vmware-aiops daemon status         # Check daemon status / 查看守护进程状态
vmware-aiops daemon stop           # Stop daemon / 停止守护进程
```

## Configuration / 配置说明

See `config.example.yaml` for all options. / 完整选项见 `config.example.yaml`。

| Section / 节 | Key / 键 | Default / 默认值 | Description / 说明 |
|---------|-----|---------|-------------|
| targets | name | — | Friendly name / 目标名称 |
| targets | host | — | vCenter/ESXi hostname or IP / 主机名或 IP |
| targets | type | vcenter | `vcenter` or `esxi` / 类型 |
| targets | verify_ssl | false | SSL certificate verification / SSL 证书验证 |
| scanner | interval_minutes | 15 | Scan frequency / 扫描频率（分钟） |
| scanner | severity_threshold | warning | Min severity / 最低严重级别: critical/warning/info |
| scanner | lookback_hours | 1 | How far back to scan / 回溯扫描时长（小时） |
| notify | log_file | ~/.vmware-aiops/scan.log | JSONL log output / 日志输出路径 |
| notify | webhook_url | — | Webhook endpoint / Webhook 地址 |

## Architecture / 架构

```
VMware-AIops/
├── vmware_aiops/          # Python backend / Python 后端
│   ├── config.py          # YAML + .env config / 配置管理
│   ├── connection.py      # Multi-target pyVmomi / 多目标连接管理
│   ├── cli.py             # Typer CLI (double confirm) / CLI（双重确认）
│   ├── ops/               # Operations / 运维操作
│   │   ├── inventory.py   # VMs, hosts, datastores / 资源清单
│   │   ├── health.py      # Alarms, events / 健康检查
│   │   └── vm_lifecycle.py # VM CRUD / 虚拟机生命周期
│   ├── scanner/           # Log scanning / 日志扫描
│   └── notify/            # Notifications / 通知
├── skill/                 # Claude Code skill / Claude Code 技能
│   └── SKILL.md
├── gemini-extension/      # Gemini CLI extension / Gemini CLI 扩展
│   ├── gemini-extension.json
│   └── GEMINI.md
├── codex-skill/           # Codex CLI skill + AGENTS.md / Codex CLI 技能
│   ├── SKILL.md
│   └── AGENTS.md          # Also works for Aider & Continue / 同时适用于 Aider 和 Continue
├── config.example.yaml
└── pyproject.toml
```

## Platform Comparison / 平台对比

| Feature / 功能 | Claude Code | Gemini CLI | Codex CLI | Aider | Continue |
|---------|-------------|------------|-----------|-------|----------|
| Cloud AI / 云端 AI | Anthropic | Google | OpenAI | Any / 任意 | Any / 任意 |
| Local models / 本地模型 | — | — | — | Ollama | Ollama |
| Skill system / 技能系统 | SKILL.md | Extension | SKILL.md | — | Rules |
| MCP support / MCP 支持 | Native / 原生 | Native / 原生 | Via Skills | Third-party / 第三方 | Native / 原生 |
| Free tier / 免费额度 | — | 60 req/min | — | Self-hosted / 自托管 | Self-hosted / 自托管 |

## API Coverage / API 覆盖

Built on **pyVmomi** (vSphere Web Services API / SOAP). / 基于 **pyVmomi**（vSphere SOAP API）构建。

- `vim.VirtualMachine` — VM lifecycle / 虚拟机生命周期
- `vim.HostSystem` — ESXi host management / 主机管理
- `vim.Datastore` — Storage / 存储
- `vim.ClusterComputeResource` — Cluster (DRS, HA) / 集群
- `vim.Network` — Networking / 网络
- `vim.alarm.AlarmManager` — Alarms / 告警
- `vim.event.EventManager` — Events/logs / 事件与日志

## License / 许可证

MIT
