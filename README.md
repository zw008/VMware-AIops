# VMware AIops

AI-powered VMware vCenter/ESXi monitoring and operations tool.

AI 驱动的 VMware vCenter/ESXi 监控与运维工具。

Two modes of operation / 两种使用模式:
- **Claude Code Skill**: Natural language VMware infrastructure management via Claude / 通过 Claude 自然语言管理 VMware 基础设施
- **CLI + Daemon**: Standalone Python tool for operations and scheduled log/alarm scanning / 独立 Python 工具，支持运维操作和定时日志/告警扫描

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

## Installation / 安装

### Option A: Claude Code Skill (Natural Language Ops) / 方式 A：Claude Code 技能（自然语言运维）

```bash
# Step 1: Clone the marketplace repository
# 第 1 步：克隆市场仓库
git clone https://github.com/zw008/VMware-AIops.git \
  ~/.claude/plugins/marketplaces/vmware-aiops

# Step 2: Register the marketplace
# 第 2 步：注册市场
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

# Step 3: Enable the plugin
# 第 3 步：启用插件
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/settings.json'
d = json.loads(f.read_text()) if f.exists() else {}
d.setdefault('enabledPlugins', {})['vmware-ops@vmware-aiops'] = True
f.write_text(json.dumps(d, indent=2))
print('Plugin enabled.')
"
```

Then restart Claude Code. / 然后重启 Claude Code。

After restart, the Skill will first ask which environment you want to manage: / 重启后，技能会先询问你要管理哪个环境：

```
You: "I want to check the VMware environment"
你: "我要查看 VMware 环境"

Claude: "Which environment do you want to manage?
  1. vCenter Server (e.g. vcenter-prod.example.com)
  2. Standalone ESXi host (e.g. 192.168.1.100)
  Please provide the target name from your config, or the host address."

Claude: "你要管理哪个环境？
  1. vCenter Server（如 vcenter-prod.example.com）
  2. 独立 ESXi 主机（如 192.168.1.100）
  请提供配置中的目标名称或主机地址。"
```

Example commands after connecting / 连接后的示例命令:
```
"Show me all VMs"               → "显示所有虚拟机"
"Are there any active alarms?"  → "有没有活跃的告警？"
"Take a snapshot of prod-db"    → "给 prod-db 打个快照"
"Power off test-vm gracefully"  → "优雅关闭 test-vm"
"How much free space left?"     → "存储还有多少可用空间？"
"Scan logs for errors"          → "扫描日志中的错误"
```

### Option B: Python CLI + Daemon / 方式 B：Python CLI + 守护进程

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configure (Required for Both) / 配置（两种方式都需要）

```bash
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
# Edit config.yaml with your vCenter/ESXi targets
# 编辑 config.yaml，填入你的 vCenter/ESXi 目标信息
```

Set passwords via `.env` file (recommended) / 通过 `.env` 文件设置密码（推荐）:
```bash
# Create .env file with restricted permissions
# 创建 .env 文件并限制权限
cat > ~/.vmware-aiops/.env << 'EOF'
VMWARE_PROD_VCENTER_PASSWORD=your-password
VMWARE_LAB_ESXI_PASSWORD=your-password
EOF
chmod 600 ~/.vmware-aiops/.env
```

Or via environment variables / 或通过环境变量:
```bash
export VMWARE_PROD_VCENTER_PASSWORD="your-password"
```

> **Security note / 安全提示**: Prefer `.env` file over command-line `export` to avoid passwords appearing in shell history. / 推荐使用 `.env` 文件而非命令行 `export`，避免密码出现在 shell 历史记录中。

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
vmware_aiops/
├── config.py          # YAML + env var config / 配置管理（YAML + 环境变量 + .env）
├── connection.py      # Multi-target pyVmomi connection / 多目标 pyVmomi 连接管理
├── cli.py             # Typer CLI with double confirmation / CLI 入口（含双重确认）
├── ops/
│   ├── inventory.py   # VMs, hosts, datastores, clusters / 资源清单查询
│   ├── health.py      # Alarms, events, hardware / 健康检查
│   └── vm_lifecycle.py # Create, delete, power, snapshot / 虚拟机生命周期管理
├── scanner/
│   ├── log_scanner.py    # Event + syslog scanning / 事件与日志扫描
│   ├── alarm_scanner.py  # Triggered alarm scanning / 告警扫描
│   └── scheduler.py      # APScheduler daemon / 定时调度守护进程
└── notify/
    ├── logger.py      # JSONL structured logging / 结构化日志
    └── webhook.py     # Generic webhook sender / Webhook 通知
```

## API Coverage / API 覆盖

Built on **pyVmomi** (vSphere Web Services API / SOAP). / 基于 **pyVmomi**（vSphere SOAP API）构建。

Key managed objects / 核心管理对象:

- `vim.VirtualMachine` — VM lifecycle and configuration / 虚拟机生命周期与配置
- `vim.HostSystem` — ESXi host management / ESXi 主机管理
- `vim.Datastore` — Storage / 存储管理
- `vim.ClusterComputeResource` — Cluster configuration (DRS, HA) / 集群配置
- `vim.Network` — Networking / 网络管理
- `vim.alarm.AlarmManager` — Alarm management / 告警管理
- `vim.event.EventManager` — Event/log queries / 事件与日志查询

## License / 许可证

MIT
