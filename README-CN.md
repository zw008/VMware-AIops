# VMware AIops

[English](README.md) | 中文

AI 驱动的 VMware vCenter/ESXi 监控与运维工具。

> **提供两个技能版本：**
>
> | 技能 | 命令 | 使用场景 |
> |------|------|---------|
> | **vmware-monitor**（安全版） | `/vmware-ops:vmware-monitor` | 只读监控：资源清单、健康检查、告警、指标查询。不会误操作。 |
> | **vmware-aiops**（完整版） | `/vmware-ops:vmware-aiops` | 完整运维：监控全部功能 + 开关机、创建/删除 VM、快照、克隆、迁移。 |

[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-AIops)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-AIops)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 快速安装（推荐）

支持 Claude Code、Cursor、Codex、Gemini CLI、Trae 等 30+ AI 工具：

```bash
npx skills add zw008/VMware-AIops
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

### 4. 定时扫描与通知

| 功能 | 说明 |
|------|------|
| 守护进程 | 基于 APScheduler，可配置间隔（默认 15 分钟） |
| 多目标扫描 | 依次扫描所有配置的 vCenter/ESXi 目标 |
| 日志分析 | 正则匹配：error, fail, critical, panic, timeout, corrupt |
| 结构化日志 | JSONL 输出到 `~/.vmware-aiops/scan.log` |
| Webhook 通知 | 支持 Slack、Discord 或任意 HTTP 端点 |

### 5. vSAN 管理

| 功能 | 说明 |
|------|------|
| 健康检查 | 集群健康总览、分组测试结果 |
| 容量监控 | 总容量、可用、已用及趋势预测 |
| 磁盘组 | 每主机缓存 SSD + 容量盘列表 |
| 性能指标 | 集群/主机/VM 级别的 IOPS、延迟、吞吐 |

> 需要 pyVmomi 8.0.3+（vSAN SDK 已合并）。旧版本需单独安装 vSAN Management SDK。

### 6. Aria Operations / VCF Operations

| 功能 | 说明 |
|------|------|
| 历史指标 | 时序 CPU、内存、磁盘、网络，保留数月历史 |
| 异常检测 | 基于 ML 的动态基线和异常告警 |
| 容量规划 | 假设分析、剩余时间预测、容量预测 |
| 右规格建议 | 每 VM 的 CPU/内存调整建议 |
| 智能告警 | 根因分析、修复建议 |

> REST API，端点 `/suite-api/`。VCF 9.0 中已更名为 VCF Operations。

### 7. vSphere Kubernetes Service (VKS)

| 功能 | 说明 |
|------|------|
| 列出集群 | Tanzu K8s 集群及阶段状态 |
| 集群健康 | 基础设施就绪、控制面可用、工作节点状态 |
| 扩缩容 | 调整 MachineDeployment 工作节点副本数 |
| 节点状态 | 节点就绪/异常计数 |

> 通过 kubectl/kubeconfig 使用 Kubernetes 原生 API。VKS 3.6+ 基于 Cluster API 规范。

### 8. 安全特性

| 功能 | 说明 |
|------|------|
| Plan → Confirm → Execute → Log | 结构化工作流：展示当前状态、确认变更、执行、审计日志 |
| 双重确认 | 关机、删除、调整配置需连续两次确认 |
| 审计日志 | 所有操作记录到 `~/.vmware-aiops/audit.log`（JSONL），包含操作前后状态 |
| 密码保护 | 通过 `.env` 加载密码，不会出现在 shell 历史 |
| SSL 自签名 | 适配 ESXi 8.0 自签名证书 |
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
- **始终**使用 `ConnectionManager.from_config()` 建立连接
- 密码在模块导入时自动从 `.env` 加载，无需手动 `export`

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
# 资源清单
vmware-aiops inventory vms|hosts|datastores|clusters [--target <name>]

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

## 问题反馈与贡献

如果遇到任何报错或问题，请将错误信息、日志或截图发送至 **zhouwei008@gmail.com**。欢迎加入我们，一起维护和改进这个项目！

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this project!

## 许可证

MIT
