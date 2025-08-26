# Contributing to PMCP

Thank you for your interest in contributing to PMCP! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Reporting Issues
- Use the [GitHub Issues](https://github.com/NoobyNull/PMCP/issues) page
- Search existing issues before creating a new one
- Provide detailed information including:
  - Steps to reproduce
  - Expected vs actual behavior
  - System information (OS, Python version, etc.)
  - Relevant log files

### Suggesting Features
- Open a [GitHub Discussion](https://github.com/NoobyNull/PMCP/discussions) for feature requests
- Describe the use case and expected behavior
- Consider implementation complexity and maintenance burden

### Code Contributions

#### Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/PMCP.git
   cd PMCP
   ```
3. Set up development environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```
4. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

#### Code Standards
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable and function names

#### Testing
- Write tests for new functionality
- Ensure existing tests pass:
  ```bash
  pytest
  ```
- Test both success and error cases
- Include integration tests for API endpoints

#### Documentation
- Update relevant documentation files
- Add docstrings to new functions/classes
- Update README.md if adding new features
- Include examples in docstrings

#### Pull Request Process
1. Ensure your code follows the style guidelines
2. Add or update tests as needed
3. Update documentation
4. Commit with clear, descriptive messages:
   ```bash
   git commit -m "feat: add new MCP plugin management feature"
   ```
5. Push to your fork and create a pull request
6. Fill out the pull request template completely
7. Respond to review feedback promptly

## 🏗️ Project Structure

```
PMCP/
├── admin/                  # Web admin interface
│   ├── static/            # CSS, JS, images
│   └── templates/         # HTML templates
├── config/                # Configuration files
├── src/                   # Core application code
│   ├── api/              # API routes and endpoints
│   ├── auth/             # Authentication system
│   ├── models/           # Data models
│   ├── services/         # Business logic services
│   └── utils/            # Utility functions
├── scripts/              # Setup and utility scripts
├── tests/                # Test files
└── docs/                 # Documentation
```

## 🎯 Development Guidelines

### Adding New Features
1. **Plan First**: Discuss major features in GitHub Discussions
2. **Start Small**: Break large features into smaller, manageable PRs
3. **Test Thoroughly**: Include unit and integration tests
4. **Document**: Update relevant documentation
5. **Review**: Request reviews from maintainers

### Bug Fixes
1. **Reproduce**: Ensure you can reproduce the issue
2. **Test**: Add tests that would have caught the bug
3. **Fix**: Implement the minimal fix needed
4. **Verify**: Ensure the fix works and doesn't break other functionality

### Code Review Process
- All changes require review from at least one maintainer
- Reviews focus on:
  - Code quality and style
  - Test coverage
  - Documentation completeness
  - Security considerations
  - Performance impact

## 🔧 Development Tools

### Recommended Tools
- **IDE**: VS Code with Python extension
- **Linting**: pylint, black, isort
- **Testing**: pytest, pytest-asyncio
- **Documentation**: Sphinx (for API docs)

### Pre-commit Hooks
Consider setting up pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

## 📋 Commit Message Guidelines

Use conventional commit format:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add MCP plugin auto-discovery
fix: resolve memory leak in context management
docs: update installation instructions
```

## 🚀 Release Process

1. Version bumping follows semantic versioning (SemVer)
2. Releases are created from the main branch
3. Release notes are generated from commit messages
4. Docker images are built and published automatically

## 📞 Getting Help

- **Questions**: Use [GitHub Discussions](https://github.com/NoobyNull/PMCP/discussions)
- **Chat**: Join our community chat (link in README)
- **Documentation**: Check the [project wiki](https://github.com/NoobyNull/PMCP/wiki)

## 🙏 Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing to PMCP! 🚀
