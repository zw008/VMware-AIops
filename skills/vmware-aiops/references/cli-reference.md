# CLI Reference

```bash
# Diagnostics
vmware-aiops doctor [--skip-auth]

# MCP Config Generator
vmware-aiops mcp-config generate --agent <goose|cursor|claude-code|continue|vscode-copilot|localcowork|mcp-agent>
vmware-aiops mcp-config list

# VM Operations
vmware-aiops vm power-on <vm-name>
vmware-aiops vm power-off <vm-name> [--force]
vmware-aiops vm create <name> [--cpu <n>] [--memory <mb>] [--disk <gb>]
vmware-aiops vm delete <vm-name>
vmware-aiops vm reconfigure <vm-name> [--cpu <n>] [--memory <mb>]
vmware-aiops vm snapshot-create <vm-name> --name <snap-name>
vmware-aiops vm snapshot-list <vm-name>
vmware-aiops vm snapshot-revert <vm-name> --name <snap-name>
vmware-aiops vm snapshot-delete <vm-name> --name <snap-name>
vmware-aiops vm clone <vm-name> --new-name <name>
vmware-aiops vm migrate <vm-name> --to-host <host>
vmware-aiops vm set-ttl <vm-name> --minutes <n>
vmware-aiops vm cancel-ttl <vm-name>
vmware-aiops vm list-ttl
vmware-aiops vm clean-slate <vm-name> [--snapshot baseline]

# Guest Operations (requires VMware Tools)
vmware-aiops vm guest-exec <vm-name> --cmd /bin/bash --args "-c 'ls -la /tmp'" --user root
vmware-aiops vm guest-upload <vm-name> --local ./script.sh --guest /tmp/script.sh --user root
vmware-aiops vm guest-download <vm-name> --guest /var/log/syslog --local ./syslog.txt --user root

# Plan → Apply (multi-step operations)
vmware-aiops plan list

# Deploy
vmware-aiops deploy ova <path> --name <vm-name> [--datastore <ds>] [--network <net>]
vmware-aiops deploy template <template-name> --name <vm-name> [--datastore <ds>]
vmware-aiops deploy linked-clone --source <vm> --snapshot <snap> --name <new-name>
vmware-aiops deploy iso <vm-name> --iso "[datastore] path/file.iso"
vmware-aiops deploy mark-template <vm-name>
vmware-aiops deploy batch-clone --source <vm> --count <n> [--prefix <prefix>]
vmware-aiops deploy batch <spec.yaml>

# Cluster
vmware-aiops cluster info <name>
vmware-aiops cluster create <name> [--ha] [--drs] [--drs-behavior fullyAutomated|partiallyAutomated|manual] [--datacenter <dc>]
vmware-aiops cluster delete <name>
vmware-aiops cluster add-host <cluster> --host <hostname>
vmware-aiops cluster remove-host <cluster> --host <hostname>
vmware-aiops cluster configure <name> [--ha/--no-ha] [--drs/--no-drs] [--drs-behavior <behavior>]

# Datastore
vmware-aiops datastore browse <ds-name> [--path <subdir>]
vmware-aiops datastore scan-images [--target <name>]

# Scanning & Daemon
vmware-aiops scan now [--target <name>]
vmware-aiops daemon start
vmware-aiops daemon stop
vmware-aiops daemon status

# Moved to companion skills:
# vmware-monitor inventory vms/hosts/datastores/clusters, health alarms/events, vm info
# vmware-storage iscsi-enable/status/add-target/remove-target, rescan, vsan health/capacity
# vmware-vks list-namespaces, create-tkc, scale-tkc, etc.
```
