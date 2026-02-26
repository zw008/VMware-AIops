# Release Notes / 版本发布历史

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
