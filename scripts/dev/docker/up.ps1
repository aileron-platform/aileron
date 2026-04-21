$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$opsScript = Join-Path $scriptDir "ops.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $opsScript up @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $opsScript up @args
    exit $LASTEXITCODE
}

Write-Error "找不到 py 或 python，無法執行跨平台 docker compose CLI。"
