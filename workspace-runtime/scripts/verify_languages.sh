#!/bin/bash
# 語言環境驗證腳本
# 用於驗證 Codex-Universal 中所有語言環境是否正確安裝
# 可選執行：docker exec <container_id> bash /workspace-runtime/scripts/verify_languages.sh

echo "🔍 驗證語言環境..."
echo ""

# 計數器
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
        echo "❌ $name: 未安裝"
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
# Swift (僅 amd64)
# ============================================================================
if [ "$(uname -m)" = "x86_64" ]; then
    echo "📦 Swift:"
    check_command "Swift" "swift"
    echo ""
else
    echo "📦 Swift:"
    echo "⚠️  Swift 不支援 $(uname -m) 架構"
    echo ""
fi

# ============================================================================
# Elixir
# ============================================================================
echo "📦 Elixir:"
check_command "Elixir" "elixir"
check_command "Erlang" "erl" || echo "❌ Erlang: 未找到"
echo ""

# ============================================================================
# Bun
# ============================================================================
echo "📦 Bun:"
check_command "Bun" "bun"
echo ""

# ============================================================================
# 開發工具
# ============================================================================
echo "🛠️  開發工具:"

if command -v git &> /dev/null; then
    echo "✅ Git: $(git --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ Git: 未安裝"
fi
((TOTAL_CHECKS++))

if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ Docker: 未安裝"
fi
((TOTAL_CHECKS++))

if command -v claude &> /dev/null; then
    echo "✅ Claude CLI: $(which claude)"
    ((PASSED_CHECKS++))
else
    echo "❌ Claude CLI: 未安裝"
fi
((TOTAL_CHECKS++))

if command -v uv &> /dev/null; then
    echo "✅ uv: $(uv --version)"
    ((PASSED_CHECKS++))
else
    echo "❌ uv: 未安裝"
fi
((TOTAL_CHECKS++))

if command -v supervisor &> /dev/null; then
    echo "✅ Supervisor: 已安裝"
    ((PASSED_CHECKS++))
else
    echo "❌ Supervisor: 未安裝"
fi
((TOTAL_CHECKS++))

echo ""

# ============================================================================
# 環境變數檢查
# ============================================================================
echo "🔧 環境變數:"
echo "   - PYTHONPATH: $PYTHONPATH"
echo "   - NPM_CONFIG_PREFIX: $NPM_CONFIG_PREFIX"
echo "   - GOPATH: $GOPATH"
echo "   - PATH: ${PATH:0:80}..."
echo ""

# ============================================================================
# 系統信息
# ============================================================================
echo "🖥️  系統信息:"
echo "   - 架構: $(uname -m)"
echo "   - 操作系統: $(uname -s)"
echo "   - 內核版本: $(uname -r)"
echo "   - 發行版本: $(lsb_release -d 2>/dev/null | cut -f2)"
echo ""

# ============================================================================
# 總結
# ============================================================================
PERCENT=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
echo "📊 驗證結果: $PASSED_CHECKS/$TOTAL_CHECKS 通過 ($PERCENT%)"
echo ""

if [ $PERCENT -ge 80 ]; then
    echo "✅ 語言環境驗證完成，大部分環境已正確安裝"
    exit 0
elif [ $PERCENT -ge 50 ]; then
    echo "⚠️  語言環境驗證完成，部分環境缺失"
    exit 1
else
    echo "❌ 語言環境驗證失敗，大部分環境缺失"
    exit 2
fi
