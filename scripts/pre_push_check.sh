#!/bin/bash

echo "🚀 CryptoWeaver AI - Pre-Push Validation Suite"
echo "=============================================="

# Exit on any error
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check() {
    echo -n "🔍 $1... "
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

fail() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 1. Check Python version
check "Python version (3.11+)"
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ "$PYTHON_VERSION" =~ ^3\.(1[1-9]|2[0-9]) ]]; then
    success "Python $PYTHON_VERSION"
else
    fail "Python 3.11+ required, found $PYTHON_VERSION"
fi

# 2. Check critical files exist
check "Critical files"
required_files=(
    "main.py"
    "bot.py"
    "requirements.txt"
    "Dockerfile"
    "docker-compose.yml"
    ".env.example"
    "README.md"
)

missing=0
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        warning "Missing: $file"
        missing=1
    fi
done

if [ $missing -eq 0 ]; then
    success "All critical files present"
fi

# 3. Check for secrets in code
check "Secrets in code"
if grep -r "password\|secret\|token\|key" --include="*.py" --include="*.env" --exclude-dir=.venv . | grep -v "example\|test\|mock\|TODO"; then
    warning "Potential secrets found. Review above lines."
else
    success "No obvious secrets in code"
fi

# 4. Run syntax check
check "Python syntax"
find . -name "*.py" -not -path "./.venv/*" -not -path "*/__pycache__/*" -exec python -m py_compile {} \;
if [ $? -eq 0 ]; then
    success "All Python files compile"
else
    fail "Syntax errors found"
fi

# 5. Import check
check "Module imports"
python -c "
try:
    from crypto_weaver.bot import CryptoWeaverBot
    from crypto_weaver.core.database import get_db
    from crypto_weaver.modules.auth.handlers import AuthHandlers
    print('Import successful')
except Exception as e:
    print(f'Import failed: {e}')
    exit(1)
"
if [ $? -eq 0 ]; then
    success "All modules import correctly"
else
    fail "Import errors found"
fi

# 6. Run unit tests
check "Unit tests"
pytest tests/unit/ -v --tb=short --disable-warnings > /dev/null 2>&1
if [ $? -eq 0 ]; then
    success "Unit tests passed"
else
    fail "Unit tests failed"
fi

# 7. Check code style
check "Code style (flake8)"
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics > /dev/null 2>&1
if [ $? -eq 0 ]; then
    success "No critical style issues"
else
    warning "Code style issues found (non-critical)"
fi

# 8. Check Docker build
check "Docker build"
docker build -t crypto-weaver-test . > /dev/null 2>&1
if [ $? -eq 0 ]; then
    success "Docker builds successfully"
else
    fail "Docker build failed"
fi

# 9. Clean up
docker rmi crypto-weaver-test > /dev/null 2>&1

echo -e "\n${GREEN}✅ All pre-push checks passed! Ready to push to GitHub.${NC}"
