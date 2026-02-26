# VMware AIops

English | [中文](README-CN.md)

AI-powered VMware vCenter/ESXi monitoring and operations tool.

[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-AIops)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### Quick Install for Claude Code / Claude Code 快速安装

```bash
# Add marketplace / 添加市场
/plugin marketplace add zw008/VMware-AIops

# Install plugin / 安装插件
/plugin install vmware-ops

# Use it / 开始使用
/vmware-ops:vmware-aiops
```

---

## Capabilities Overview / 功能能力总览

### Architecture / 架构

```
用户 (自然语言 / Natural Language)
  ↓
AI CLI 工具 (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓ 读取 SKILL.md / AGENTS.md / rules 指令
  ↓
vmware-aiops CLI
  ↓ pyVmomi (vSphere SOAP API)
  ↓
vCenter Server ──→ ESXi 集群 ──→ VM
    或 / or
ESXi 独立主机 ──→ VM
```

### Version Compatibility / 版本兼容性

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | `CreateSnapshot_Task` deprecated → use `CreateSnapshotEx_Task` |
| 7.0 / 7.0U1-U3 | ✅ Full | All APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed. The same codebase manages both 7.0 and 8.0 environments seamlessly.

### 1. Inventory / 资源清单

| Feature / 功能 | vCenter | ESXi | Details / 说明 |
|------|:-------:|:----:|------|
| List VMs / 列出虚拟机 | ✅ | ✅ | Name, power state, CPU, memory, guest OS, IP / 名称、电源状态、CPU、内存、操作系统、IP |
| List Hosts / 列出主机 | ✅ | ⚠️ Self only / 仅自身 | CPU cores, memory, ESXi version, VM count, uptime / CPU 核数、内存、版本、VM 数、在线时间 |
| List Datastores / 列出数据存储 | ✅ | ✅ | Capacity, free/used, type (VMFS/NFS), usage % / 容量、已用/可用、类型、使用率 |
| List Clusters / 列出集群 | ✅ | ❌ | Host count, DRS/HA status / 主机数、DRS/HA 状态 |
| List Networks / 列出网络 | ✅ | ✅ | Network name, associated VM count / 网络名、关联 VM 数 |

### 2. Health & Monitoring / 健康监控

| Feature / 功能 | vCenter | ESXi | Details / 说明 |
|------|:-------:|:----:|------|
| Active Alarms / 活跃告警 | ✅ | ✅ | Severity, alarm name, entity, timestamp / 严重级别、告警名、实体、时间 |
| Event/Log Query / 事件日志查询 | ✅ | ✅ | Filter by time range (--hours), severity level; 50+ event types / 按时间、严重级别过滤，识别 50+ 事件类型 |
| Hardware Sensors / 硬件传感器 | ✅ | ✅ | Temperature, voltage, fan status / 温度、电压、风扇状态 |
| Host Services / 主机服务状态 | ✅ | ✅ | hostd, vpxa, etc. running/stopped / 服务运行/停止状态 |

**Monitored Event Types / 监控的事件类型**:

| Category / 分类 | Events / 事件 |
|------|------|
| VM Failures / VM 故障 | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues / 主机问题 | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage / 存储 | `DatastoreCapacityIncreasedEvent`, `NASDatastoreEvent`, SCSI high latency / SCSI 高延迟 |
| HA/DRS | `DasHostFailedEvent`, `DrsVmMigratedEvent`, `DrsSoftRuleViolationEvent` |
| Auth / 认证 | `UserLoginSessionEvent`, `BadUsernameSessionEvent` |

### 3. VM Lifecycle / 虚拟机生命周期

| Operation / 操作 | Command / 命令 | Confirmation / 确认 | vCenter | ESXi |
|------|------|:--------:|:-------:|:----:|
| Power On / 开机 | `vm power-on <name>` | — | ✅ | ✅ |
| Graceful Shutdown / 优雅关机 | `vm power-off <name>` | Double / 双重 | ✅ | ✅ |
| Force Power Off / 强制关机 | `vm power-off <name> --force` | Double / 双重 | ✅ | ✅ |
| Reset / 重置 | `vm reset <name>` | — | ✅ | ✅ |
| Suspend / 挂起 | `vm suspend <name>` | — | ✅ | ✅ |
| VM Info / 详情 | `vm info <name>` | — | ✅ | ✅ |
| Create VM / 创建 | `vm create <name> --cpu --memory --disk` | — | ✅ | ✅ |
| Delete VM / 删除 | `vm delete <name>` | Double / 双重 | ✅ | ✅ |
| Reconfigure / 调整配置 | `vm reconfigure <name> --cpu --memory` | Double / 双重 | ✅ | ✅ |
| Create Snapshot / 创建快照 | `vm snapshot-create <name> --name <snap>` | — | ✅ | ✅ |
| List Snapshots / 列出快照 | `vm snapshot-list <name>` | — | ✅ | ✅ |
| Revert Snapshot / 恢复快照 | `vm snapshot-revert <name> --name <snap>` | — | ✅ | ✅ |
| Delete Snapshot / 删除快照 | `vm snapshot-delete <name> --name <snap>` | — | ✅ | ✅ |
| Clone VM / 克隆 | `vm clone <name> --new-name <new>` | — | ✅ | ✅ |
| vMotion / 迁移 | `vm migrate <name> --to-host <host>` | — | ✅ | ❌ |

### 4. Scheduled Scanning & Notifications / 定时扫描与通知

| Feature / 功能 | Details / 说明 |
|------|------|
| Daemon / 守护进程 | APScheduler-based, configurable interval (default 15 min) / 基于 APScheduler，可配置间隔（默认 15 分钟） |
| Multi-target Scan / 多目标扫描 | Sequentially scan all configured vCenter/ESXi targets / 依次扫描所有配置的 vCenter/ESXi 目标 |
| Scan Content / 扫描内容 | Alarms + Events + Host logs (hostd, vmkernel, vpxd) / 告警 + 事件 + 主机日志 |
| Log Analysis / 日志分析 | Regex pattern matching: error, fail, critical, panic, timeout, corrupt / 正则匹配关键词 |
| Structured Log / 结构化日志 | JSONL output to `~/.vmware-aiops/scan.log` |
| Webhook / 通知推送 | Slack, Discord, or any HTTP endpoint / 支持 Slack、Discord 或任意 HTTP 端点 |
| Daemon Management / 进程管理 | `daemon start/stop/status`, PID file, graceful shutdown / PID 文件管理，优雅关闭 |

### 5. Safety Features / 安全特性

| Feature / 功能 | Details / 说明 |
|------|------|
| **Double Confirmation / 双重确认** | Power-off, delete, reconfigure require 2 sequential confirmations / 关机、删除、调整配置需连续两次确认 |
| **Password Protection / 密码保护** | `.env` file loading, never in command line or shell history / 通过 `.env` 加载密码，不会出现在命令行或 shell 历史 |
| **SSL Self-signed Support / 自签名证书** | `disableSslCertValidation` for ESXi 8.0 self-signed certs / 适配 ESXi 8.0 自签名证书 |
| **Task Waiting / 任务等待** | All async operations wait for completion and report result / 所有异步操作等待完成并报告结果 |
| **State Validation / 状态校验** | Pre-operation checks (VM exists, power state correct) / 操作前检查 VM 是否存在、电源状态是否正确 |

### 6. vCenter vs ESXi Comparison / vCenter 与 ESXi 能力对比

| Capability / 能力 | vCenter | ESXi Standalone / ESXi 独立 |
|------|:-------:|:----:|
| Full cluster inventory / 完整集群清单 | ✅ | ❌ Single host only / 仅单主机 |
| DRS/HA management / DRS/HA 管理 | ✅ | ❌ |
| vMotion migration / vMotion 迁移 | ✅ | ❌ |
| Cross-host clone / 跨主机克隆 | ✅ | ❌ |
| All VM lifecycle ops / 所有 VM 生命周期操作 | ✅ | ✅ |
| Alarms & events / 告警与事件 | ✅ | ✅ |
| Hardware sensors / 硬件传感器 | ✅ | ✅ |
| Host services / 主机服务 | ✅ | ✅ |
| Snapshots / 快照 | ✅ | ✅ |
| Scheduled scanning / 定时扫描 | ✅ | ✅ |

---

## Supported AI Platforms / 支持的 AI 平台

| Platform / 平台 | Status / 状态 | Config File / 配置文件 | AI Model / AI 模型 |
|---------|--------|----------|----------|
| **Claude Code** | ✅ Native Skill / 原生技能 | `skill/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ Extension / 扩展 | `gemini-extension/GEMINI.md` | Google Gemini |
| **OpenAI Codex CLI** | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ Conventions / 约定文件 | `codex-skill/AGENTS.md` | Any (cloud + local) / 任意 |
| **Continue CLI** | ✅ Rules / 规则文件 | `codex-skill/AGENTS.md` | Any (cloud + local) / 任意 |
| **Trae IDE** | ✅ Rules / 规则文件 | `trae-rules/project_rules.md` | Claude/DeepSeek/GPT-4o/Doubao |
| **Kimi Code CLI** | ✅ Skill | `kimi-skill/SKILL.md` | Moonshot Kimi |
| **Python CLI** | ✅ Standalone / 独立运行 | N/A | N/A |

### Platform Comparison / 平台对比

| Feature / 功能 | Claude Code | Gemini CLI | Codex CLI | Aider | Continue | Trae IDE | Kimi CLI |
|---------|-------------|------------|-----------|-------|----------|----------|----------|
| Cloud AI / 云端 AI | Anthropic | Google | OpenAI | Any / 任意 | Any / 任意 | Multi / 多选 | Moonshot |
| Local models / 本地模型 | — | — | — | Ollama | Ollama | — | — |
| Skill system / 技能系统 | SKILL.md | Extension | SKILL.md | — | Rules | Rules | SKILL.md |
| MCP support / MCP 支持 | Native / 原生 | Native / 原生 | Via Skills | Third-party / 第三方 | Native / 原生 | — | — |
| Free tier / 免费额度 | — | 60 req/min | — | Self-hosted / 自托管 | Self-hosted / 自托管 | — | — |

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

Password environment variable naming convention / 密码环境变量命名规则:
```
VMWARE_{TARGET_NAME_UPPER}_PASSWORD
# Example: target "home-esxi" → VMWARE_HOME_ESXI_PASSWORD
# Example: target "prod-vcenter" → VMWARE_PROD_VCENTER_PASSWORD
```

### Step 3: Connect Your AI Tool / 连接你的 AI 工具

Choose one (or more) of the following: / 选择以下一种（或多种）：

---

#### Option A: Claude Code (Marketplace) / 方式 A：Claude Code（市场安装）

**Method 1: Marketplace (recommended) / 方式 1：市场安装（推荐）**

In Claude Code, run: / 在 Claude Code 中执行：
```
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
```

Then use: / 然后使用：
```
/vmware-ops:vmware-aiops
> 192.168.1.100 是 ESXi 主机，用户名 root
```

**Method 2: Local install / 方式 2：本地安装**

```bash
# Clone and symlink / 克隆并链接
git clone https://github.com/zw008/VMware-AIops.git
ln -sf $(pwd)/VMware-AIops ~/.claude/plugins/marketplaces/vmware-aiops

# Register marketplace / 注册市场
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/plugins/known_marketplaces.json'
d = json.loads(f.read_text()) if f.exists() else {}
d['vmware-aiops'] = {
    'source': {'source': 'github', 'repo': 'zw008/VMware-AIops'},
    'installLocation': str(pathlib.Path.home() / '.claude/plugins/marketplaces/vmware-aiops')
}
f.write_text(json.dumps(d, indent=2))
"

# Enable plugin / 启用插件
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/settings.json'
d = json.loads(f.read_text()) if f.exists() else {}
d.setdefault('enabledPlugins', {})['vmware-ops@vmware-aiops'] = True
f.write_text(json.dumps(d, indent=2))
"
```

Restart Claude Code, then: / 重启 Claude Code，然后：
```
/vmware-ops:vmware-aiops
```

**Submit to Official Marketplace / 提交到官方市场**

This plugin can also be submitted to the [Anthropic official plugin directory](https://clau.de/plugin-directory-submission) for public discovery. / 本插件也可提交到 [Anthropic 官方插件目录](https://clau.de/plugin-directory-submission) 供公开发现。

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

#### Option F: Trae IDE / 方式 F：Trae IDE

Copy the rules file to your project's `.trae/rules/` directory: / 将规则文件复制到项目的 `.trae/rules/` 目录：

```bash
mkdir -p .trae/rules
cp trae-rules/project_rules.md .trae/rules/project_rules.md
```

Trae IDE's Builder Mode reads `.trae/rules/` Markdown files at startup. / Trae IDE 的 Builder Mode 会在启动时自动读取规则文件。

> **Note**: You can also install Claude Code extension in Trae IDE and use `.claude/skills/` format directly. / 也可以在 Trae IDE 中安装 Claude Code 扩展，直接使用 `.claude/skills/` 格式。

---

#### Option G: Kimi Code CLI / 方式 G：Kimi Code CLI

```bash
# Copy skill file to Kimi skills directory / 复制技能文件到 Kimi 技能目录
mkdir -p ~/.kimi/skills/vmware-aiops
cp kimi-skill/SKILL.md ~/.kimi/skills/vmware-aiops/SKILL.md
```

---

#### Option H: Standalone CLI (no AI) / 方式 H：独立 CLI（无需 AI）

```bash
# Already installed in Step 1 / 在第 1 步已安装
source .venv/bin/activate

vmware-aiops inventory vms --target home-esxi
vmware-aiops health alarms --target home-esxi
vmware-aiops vm power-on my-vm --target home-esxi
```

---

## Chinese Cloud Models / 国内云端模型

For users in China who prefer domestic cloud APIs or have limited access to overseas services. / 国内用户推荐使用国产云端 API，无需翻墙。

### DeepSeek（深度求索）

Cost-effective, strong coding capability. / 性价比高，编程能力强。

```bash
# Set DeepSeek API key (get from https://platform.deepseek.com)
# 设置 DeepSeek API 密钥（从 https://platform.deepseek.com 获取）
export DEEPSEEK_API_KEY="your-key"

# Run with Aider / 配合 Aider 运行
aider --conventions codex-skill/AGENTS.md \
  --model deepseek/deepseek-coder
```

Persistent config `~/.aider.conf.yml` / 持久化配置：
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

### With Continue CLI / 配合 Continue CLI

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

---

## Local Models / 本地模型（Aider + Ollama）

For fully offline operation — no cloud API, no internet, full privacy. / 完全离线运行 — 无需云端 API，无需联网，完全隐私。

**Aider + Ollama + local Qwen/DeepSeek** is ideal for Chinese users or air-gapped environments. / **Aider + Ollama + 本地 Qwen/DeepSeek** 是国内用户或隔离网络的最佳方案。

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
| **Qwen 2.5 Coder 32B** | `ollama pull qwen2.5-coder:32b` | ~20GB | Best local coding / 最佳本地编程模型 |
| **Qwen 2.5 Coder 7B** | `ollama pull qwen2.5-coder:7b` | ~4.5GB | Low-memory / 低内存选择 |
| **DeepSeek Coder V2** | `ollama pull deepseek-coder-v2` | ~8.9GB | Strong reasoning / 推理能力强 |
| **CodeLlama 34B** | `ollama pull codellama:34b` | ~19GB | Meta coding model |

> **Hardware / 硬件要求**: 32B → ~20GB VRAM (or 32GB RAM for CPU). 7B → 8GB RAM. / 32B 模型需 20GB 显存（或 32GB 内存 CPU 跑）。7B 模型 8GB 内存即可。

### Step 3: Run with Aider / 用 Aider 运行

```bash
pip install aider-chat
ollama serve

# Aider + local Qwen (recommended / 推荐)
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b

# Aider + local DeepSeek
aider --conventions codex-skill/AGENTS.md \
  --model ollama/deepseek-coder-v2

# Low-memory option / 低内存选择
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:7b
```

Persistent config `~/.aider.conf.yml` / 持久化配置：
```yaml
model: ollama/qwen2.5-coder:32b
conventions: codex-skill/AGENTS.md
```

### Local Architecture / 本地架构

```
用户 → Aider CLI → Ollama (localhost:11434) → Qwen / DeepSeek 本地模型
  │                                                    ↓
  │                                          读取 AGENTS.md 指令
  │                                                    ↓
  └──────────────────────────────→ vmware-aiops CLI ──→ ESXi / vCenter
```

> **Tip**: Local models are fully offline — perfect for air-gapped environments or strict data compliance. / 本地模型完全离线 — 适合隔离网络或严格数据合规环境。

---

## CLI Reference / CLI 命令参考

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
vmware-aiops vm snapshot-delete my-vm --name "before-upgrade"  # Delete snapshot / 删除快照
vmware-aiops vm clone my-vm --new-name my-vm-clone             # Clone VM / 克隆虚拟机
vmware-aiops vm migrate my-vm --to-host esxi-02                # vMotion / 迁移虚拟机

# Scan / 扫描
vmware-aiops scan now              # One-time scan / 一次性扫描

# Daemon / 守护进程
vmware-aiops daemon start          # Start scanner / 启动扫描守护进程
vmware-aiops daemon status         # Check status / 查看状态
vmware-aiops daemon stop           # Stop daemon / 停止守护进程
```

---

## Configuration / 配置说明

See `config.example.yaml` for all options. / 完整选项见 `config.example.yaml`。

| Section / 节 | Key / 键 | Default / 默认值 | Description / 说明 |
|---------|-----|---------|-------------|
| targets | name | — | Friendly name / 目标名称 |
| targets | host | — | vCenter/ESXi hostname or IP / 主机名或 IP |
| targets | type | vcenter | `vcenter` or `esxi` / 类型 |
| targets | port | 443 | Connection port / 连接端口 |
| targets | verify_ssl | false | SSL certificate verification / SSL 证书验证 |
| scanner | interval_minutes | 15 | Scan frequency / 扫描频率（分钟） |
| scanner | severity_threshold | warning | Min severity: critical/warning/info / 最低严重级别 |
| scanner | lookback_hours | 1 | How far back to scan / 回溯扫描时长（小时） |
| scanner | log_types | [vpxd, hostd, vmkernel] | Log sources / 日志源 |
| notify | log_file | ~/.vmware-aiops/scan.log | JSONL log output / 日志输出路径 |
| notify | webhook_url | — | Webhook endpoint (Slack, Discord, etc.) / Webhook 地址 |

---

## Project Structure / 项目结构

```
VMware-AIops/
├── .claude-plugin/                # Claude Code marketplace manifest / 市场清单
│   └── marketplace.json           # Marketplace registration / 市场注册文件
├── plugins/                       # Claude Code plugin / 插件
│   └── vmware-ops/
│       ├── .claude-plugin/
│       │   └── plugin.json        # Plugin manifest / 插件清单
│       └── skills/
│           └── vmware-aiops/
│               └── SKILL.md       # Skill instructions / 技能指令
├── vmware_aiops/                  # Python backend / Python 后端
│   ├── config.py                  # YAML + .env config / 配置管理
│   ├── connection.py              # Multi-target pyVmomi / 多目标连接管理
│   ├── cli.py                     # Typer CLI (double confirm) / CLI（双重确认）
│   ├── ops/                       # Operations / 运维操作
│   │   ├── inventory.py           # VMs, hosts, datastores, clusters / 资源清单
│   │   ├── health.py              # Alarms, events, sensors / 健康检查
│   │   └── vm_lifecycle.py        # VM CRUD, snapshots, clone, migrate / VM 生命周期
│   ├── scanner/                   # Log scanning daemon / 日志扫描守护进程
│   └── notify/                    # Notifications (JSONL + webhook) / 通知
├── skill/                         # Standalone skill file / 独立技能文件
│   └── SKILL.md
├── gemini-extension/              # Gemini CLI extension / Gemini CLI 扩展
│   ├── gemini-extension.json
│   └── GEMINI.md
├── codex-skill/                   # Codex + Aider + Continue / 多平台共用
│   ├── SKILL.md
│   └── AGENTS.md
├── trae-rules/                    # Trae IDE rules / Trae IDE 规则
│   └── project_rules.md
├── kimi-skill/                    # Kimi Code CLI skill / Kimi Code CLI 技能
│   └── SKILL.md
├── RELEASE_NOTES.md               # Release history / 版本发布历史
├── config.example.yaml
└── pyproject.toml
```

## API Coverage / API 覆盖

Built on **pyVmomi** (vSphere Web Services API / SOAP). / 基于 **pyVmomi**（vSphere SOAP API）构建。

| API Object | Usage / 用途 |
|------------|------|
| `vim.VirtualMachine` | VM lifecycle, snapshots, clone, migrate / 虚拟机生命周期、快照、克隆、迁移 |
| `vim.HostSystem` | ESXi host info, sensors, services / 主机信息、传感器、服务 |
| `vim.Datastore` | Storage capacity, type, accessibility / 存储容量、类型 |
| `vim.ClusterComputeResource` | Cluster, DRS, HA / 集群、DRS、HA |
| `vim.Network` | Network listing / 网络列表 |
| `vim.alarm.AlarmManager` | Active alarm monitoring / 活跃告警监控 |
| `vim.event.EventManager` | Event/log queries / 事件日志查询 |

## Troubleshooting & Contributing / 问题反馈与贡献

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this project!

如果遇到任何报错或问题，请将错误信息、日志或截图发送至 **zhouwei008@gmail.com**。欢迎加入我们，一起维护和改进这个项目！

## License / 许可证

MIT
