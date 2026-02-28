# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in VMware AIops, please report it responsibly.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, send an email to **zhouwei008@gmail.com** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive an acknowledgment within 48 hours. We will work with you to understand and address the issue before any public disclosure.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | ✅ |
| Older releases | ❌ |

We recommend always using the latest version from the `main` branch.

## Security Best Practices

VMware AIops manages connections to vCenter Server and ESXi hosts. Follow these practices to keep your environment secure:

### Credential Management

- **NEVER** hardcode passwords in scripts, config files, or command-line arguments
- **ALWAYS** store passwords in `~/.vmware-aiops/.env` with `chmod 600` (owner-only access)
- **ALWAYS** use `ConnectionManager.from_config()` for connections — it loads credentials securely from `.env`
- Passwords are never displayed in output, logs, or error messages

### Password Environment Variables

```
VMWARE_{TARGET_NAME}_PASSWORD
# Replace hyphens with underscores, UPPERCASE
# Example: target "home-esxi" → VMWARE_HOME_ESXI_PASSWORD
```

### Network Security

- Connections use SSL/TLS by default
- Self-signed certificate support via `disableSslCertValidation` for lab environments
- For production, use valid SSL certificates and set `verify_ssl: true`

### Destructive Operations

All destructive operations (power-off, delete, reconfigure) require **double confirmation** before execution. This is enforced at the CLI level and cannot be bypassed.

## Scope

The following are considered security issues:

- Credential exposure (passwords appearing in logs, output, or error messages)
- Authentication bypass
- Unauthorized access to vCenter/ESXi operations
- Command injection via CLI inputs
- Insecure default configurations

The following are **not** considered security issues:

- Misconfigured user permissions on vCenter/ESXi (outside this tool's control)
- Vulnerabilities in upstream dependencies (report to the respective project)
- Issues requiring physical access to the host machine
