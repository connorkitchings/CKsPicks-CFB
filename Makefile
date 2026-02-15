.PHONY: help format lint test health check all clean

# Default target
help:
	@echo "CFB Model - Available Commands:"
	@echo ""
	@echo "  make format    - Format code with ruff"
	@echo "  make lint      - Run linter with ruff"
	@echo "  make test      - Run tests with pytest"
	@echo "  make health    - Run full health checks"
	@echo "  make check     - Format + lint + test (alias for 'all')"
	@echo "  make all       - Run all quality checks"
	@echo "  make clean     - Clean cache files"
	@echo ""

# Code formatting
format:
	@echo "🎨 Formatting code..."
	uv run ruff format .

# Linting
lint:
	@echo "🔍 Running linter..."
	uv run ruff check .

# Tests (with PYTHONPATH set for proper imports)
test:
	@echo "🧪 Running tests..."
	PYTHONPATH=src:. uv run pytest tests/ -q

# Full health check
health:
	@echo "🏥 Running health checks..."
	sh .agent/workflows/health-check.sh

# Run all checks (format, lint, test)
all: format lint test
	@echo ""
	@echo "✅ All checks complete!"

# Alias for 'all'
check: all

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cache files cleaned"
