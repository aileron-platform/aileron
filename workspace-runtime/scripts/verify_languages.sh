#!/bin/bash
# Language environment verification script
# Verifies that all Codex-Universal language environments are installed correctly.
# Optional command: docker exec <container_id> bash /workspace-runtime/scripts/verify_languages.sh

echo "🔍 Verifying language environments..."
echo ""

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

check_command() {
    local name=$1
    local cmd=$2
    ((TOTAL_CHECKS++))

    if command -v $cmd &> /dev/null; then
        eval "$cmd" > /tmp/version.txt 2>&1
        VERSION=$(cat /tmp/version.txt | head -n1)
        echo "✅ $name: $VERSION"
        ((PASSED_CHECKS++))
        return 0
    else
        echo "❌ $name: not installed"
        return 1
    fi
}

# ============================================================================
# Python
# ============================================================================
echo "📦 Python:"
if command -v pyenv &> /dev/null; then
    echo "   Available versions:"
    pyenv versions | grep -v system || echo "   No versions installed"
fi
check_command "Python" "python"
check_command "pip" "pip"
echo ""

# ============================================================================
# Node.js
# ============================================================================
echo "📦 Node.js:"
if command -v nvm &> /dev/null; then
    echo "   Available versions:"
    . ~/.nvm/nvm.sh
    nvm list | head -5
fi
check_command "Node.js" "node"
check_command "npm" "npm"
check_command "yarn" "yarn"
echo ""

# ============================================================================
# Java
# ============================================================================
echo "📦 Java:"
check_command "Java" "java" || true
if command -v javac &> /dev/null; then
    echo "   Compiler: $(javac -version 2>&1 | head -n1)"
fi
echo ""

# ============================================================================
# Go
# ============================================================================
echo "📦 Go:"
check_command "Go" "go"
if command -v go &> /dev/null; then
    echo "   GOPATH: $GOPATH"
    echo "   GOROOT: $(go env GOROOT)"
fi
echo ""

# ============================================================================
# Rust
# ============================================================================
echo "📦 Rust:"
check_command "Rust (rustc)" "rustc"
check_command "Cargo" "cargo"
if command -v rustup &> /dev/null; then
    echo "   Toolchain: $(rustup show active-toolchain)"
fi
echo ""

# ============================================================================
# Ruby
# ============================================================================
echo "📦 Ruby:"
check_command "Ruby" "ruby"
check_command "RubyGems" "gem"
echo ""

# ============================================================================
# PHP
# ============================================================================
echo "📦 PHP:"
check_command "PHP" "php"
check_command "Composer" "composer"
echo ""

# ============================================================================
# Swift (amd64 only)
# ============================================================================
if [ "$(uname -m)" = "x86_64" ]; then
    echo "📦 Swift:"
    check_command "Swift" "swift"
    echo ""
else
    echo "📦 Swift:"
    echo "⚠️  Swift does not support the $(uname -m) architecture"
    echo ""
fi

# ============================================================================
# Elixir
# ============================================================================
echo "📦 Elixir:"
check_command "Elixir" "elixir"
check_command "Erlang" "erl" || echo "❌ Erlang: not found"
echo ""

# ============================================================================
# Bun
# ============================================================================
echo "📦 Bun:"
check_command "Bun" "bun"
echo ""

# ============================================================================
# Development tools
# ============================================================================
echo "🛠️  Development tools:"

if command -v git &> /dev/null; then
    echo "✅ Git: $(git --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ Git: not installed"
fi
((TOTAL_CHECKS++))

if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ Docker: not installed"
fi
((TOTAL_CHECKS++))

if command -v claude &> /dev/null; then
    echo "✅ Claude CLI: $(which claude)"
    ((PASSED_CHECKS++))
else
    echo "❌ Claude CLI: not installed"
fi
((TOTAL_CHECKS++))

if command -v uv &> /dev/null; then
    echo "✅ uv: $(uv --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ uv: not installed"
fi
((TOTAL_CHECKS++))

if command -v supervisor &> /dev/null; then
    echo "✅ Supervisor: installed"
    ((PASSED_CHECKS++))
else
    echo "❌ Supervisor: not installed"
fi
((TOTAL_CHECKS++))

echo ""

# ============================================================================
# Environment variable checks
# ============================================================================
echo "🔧 Environment variables:"
echo "   - PYTHONPATH: $PYTHONPATH"
echo "   - NPM_CONFIG_PREFIX: $NPM_CONFIG_PREFIX"
echo "   - GOPATH: $GOPATH"
echo "   - PATH: ${PATH:0:80}..."
echo ""

# ============================================================================
# System information
# ============================================================================
echo "🖥️  System information:"
echo "   - Architecture: $(uname -m)"
echo "   - Operating system: $(uname -s)"
echo "   - Kernel version: $(uname -r)"
echo "   - Distribution: $(lsb_release -d 2>/dev/null | cut -f2)"
echo ""

# ============================================================================
# Summary
# ============================================================================
PERCENT=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
echo "📊 Verification result: $PASSED_CHECKS/$TOTAL_CHECKS passed ($PERCENT%)"
echo ""

if [ $PERCENT -ge 80 ]; then
    echo "✅ Language environment verification complete; most environments are installed correctly"
    exit 0
elif [ $PERCENT -ge 50 ]; then
    echo "⚠️  Language environment verification complete; some environments are missing"
    exit 1
else
    echo "❌ Language environment verification failed; most environments are missing"
    exit 2
fi
