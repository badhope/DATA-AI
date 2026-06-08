# Contributing to DATA-AI

Thank you for your interest in contributing to DATA-AI! This document provides guidelines and instructions for contributing.

## 🚀 Quick Start

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up development environment**
4. **Create a branch** for your changes
5. **Make your changes** and commit
6. **Push to your fork** and create a Pull Request

## 📋 Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment (recommended)

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/badhope/DATA-AI.git
cd DATA-AI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests to verify setup
pytest tests/ -v
```

## 🏗️ Project Structure

```
DATA-AI/
├── src/data_ai/          # Main source code
│   ├── core/             # Core engine modules
│   ├── cli/              # Command-line interface
│   ├── plugins/          # Plugin system
│   └── utils/            # Utility functions
├── tests/                # Test suite
├── docs/                 # Documentation
├── examples/             # Example usage
└── config/               # Configuration examples
```

## 📝 Coding Standards

### Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check . --fix
```

### Type Hints

All code should include type hints:

```python
def process_data(data: dict[str, Any]) -> list[Result]:
    """Process input data and return results."""
    results: list[Result] = []
    # ... implementation
    return results
```

### Documentation

- Use docstrings for all public functions, classes, and modules
- Follow Google-style docstrings
- Include type information in docstrings

```python
def example_function(param1: str, param2: int) -> bool:
    """Short description of the function.

    Longer description if needed, explaining the purpose
    and behavior of the function.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When input is invalid

    Example:
        >>> example_function("test", 42)
        True
    """
    pass
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/data_ai

# Run specific test file
pytest tests/test_core.py

# Run with verbose output
pytest -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern
- Use fixtures for common setup

```python
def test_intent_recognition_basic():
    """Test basic intent recognition functionality."""
    # Arrange
    recognizer = IntentRecognizer()
    
    # Act
    result = recognizer.recognize("Search for Python tutorials")
    
    # Assert
    assert result.intent_type == IntentType.WEB_SEARCH
    assert result.confidence > 0.8
```

## 🔄 Pull Request Process

1. **Update documentation** for any changed functionality
2. **Add tests** for new features
3. **Ensure all tests pass**
4. **Update CHANGELOG.md** with your changes
5. **Create a Pull Request** with a clear description

### PR Title Format

- `feat: Add new feature`
- `fix: Fix specific bug`
- `docs: Update documentation`
- `test: Add or update tests`
- `refactor: Code refactoring`
- `perf: Performance improvements`

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
Describe the tests you ran

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
- [ ] I have updated the documentation accordingly
```

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Minimal steps to reproduce
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: Python version, OS, etc.
6. **Logs**: Relevant error messages or logs

## 💡 Feature Requests

Feature requests are welcome! Please:

1. Check if the feature has already been requested
2. Provide a clear use case
3. Explain why this feature would be useful

## 🏷️ Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: Add new feature`
- `fix: Fix specific bug`
- `docs: Update documentation`
- `style: Formatting changes`
- `refactor: Code restructuring`
- `test: Add or update tests`
- `chore: Maintenance tasks`

## 📜 Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## ❓ Questions?

- Open an [issue](https://github.com/badhope/DATA-AI/issues)
- Start a [discussion](https://github.com/badhope/DATA-AI/discussions)

## 🙏 Thank You!

Your contributions make DATA-AI better for everyone!
