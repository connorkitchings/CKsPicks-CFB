#!/bin/bash
# Health Check Script for CFB Model
# Runs all quality gates before commits
# Usage: sh .agent/workflows/health-check.sh

set -e

echo "🔍 Running health checks..."
echo ""

# Track exit codes
FAILED=0

# 1. Code formatting
echo "1️⃣  Checking code formatting..."
if uv run ruff format . --check > /dev/null 2>&1; then
    echo "   ✅ Code is properly formatted"
else
    echo "   ❌ Code not formatted"
    echo "   Run: uv run ruff format ."
    FAILED=1
fi
echo ""

# 2. Linting
echo "2️⃣  Running linter..."
if uv run ruff check . > /dev/null 2>&1; then
    echo "   ✅ No linting errors"
else
    echo "   ❌ Linting errors found"
    echo "   Run: uv run ruff check ."
    FAILED=1
fi
echo ""

# 3. Tests (with PYTHONPATH for proper imports)
echo "3️⃣  Running tests..."
if PYTHONPATH=. uv run pytest tests/ -q > /dev/null 2>&1; then
    echo "   ✅ All tests passing"
else
    echo "   ❌ Tests failed"
    echo "   Run: PYTHONPATH=. uv run pytest tests/ -v for details"
    FAILED=1
fi
echo ""

# 4. Security scan
echo "4️⃣  Scanning for security issues..."
if uv run bandit -r src/ -ll > /dev/null 2>&1; then
    echo "   ✅ No security issues found"
else
    echo "   ⚠️  Security issues detected"
    echo "   Run: uv run bandit -r src/ -ll for details"
    # Don't fail on security warnings, just warn
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo "✅ All health checks passed!"
    exit 0
else
    echo "❌ Some health checks failed"
    echo ""
    echo "Fix the issues above before committing."
    exit 1
fi
