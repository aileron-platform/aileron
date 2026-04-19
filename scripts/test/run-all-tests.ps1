$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$opsScript = Join-Path $scriptDir "..\dev\docker\ops.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $opsScript test @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $opsScript test @args
    exit $LASTEXITCODE
}

Write-Error "找不到 py 或 python，無法執行跨平台測試 CLI。"
