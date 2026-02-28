# Contributing to VMware AIops

Thank you for your interest in contributing to VMware AIops! This guide will help you get started.

## How to Contribute

### Reporting Bugs

If you find a bug, please [open an issue](https://github.com/zw008/VMware-AIops/issues/new?template=bug_report.yml) with:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (Python version, vSphere version, OS)
- Error messages or logs (with passwords redacted)

### Suggesting Features

Have an idea? [Open a feature request](https://github.com/zw008/VMware-AIops/issues/new?template=feature_request.yml) and describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Set up the development environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Make your changes** and write tests if applicable
5. **Test your changes**:
   ```bash
   pytest
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add support for new feature"
   ```
7. **Push** and open a Pull Request

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `refactor:` — Code refactoring
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

## Development Guidelines

### Code Style

- Follow PEP 8 conventions
- Use type annotations on function signatures
- Keep functions focused and small

### Security

- **NEVER** hardcode passwords or credentials in code
- **NEVER** log or print sensitive information
- **ALWAYS** use `ConnectionManager.from_config()` for connections
- **ALWAYS** store credentials in `~/.vmware-aiops/.env`

### Testing

- Test against both vCenter and standalone ESXi when possible
- Mock pyVmomi objects for unit tests
- Redact all credentials in test fixtures

## Adding Support for New AI Platforms

VMware AIops supports multiple AI platforms. To add a new one:

1. Create a directory for the platform config (e.g., `new-platform/`)
2. Write the platform-specific skill/rules file
3. Add setup instructions to the README
4. Test with the actual platform

## Getting Help

- Email: zhouwei008@gmail.com
- [Open an issue](https://github.com/zw008/VMware-AIops/issues) for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
