# Release Notes / 版本发布历史

---

## v0.4.1 — 2026-02-26

### Improvements / 改进

- **Secure credential management / 安全凭据管理**: Added `.env.example` template with naming convention (`VMWARE_{TARGET_NAME}_PASSWORD`) and `chmod 600` instructions. Users can now `cp .env.example ~/.vmware-aiops/.env` for quick setup.
  新增 `.env.example` 凭据模板，包含命名规则和 `chmod 600` 说明，用户可快速复制使用。

- **First-run configuration guide / 首次配置引导**: SKILL.md now includes a 3-step setup guide (check config.yaml → check .env → verify connection) for new users.
  SKILL.md 新增 3 步配置引导流程，帮助新用户快速上手。

- **Credential security rules / 凭据安全规则**: Added explicit NEVER/ALWAYS rules to SKILL.md — never hardcode passwords, never display passwords in output, always use `ConnectionManager.from_config()`.
  SKILL.md 新增明确的安全规则——禁止硬编码密码、禁止在输出中显示密码、始终使用 `ConnectionManager.from_config()`。

- **Output sanitization / 输出脱敏**: Connection info displays only host, username, and type — passwords are never shown in any output or logs.
  连接信息仅显示主机、用户名和类型，密码永远不会出现在任何输出或日志中。

- **Security best practices in README / README 安全最佳实践**: Added security best practices section to both English and Chinese READMEs.
  中英文 README 均新增安全最佳实践章节。

### Files Added / 新增文件

- `.env.example` — Credential template with naming convention and security instructions

### Files Updated / 更新文件

- `config.example.yaml` — Added `.env` setup guidance comments
- `skill/SKILL.md` — Rewritten with first-run guide, credential security rules, output sanitization
- `plugins/vmware-ops/skills/vmware-aiops/SKILL.md` — Synced with `skill/SKILL.md`
- `README.md` — Updated password setup to use `.env.example`, added security best practices
- `README-CN.md` — Same updates in Chinese

---

## v0.4.0 — 2026-02-26

### New Features / 新功能

- **vSAN Management / vSAN 管理**: Added vSAN health check, capacity monitoring, disk group listing, and performance metrics via pyVmomi 8u3+ integrated vSAN SDK.
  新增 vSAN 健康检查、容量监控、磁盘组列表、性能指标（通过 pyVmomi 8u3+ 内置 vSAN SDK）。

- **Aria Operations / VCF Operations 集成**: Added REST API integration for `/suite-api/` — historical metrics, ML anomaly detection, capacity planning, right-sizing recommendations, intelligent alerts with root cause analysis.
  新增 Aria Operations REST API 集成——历史指标、ML 异常检测、容量规划、右规格建议、根因分析智能告警。

- **vSphere Kubernetes Service (VKS) / Kubernetes 服务**: Added Tanzu Kubernetes cluster management — list clusters, health checks (InfrastructureReady/ControlPlaneAvailable/WorkersAvailable), scale workers, node status.
  新增 Tanzu Kubernetes 集群管理——列出集群、健康检查、扩缩容、节点状态。

### New CLI Commands / 新增命令

```bash
# vSAN
vmware-aiops vsan health|capacity|disks|performance [--target <name>]

# Aria Operations / VCF Operations
vmware-aiops ops alerts|metrics|recommendations|capacity [--target <name>]

# VKS
vmware-aiops vks clusters|health|scale|nodes
```

- **MCP Server / MCP 服务器**: Added `mcp_server/` package wrapping VMware operations as MCP tools (list VMs/hosts/datastores/clusters, alarms, events, VM power on/off, VM info). Enables registration on Smithery, Glama, and MCP Server Registry.
  新增 MCP 服务器，将 VMware 操作封装为 MCP 工具，支持注册到 Smithery、Glama 和 MCP Server Registry。

- **Smithery Integration / Smithery 集成**: Added `smithery.yaml` for one-click install via `npx @smithery/cli install`.
  新增 Smithery 配置文件，支持一键安装。

- **Marketplace Publishing / 市场发布**: Prepared for PyPI (`pip install vmware-aiops`), SkillsMP (skills.sh), Smithery, Glama, and MCP Server Registry.
  准备发布到 PyPI、SkillsMP、Smithery、Glama 和 MCP Server Registry。

### Files Updated / 更新文件

- All skill files updated with vSAN, Aria Operations, and VKS sections:
  `skill/SKILL.md`, `codex-skill/AGENTS.md`, `gemini-extension/GEMINI.md`,
  `trae-rules/project_rules.md`, `kimi-skill/SKILL.md`,
  `plugins/vmware-ops/skills/vmware-aiops/SKILL.md`
- `README.md` — Added capabilities sections 6-8 (vSAN, Aria Ops, VKS) and CLI commands
- `README-CN.md` — Same updates in Chinese
- `plugins/vmware-ops/.claude-plugin/plugin.json` — Version 0.3.0 → 0.4.0
- `.claude-plugin/marketplace.json` — Version 0.2.0 → 0.4.0
- `pyproject.toml` — Version 0.1.0 → 0.4.0, added `mcp[cli]` dependency and `vmware-aiops-mcp` entry point
- `README.md` / `README-CN.md` — Added MCP server section, updated platform table and project structure

### Files Added / 新增文件

- `mcp_server/__init__.py`
- `mcp_server/server.py` — FastMCP server exposing 9 VMware tools
- `mcp_server/__main__.py` — `python -m mcp_server` entry point
- `smithery.yaml` — Smithery marketplace configuration

### API References / API 参考

- vSAN Management SDK: https://developer.broadcom.com/sdks/vsan-management-sdk-for-python/latest/
- Aria Operations API: https://developer.broadcom.com/xapis/vmware-aria-operations-api/latest/
- VKS API: https://developer.broadcom.com/xapis/vmware-vsphere-kubernetes-service/3.6.0/api-docs.html
- VCF 9.0 API Spec: https://developer.broadcom.com/sdks/vcf-api-specification/latest/

---

## v0.3.0 — 2026-02-26

### New Features / 新功能

- **Trae IDE support / Trae IDE 支持**: Added `trae-rules/project_rules.md` for Trae IDE's Builder Mode. Copy to `.trae/rules/` to use with Claude, DeepSeek, GPT-4o, or Doubao models.
  添加 Trae IDE 规则文件，复制到 `.trae/rules/` 即可使用 Claude、DeepSeek、GPT-4o 或豆包模型。

- **Kimi Code CLI support / Kimi Code CLI 支持**: Added `kimi-skill/SKILL.md` for Moonshot Kimi Code CLI. Copy to `~/.kimi/skills/vmware-aiops/`.
  添加 Kimi Code CLI 技能文件，复制到 `~/.kimi/skills/vmware-aiops/`。

- **Version compatibility matrix / 版本兼容矩阵**: Documented support for vSphere 6.5, 6.7, 7.0, and 8.0 across all skill files and README. pyVmomi auto-negotiates API version during SOAP handshake.
  记录了 vSphere 6.5–8.0 版本兼容性。pyVmomi 在 SOAP 握手阶段自动协商 API 版本。

- **Bilingual README / 中英文 README**: Split into `README.md` (English) and `README-CN.md` (Chinese) with language switcher.
  拆分为英文 README.md 和中文 README-CN.md，带语言切换链接。

### Changes / 变更

- Updated architecture diagram to include Trae IDE and Kimi Code CLI.
  更新架构图，加入 Trae IDE 和 Kimi Code CLI。

- Added version-specific notes to all skill/rules files:
  - vSphere 8.0: `CreateSnapshot_Task` deprecated → use `CreateSnapshotEx_Task`
  - vSphere 8.0: `SmartConnectNoSSL()` removed → use `SmartConnect(disableSslCertValidation=True)`
  - vSphere 7.0: All standard APIs fully supported

  为所有技能/规则文件添加版本特定说明。

- Plugin version bumped to 0.3.0.
  插件版本升级到 0.3.0。

### Files Added / 新增文件

- `trae-rules/project_rules.md`
- `kimi-skill/SKILL.md`
- `README-CN.md`
- `RELEASE_NOTES.md`

### Files Updated / 更新文件

- `README.md` — English-only, added Trae/Kimi platforms, version compatibility, updated project structure
- `skill/SKILL.md` — Added version compatibility section
- `codex-skill/AGENTS.md` — Added version compatibility section
- `gemini-extension/GEMINI.md` — Added version compatibility section
- `plugins/vmware-ops/.claude-plugin/plugin.json` — Version 0.2.0 → 0.3.0

---

## v0.2.0 — 2026-02-25

### New Features / 新功能

- **Claude Code Marketplace plugin / Claude Code 市场插件**: Added `.claude-plugin/marketplace.json` and `plugins/vmware-ops/` for one-click install via `/plugin marketplace add zw008/VMware-AIops`.
  新增 Claude Code 市场插件，支持一键安装。

- **Gemini CLI extension / Gemini CLI 扩展**: Added `gemini-extension/` with `GEMINI.md` and `gemini-extension.json` for Google Gemini CLI integration.
  新增 Gemini CLI 扩展。

- **Multi-platform support / 多平台支持**: Claude Code, Gemini CLI, OpenAI Codex CLI, Aider, Continue CLI all supported via shared Python backend.
  支持 Claude Code、Gemini CLI、OpenAI Codex CLI、Aider、Continue CLI。

- **Chinese cloud models / 国内云端模型**: Documentation for DeepSeek, Qwen (Alibaba), and Doubao (ByteDance).
  新增 DeepSeek、通义千问、豆包的配置文档。

- **Local models / 本地模型**: Aider + Ollama workflow for fully offline operation.
  新增 Aider + Ollama 离线运行方案。

### Core Features / 核心功能

- **Inventory**: List VMs, hosts, datastores, clusters, networks (vCenter + ESXi)
  资源清单：虚拟机、主机、数据存储、集群、网络

- **Health monitoring**: Active alarms, event/log queries (50+ event types), hardware sensors, host services
  健康监控：活跃告警、事件日志查询、硬件传感器、主机服务

- **VM lifecycle**: Power on/off/reset/suspend, create, delete, reconfigure (CPU/memory), snapshots (create/list/revert/delete), clone, vMotion migration
  VM 生命周期：开关机、创建、删除、调整配置、快照、克隆、迁移

- **Scheduled scanning**: APScheduler daemon, multi-target scan, regex log analysis, JSONL output, webhook notifications (Slack/Discord)
  定时扫描：APScheduler 守护进程、多目标扫描、正则日志分析、JSONL 输出、Webhook 通知

- **Safety**: Double confirmation for destructive ops, `.env` password protection, SSL self-signed cert support, async task waiting
  安全特性：双重确认、密码保护、自签名证书支持、异步任务等待

---

## v0.1.0 — 2026-02-24

### Initial Release / 初始发布

- Core Python backend (`vmware_aiops/`) with pyVmomi SOAP API integration.
  核心 Python 后端，集成 pyVmomi SOAP API。

- CLI tool (`vmware-aiops`) with Typer framework.
  基于 Typer 框架的 CLI 工具。

- Claude Code skill file (`skill/SKILL.md`).
  Claude Code 技能文件。

- OpenAI Codex CLI / Aider / Continue shared instructions (`codex-skill/AGENTS.md`).
  OpenAI Codex CLI / Aider / Continue 共用指令文件。

- Multi-target configuration via `~/.vmware-aiops/config.yaml`.
  多目标配置。

- Environment variable password management.
  环境变量密码管理。
