<!-- mcp-name: io.github.zw008/vmware-aiops -->
# VMware AIops

[English](README.md) | 中文

AI 驱动的 VMware vCenter/ESXi 监控与运维工具。

> **提供两个技能版本：**
>
> | 技能 | 命令 | 使用场景 |
> |------|------|---------|
> | **vmware-monitor**（安全版） | `/vmware-ops:vmware-monitor` | 只读监控：资源清单、健康检查、告警、指标查询。不会误操作。 |
> | **vmware-aiops**（完整版） | `/vmware-ops:vmware-aiops` | 完整运维：监控全部功能 + 开关机、创建/删除 VM、快照、克隆、迁移。 |

[![ClawHub](https://img.shields.io/badge/ClawHub-vmware--aiops-orange)](https://clawhub.ai/skills/vmware-aiops)
[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-AIops)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-AIops)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 快速安装（推荐）

支持 Claude Code、Cursor、Codex、Gemini CLI、Trae 等 30+ AI 工具：

```bash
# 通过 Skills.sh 安装
npx skills add zw008/VMware-AIops

# 通过 ClawHub 安装
clawhub install vmware-aiops
```

### PyPI 安装（无需访问 GitHub）

```bash
# 通过 uv 安装（推荐）
uv tool install vmware-aiops

# 或通过 pip 安装
pip install vmware-aiops

# 国内镜像加速
pip install vmware-aiops -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Claude Code 快速安装

```bash
# 添加市场
/plugin marketplace add zw008/VMware-AIops

# 安装插件
/plugin install vmware-ops

# 使用完整版
/vmware-ops:vmware-aiops

# 或使用只读监控版（更安全）
/vmware-ops:vmware-monitor
```

---

## 功能总览

### CLI vs MCP：如何选择

| 场景 | 推荐模式 | 原因 |
|------|:-------:|------|
| **本地/小模型**（Ollama、Qwen <32B） | **CLI** | 上下文占用 ~2K tokens vs MCP ~10K；小模型难以处理 31 个工具 schema |
| **Token 敏感场景** | **CLI** | SKILL.md + Bash = 最小开销 |
| **云端大模型**（Claude、GPT-4o） | 均可 | MCP 提供结构化 JSON 输入输出 |
| **自动化管道 / Agent 链式调用** | **MCP** | 类型安全参数，结构化输出，无需 Shell 解析 |

> **经验法则**：追求成本和兼容性选 CLI，追求结构化自动化选 MCP。

### 架构

```
用户 (自然语言)
  ↓
AI CLI 工具 (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓ 读取 SKILL.md / AGENTS.md / rules 指令
  ↓
vmware-aiops CLI
  ↓ pyVmomi (vSphere SOAP API)
  ↓
vCenter Server ──→ ESXi 集群 ──→ VM
    或
ESXi 独立主机 ──→ VM
```

### 版本兼容性

| vSphere 版本 | 支持状态 | 说明 |
|-------------|---------|------|
| 8.0 / 8.0U1-U3 | ✅ 完全支持 | `CreateSnapshot_Task` 已弃用，推荐 `CreateSnapshotEx_Task` |
| 7.0 / 7.0U1-U3 | ✅ 完全支持 | 所有 API 正常工作 |
| 6.7 | ✅ 兼容 | 向后兼容，已测试 |
| 6.5 | ✅ 兼容 | 向后兼容，已测试 |

> pyVmomi 在 SOAP 握手阶段自动协商 API 版本，无需手动配置。同一套代码可同时管理 7.0 和 8.0 环境。

### 1. 资源清单

| 功能 | vCenter | ESXi | 说明 |
|------|:-------:|:----:|------|
| 列出虚拟机 | ✅ | ✅ | 名称、电源状态、CPU、内存、操作系统、IP |
| 列出主机 | ✅ | ⚠️ 仅自身 | CPU 核数、内存、版本、VM 数、在线时间 |
| 列出数据存储 | ✅ | ✅ | 容量、已用/可用、类型、使用率 |
| 列出集群 | ✅ | ❌ | 主机数、DRS/HA 状态 |
| 列出网络 | ✅ | ✅ | 网络名、关联 VM 数 |

### 2. 健康监控

| 功能 | vCenter | ESXi | 说明 |
|------|:-------:|:----:|------|
| 活跃告警 | ✅ | ✅ | 严重级别、告警名、实体、时间 |
| 事件日志查询 | ✅ | ✅ | 按时间、严重级别过滤，识别 50+ 事件类型 |
| 硬件传感器 | ✅ | ✅ | 温度、电压、风扇状态 |
| 主机服务状态 | ✅ | ✅ | 服务运行/停止状态 |

### 3. 虚拟机生命周期

| 操作 | 命令 | 确认 | vCenter | ESXi |
|------|------|:----:|:-------:|:----:|
| 开机 | `vm power-on <name>` | — | ✅ | ✅ |
| 优雅关机 | `vm power-off <name>` | 双重 | ✅ | ✅ |
| 强制关机 | `vm power-off <name> --force` | 双重 | ✅ | ✅ |
| 重置 | `vm reset <name>` | — | ✅ | ✅ |
| 创建 | `vm create <name> --cpu --memory --disk` | — | ✅ | ✅ |
| 删除 | `vm delete <name>` | 双重 | ✅ | ✅ |
| 调整配置 | `vm reconfigure <name> --cpu --memory` | 双重 | ✅ | ✅ |
| 创建快照 | `vm snapshot-create <name> --name <snap>` | — | ✅ | ✅ |
| 恢复快照 | `vm snapshot-revert <name> --name <snap>` | — | ✅ | ✅ |
| 克隆 | `vm clone <name> --new-name <new>` | — | ✅ | ✅ |
| 迁移 | `vm migrate <name> --to-host <host>` | — | ✅ | ❌ |
| **设置 TTL** | `vm set-ttl <name> --minutes <n>` | — | ✅ | ✅ |
| **取消 TTL** | `vm cancel-ttl <name>` | — | ✅ | ✅ |
| **列出 TTL** | `vm list-ttl` | — | ✅ | ✅ |
| **Clean Slate** | `vm clean-slate <name> [--snapshot baseline]` | 双重 | ✅ | ✅ |
| **Guest 执行** | `vm guest-exec <name> --cmd /bin/bash --args "..."` | — | ✅ | ✅ |
| **Guest 上传** | `vm guest-upload <name> --local f.sh --guest /tmp/f.sh` | — | ✅ | ✅ |
| **Guest 下载** | `vm guest-download <name> --guest /var/log/syslog --local ./syslog` | — | ✅ | ✅ |

> Guest Operations 需要 VM 内运行 VMware Tools。

### Plan → Apply（多步操作编排）

当操作涉及 2+ 步骤或 2+ 台 VM 时，自动使用 plan/apply 工作流：

| 步骤 | 说明 |
|------|------|
| 1. **创建 Plan** | AI 调用 `vm_create_plan` — 校验操作、检查 vSphere 中目标是否存在、生成带回滚信息的 plan |
| 2. **审查** | AI 展示 plan 给用户：步骤、影响的 VM、不可逆操作警告 |
| 3. **执行** | `vm_apply_plan` 按顺序执行；某步失败立即停止 |
| 4. **回滚**（如失败） | 询问用户是否回滚，`vm_rollback_plan` 逆序撤销已执行步骤（不可逆操作跳过） |

Plan 存储在 `~/.vmware-aiops/plans/`，成功后自动删除，超过 24 小时自动清理。

### 4. VM 部署与制备

| 操作 | 命令 | 速度 | vCenter | ESXi |
|------|------|:----:|:-------:|:----:|
| OVA 部署 | `deploy ova <path> --name <vm>` | 分钟级 | ✅ | ✅ |
| 模板部署 | `deploy template <tmpl> --name <vm>` | 分钟级 | ✅ | ✅ |
| 链接克隆 | `deploy linked-clone --source <vm> --snapshot <snap> --name <new>` | 秒级 | ✅ | ✅ |
| 挂载 ISO | `deploy iso <vm> --iso "[ds] path/to.iso"` | 即时 | ✅ | ✅ |
| 转为模板 | `deploy mark-template <vm>` | 即时 | ✅ | ✅ |
| 批量克隆 | `deploy batch-clone --source <vm> --count <n>` | 分钟级 | ✅ | ✅ |
| 批量部署 (YAML) | `deploy batch spec.yaml` | 自动 | ✅ | ✅ |

### 5. 数据存储浏览

| 功能 | vCenter | ESXi | 说明 |
|------|:-------:|:----:|------|
| 浏览文件 | ✅ | ✅ | 列出数据存储中任意路径的文件/文件夹 |
| 扫描镜像 | ✅ | ✅ | 发现所有数据存储中的 ISO、OVA、OVF、VMDK 文件 |
| 本地缓存 | ✅ | ✅ | 注册表位于 `~/.vmware-aiops/image_registry.json` |

### 6. 定时扫描与通知

| 功能 | 说明 |
|------|------|
| 守护进程 | 基于 APScheduler，可配置间隔（默认 15 分钟） |
| 多目标扫描 | 依次扫描所有配置的 vCenter/ESXi 目标 |
| 日志分析 | 正则匹配：error, fail, critical, panic, timeout, corrupt |
| 结构化日志 | JSONL 输出到 `~/.vmware-aiops/scan.log` |
| Webhook 通知 | 支持 Slack、Discord 或任意 HTTP 端点 |

### 7. vSAN 管理

| 功能 | 说明 |
|------|------|
| 健康检查 | 集群健康总览、分组测试结果 |
| 容量监控 | 总容量、可用、已用及趋势预测 |
| 磁盘组 | 每主机缓存 SSD + 容量盘列表 |
| 性能指标 | 集群/主机/VM 级别的 IOPS、延迟、吞吐 |

> 需要 pyVmomi 8.0.3+（vSAN SDK 已合并）。旧版本需单独安装 vSAN Management SDK。

### 8. Aria Operations / VCF Operations

| 功能 | 说明 |
|------|------|
| 历史指标 | 时序 CPU、内存、磁盘、网络，保留数月历史 |
| 异常检测 | 基于 ML 的动态基线和异常告警 |
| 容量规划 | 假设分析、剩余时间预测、容量预测 |
| 右规格建议 | 每 VM 的 CPU/内存调整建议 |
| 智能告警 | 根因分析、修复建议 |

> REST API，端点 `/suite-api/`。VCF 9.0 中已更名为 VCF Operations。

### 9. vSphere Kubernetes Service (VKS)

| 功能 | 说明 |
|------|------|
| 列出集群 | Tanzu K8s 集群及阶段状态 |
| 集群健康 | 基础设施就绪、控制面可用、工作节点状态 |
| 扩缩容 | 调整 MachineDeployment 工作节点副本数 |
| 节点状态 | 节点就绪/异常计数 |

> 通过 kubectl/kubeconfig 使用 Kubernetes 原生 API。VKS 3.6+ 基于 Cluster API 规范。

### 10. 安全特性

| 功能 | 说明 |
|------|------|
| 预演模式（Dry-Run） | 任何破坏性命令加 `--dry-run` 可预览 API 调用而不执行，便于信任验证 |
| Plan → Confirm → Execute → Log | 结构化工作流：展示当前状态、确认变更、执行、审计日志 |
| 双重确认 | 所有破坏性操作（关机、删除、配置变更、快照恢复/删除、克隆、迁移）需连续两次确认，无绕过参数 |
| 拒绝记录 | 用户拒绝的操作也会记录到审计日志，便于安全审计 |
| 审计日志 | 所有操作记录到 `~/.vmware-aiops/audit.log`（JSONL），包含操作前后状态 |
| 输入校验 | VM 名称长度/格式、CPU（1-128）、内存（128-1048576 MB）、磁盘（1-65536 GB）参数校验 |
| 密码保护 | 通过 `.env` 加载密码并检查文件权限（warn if not 600），不出现在 shell 历史 |
| 配置文件内容 | `config.yaml` 仅存储主机名、端口和 `.env` 引用路径，**不含密码或 Token** |
| SSL 自签名 | 仅用于 ESXi 自签名证书的隔离实验环境；生产环境应使用 CA 签名证书 |
| Prompt 注入防护 | vSphere 事件消息和主机日志在输出前进行截断、控制字符清理和边界标记（`[VSPHERE_EVENT]`/`[VSPHERE_HOST_LOG]`）包裹 |
| Webhook 数据范围 | **默认禁用**。启用后仅向用户自配置的 URL 发送告警摘要，payload 不含凭据、IP 或 PII |
| 最小权限 | 推荐使用专用 vCenter 服务账户，仅授予所需最小权限。仅需监控时使用 [VMware-Monitor](https://github.com/zw008/VMware-Monitor) |
| 任务等待 | 所有异步操作等待完成并报告结果 |

---

## 支持的 AI 平台

| 平台 | 状态 | 配置文件 | AI 模型 |
|------|------|---------|---------|
| **Claude Code** | ✅ 原生技能 | `skill/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ 扩展 | `gemini-extension/GEMINI.md` | Google Gemini |
| **OpenAI Codex CLI** | ✅ AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ 约定文件 | `codex-skill/AGENTS.md` | 任意（云端 + 本地） |
| **Continue CLI** | ✅ 规则文件 | `codex-skill/AGENTS.md` | 任意（云端 + 本地） |
| **Trae IDE** | ✅ Rules | `trae-rules/project_rules.md` | Claude/DeepSeek/GPT-4o/Doubao |
| **Kimi Code CLI** | ✅ Skill | `kimi-skill/SKILL.md` | Moonshot Kimi |
| **MCP Server** | ✅ MCP 协议 | `mcp_server/` | 任意 MCP 客户端 |
| **Python CLI** | ✅ 独立运行 | N/A | N/A |

### MCP Server 集成（本地 Agent）

vmware-aiops MCP Server 可接入**任何 MCP 兼容的 Agent 或工具**。配置模板见 [`examples/mcp-configs/`](examples/mcp-configs/)。

| Agent / 工具 | 本地模型支持 | 配置模板 | 集成指南 |
|-------------|:----------:|---------|---------|
| **[Goose](https://github.com/block/goose)** | ✅ Ollama, LM Studio | [`goose.json`](examples/mcp-configs/goose.json) | [指南](docs/integrations/goose.md) |
| **[LocalCowork](https://github.com/Liquid4All/localcowork)** | ✅ 完全离线 | [`localcowork.json`](examples/mcp-configs/localcowork.json) | [指南](docs/integrations/localcowork.md) |
| **[mcp-agent](https://github.com/lastmile-ai/mcp-agent)** | ✅ Ollama, vLLM | [`mcp-agent.yaml`](examples/mcp-configs/mcp-agent.yaml) | [指南](docs/integrations/mcp-agent.md) |
| **VS Code Copilot** | — | [`vscode-copilot.json`](examples/mcp-configs/vscode-copilot.json) | [指南](docs/integrations/vscode-copilot.md) |
| **Cursor** | — | [`cursor.json`](examples/mcp-configs/cursor.json) | — |
| **Continue** | ✅ Ollama | [`continue.yaml`](examples/mcp-configs/continue.yaml) | [指南](docs/integrations/continue.md) |
| **Claude Code** | — | [`claude-code.json`](examples/mcp-configs/claude-code.json) | — |

**完全本地运行**（无需云端 API）：

```bash
# Aider + Ollama + vmware-aiops（通过 AGENTS.md）
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

---

## 安装

### 第 0 步：前置条件

```bash
python3 --version   # 需要 Python 3.10+
node --version      # Gemini/Codex CLI 需要 Node.js 18+
```

### 第 1 步：安装 Python 后端

所有平台共用同一个 Python 后端：

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 第 2 步：配置

```bash
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
# 编辑 config.yaml，填入你的 vCenter/ESXi 目标信息
```

通过 `.env` 文件设置密码（推荐）：

```bash
# 使用模板创建 .env 文件
cp .env.example ~/.vmware-aiops/.env

# 编辑并填入真实密码
# 然后锁定文件权限（仅所有者可读写）
chmod 600 ~/.vmware-aiops/.env
```

> **安全提示**：推荐使用 `.env` 文件而非命令行 `export`，避免密码出现在 shell 历史记录中。`.env` 文件必须设置 `chmod 600`（仅所有者可读写）。

密码环境变量命名规则：`VMWARE_{目标名大写}_PASSWORD`
- 连字符替换为下划线，全大写
- 目标 `home-esxi` → `VMWARE_HOME_ESXI_PASSWORD`
- 目标 `prod-vcenter` → `VMWARE_PROD_VCENTER_PASSWORD`

### 安全最佳实践

- **绝不**在脚本或配置文件中硬编码密码
- **绝不**通过命令行参数传递密码（`ps` 命令可见）
- **绝不**在输出或日志中显示密码
- **始终**使用 `~/.vmware-aiops/.env` 并设置 `chmod 600`
- **始终**通过 `config.yaml` 配置连接 — 凭据自动从 `.env` 加载
- **TLS**：默认启用。仅在使用自签名证书的隔离实验环境中才禁用
- **Webhook**：仅向您自己配置的 URL 发送通知，默认不向第三方服务发送数据
- **代码审查**：建议在生产部署前审查[源代码](https://github.com/zw008/VMware-AIops)和提交历史
- **生产环境安全**：生产环境建议使用只读的 [VMware-Monitor](https://github.com/zw008/VMware-Monitor)。AI Agent 可能误解上下文并执行非预期的破坏性操作 — 已有真实案例表明，缺乏隔离的 AI 驱动基础设施工具可能删除生产数据库和整个环境。VMware-Monitor 在代码级别消除此风险：代码库中不存在任何破坏性函数

### 第 3 步：连接 AI 工具

#### Claude Code（推荐）

```bash
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
/vmware-ops:vmware-aiops          # 完整版
/vmware-ops:vmware-monitor        # 只读监控（更安全）
```

#### Gemini CLI

```bash
npm install -g @google/gemini-cli
gemini extensions install ./gemini-extension
gemini
> 显示 ESXi 上所有虚拟机
```

#### Codex CLI

```bash
npm i -g @openai/codex
mkdir -p ~/.codex/skills/vmware-aiops
cp codex-skill/SKILL.md ~/.codex/skills/vmware-aiops/SKILL.md
cp codex-skill/AGENTS.md ./AGENTS.md
codex --enable skills
```

#### Aider（支持本地模型）

```bash
pip install aider-chat
# 云端
aider --conventions codex-skill/AGENTS.md
# 本地 Ollama
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

#### Trae IDE

将规则文件复制到项目的 `.trae/rules/` 目录：

```bash
mkdir -p .trae/rules
cp trae-rules/project_rules.md .trae/rules/project_rules.md
```

Trae IDE 的 Builder Mode 会在启动时自动读取 `.trae/rules/` 下的 Markdown 文件。

> 注意：也可以在 Trae IDE 中安装 Claude Code VS Code 扩展，直接使用 `.claude/skills/` 格式。

#### Kimi Code CLI

```bash
# 复制技能文件到 Kimi skills 目录
mkdir -p ~/.kimi/skills/vmware-aiops
cp kimi-skill/SKILL.md ~/.kimi/skills/vmware-aiops/SKILL.md
```

#### MCP 服务器（Smithery / Glama / Claude Desktop）

MCP 服务器通过 [Model Context Protocol](https://modelcontextprotocol.io) 将 VMware 操作暴露为工具，兼容所有 MCP 客户端（Claude Desktop、Cursor 等）。

```bash
# 直接运行
python -m mcp_server

# 或通过安装的入口点
vmware-aiops-mcp

# 指定配置路径
VMWARE_AIOPS_CONFIG=/path/to/config.yaml python -m mcp_server
```

**Claude Desktop 配置** (`claude_desktop_config.json`)：
```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "VMWARE_AIOPS_CONFIG": "/path/to/config.yaml"
      }
    }
  }
}
```

**通过 Smithery 安装**：
```bash
npx -y @smithery/cli install @zw008/VMware-AIops --client claude
```

---

#### 独立 CLI（无需 AI）

```bash
source .venv/bin/activate
vmware-aiops inventory vms --target home-esxi
vmware-aiops health alarms --target home-esxi
vmware-aiops vm power-on my-vm --target home-esxi
```

---

## 国内云端模型

| 模型 | 说明 | 配合工具 |
|------|------|---------|
| DeepSeek | 性价比高，编程能力强 | Aider / Continue |
| 通义千问 Qwen | 阿里云，有免费额度 | Aider / Continue |
| 豆包 Doubao | 字节跳动 | Aider / Trae IDE |

```bash
# DeepSeek
export DEEPSEEK_API_KEY="your-key"
aider --conventions codex-skill/AGENTS.md --model deepseek/deepseek-coder

# 通义千问
export DASHSCOPE_API_KEY="your-key"
aider --conventions codex-skill/AGENTS.md --model qwen/qwen-coder-plus
```

---

## 本地模型（Aider + Ollama）

完全离线运行，无需云端 API，完全隐私：

```bash
brew install ollama              # macOS
ollama pull qwen2.5-coder:32b   # 下载模型（~20GB）
ollama serve                     # 启动服务

aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

---

## CLI 命令参考

```bash
# 环境诊断
vmware-aiops doctor                   # 检查环境、配置、连通性
vmware-aiops doctor --skip-auth       # 跳过 vSphere 认证检查（更快）

# MCP 配置生成
vmware-aiops mcp-config generate --agent goose        # 生成 Goose 配置
vmware-aiops mcp-config generate --agent claude-code  # 生成 Claude Code 配置
vmware-aiops mcp-config list                          # 列出所有支持的 Agent

# 资源清单
vmware-aiops inventory vms|hosts|datastores|clusters [--target <name>]
vmware-aiops inventory vms --limit 10 --sort-by memory_mb  # 按内存排序 Top 10
vmware-aiops inventory vms --power-state poweredOn         # 只显示开机 VM

# 健康检查
vmware-aiops health alarms [--target <name>]
vmware-aiops health events --hours 24 --severity warning [--target <name>]

# 虚拟机操作
vmware-aiops vm info|power-on|power-off|reset|suspend <vm-name>
vmware-aiops vm create <name> --cpu 4 --memory 8192 --disk 100
vmware-aiops vm delete <name> --confirm
vmware-aiops vm reconfigure <name> --cpu 4 --memory 8192
vmware-aiops vm snapshot-create|snapshot-list|snapshot-revert|snapshot-delete <name>
vmware-aiops vm clone <name> --new-name <new>
vmware-aiops vm migrate <name> --to-host <host>
vmware-aiops vm set-ttl <name> --minutes 60     # 60 分钟后自动删除
vmware-aiops vm cancel-ttl <name>              # 取消 TTL
vmware-aiops vm list-ttl                       # 查看所有 TTL
vmware-aiops vm clean-slate <name> --snapshot baseline  # 恢复基线快照（双重确认）

# Guest Operations（需要 VMware Tools）
vmware-aiops vm guest-exec my-vm --cmd /bin/bash --args "-c 'whoami'" --user root
vmware-aiops vm guest-upload my-vm --local ./script.sh --guest /tmp/script.sh --user root
vmware-aiops vm guest-download my-vm --guest /var/log/syslog --local ./syslog.txt --user root

# Plan → Apply（多步操作编排）
vmware-aiops plan list                                # 查看待执行/失败的 plan

# 部署
vmware-aiops deploy ova ./ubuntu.ova --name my-vm --datastore ds1      # 从 OVA 部署
vmware-aiops deploy template golden-ubuntu --name new-vm               # 从模板部署
vmware-aiops deploy linked-clone --source base-vm --snapshot clean --name test-vm  # 链接克隆（秒级）
vmware-aiops deploy iso my-vm --iso "[datastore1] iso/ubuntu-22.04.iso"  # 挂载 ISO
vmware-aiops deploy mark-template golden-vm                            # 转为模板
vmware-aiops deploy batch-clone --source base-vm --count 5 --prefix lab  # 批量克隆
vmware-aiops deploy batch deploy.yaml                                  # 从 YAML 批量部署

# 数据存储
vmware-aiops datastore browse datastore1 --path "iso/"                 # 浏览数据存储
vmware-aiops datastore scan-images --target home-esxi                  # 扫描所有数据存储的镜像
vmware-aiops datastore images --type iso                               # 列出缓存的镜像

# 扫描与守护进程
vmware-aiops scan now [--target <name>]
vmware-aiops daemon start|stop|status

# vSAN 管理
vmware-aiops vsan health [--target <name>]
vmware-aiops vsan capacity [--target <name>]
vmware-aiops vsan disks [--target <name>]
vmware-aiops vsan performance [--hours 1] [--target <name>]

# Aria Operations / VCF Operations
vmware-aiops ops alerts [--severity critical] [--target <name>]
vmware-aiops ops metrics <resource-name> [--hours 24]
vmware-aiops ops recommendations [--target <name>]
vmware-aiops ops capacity <cluster-name> [--target <name>]

# vSphere Kubernetes Service (VKS)
vmware-aiops vks clusters [--namespace default]
vmware-aiops vks health <cluster-name>
vmware-aiops vks scale <machine-deployment> --replicas <n>
vmware-aiops vks nodes <cluster-name>
```

---

## 项目结构

```
VMware-AIops/
├── .claude-plugin/                # Claude Code 市场清单
├── plugins/vmware-ops/            # Claude Code 插件
│   └── skills/
│       ├── vmware-aiops/SKILL.md  # 完整运维技能
│       └── vmware-monitor/SKILL.md # 只读监控技能
├── vmware_aiops/                  # Python 后端
│   ├── config.py                  # 配置管理
│   ├── connection.py              # 多目标连接（pyVmomi）
│   ├── cli.py                     # CLI（双重确认）
│   ├── ops/                       # 运维操作
│   │   ├── inventory.py           # VM、主机、数据存储、集群
│   │   ├── health.py              # 告警、事件、传感器
│   │   ├── vm_lifecycle.py        # VM 生命周期管理
│   │   ├── vm_deploy.py           # OVA、模板、链接克隆、批量部署
│   │   └── datastore_browser.py   # 数据存储浏览、镜像发现
│   ├── scanner/                   # 日志扫描守护进程
│   └── notify/                    # 通知（JSONL + Webhook）
├── skill/SKILL.md                 # Claude Code 独立技能
├── gemini-extension/GEMINI.md     # Gemini CLI 扩展
├── codex-skill/AGENTS.md          # Codex / Aider / Continue
├── trae-rules/project_rules.md    # Trae IDE 规则
├── kimi-skill/SKILL.md            # Kimi Code CLI 技能
├── mcp_server/                    # MCP 服务器
│   ├── server.py                  # MCP 工具定义
│   └── __main__.py                # 入口
├── smithery.yaml                  # Smithery 市场配置
├── config.example.yaml
└── pyproject.toml
```

## 相关项目

| 项目 | 说明 | 安装 |
|------|------|------|
| **[VMware-Monitor](https://github.com/zw008/VMware-Monitor)** | 只读监控 — 代码级安全，零破坏性操作 | `clawhub install vmware-monitor` |
| **VMware-AIops**（本仓库） | 完整 AI 运维 — 监控 + VM 生命周期管理 | `clawhub install vmware-aiops` |

> **如何选择**：如果只需要只读监控且不想有任何意外修改风险，使用 **VMware-Monitor**。如果需要完整运维能力（创建、删除、开关机、快照、克隆、迁移），使用 **VMware-AIops**。

---

## 问题反馈与贡献

如果遇到任何报错或问题，请将错误信息、日志或截图发送至 **zhouwei008@gmail.com**。欢迎加入我们，一起维护和改进这个项目！

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this project!

## 许可证

MIT
