# Contributing to xLights MCP Server

Thanks for your interest in contributing! Here's how to get started.

## Getting Started

1. **Fork** the repository and clone your fork
2. **Install** dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b my-feature
   ```

## Development Workflow

- Make your changes in a feature branch
- Write or update tests as needed
- Run the test suite before submitting:
  ```bash
  pytest
  ```
- Keep commits focused and write clear commit messages

## Submitting Changes

1. Push your branch to your fork
2. Open a **Pull Request** against `main`
3. Describe what your change does and why
4. A maintainer will review your PR — please be patient

## Reporting Bugs

- Use [GitHub Issues](https://github.com/JohnBreault/xlights-mcp-server/issues) to report bugs
- Include steps to reproduce, expected behavior, and actual behavior
- Include your OS, Python version, and xLights version if relevant

## Code Style

- Follow existing code conventions in the project
- Use type hints where possible
- Keep functions focused and well-named

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
