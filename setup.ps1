$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $ProjectRoot 'scripts\setup_whisper_cpp.py'

$Python = $null
$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher) {
    $Python = @('py', '-3')
} else {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCmd) {
        throw 'python/py not found in PATH'
    }
    $Python = @($PythonCmd.Source)
}

if ($Python.Count -gt 1) {
    & $Python[0] @($Python[1..($Python.Count - 1)]) $SetupScript @args
} else {
    & $Python[0] $SetupScript @args
}
exit $LASTEXITCODE
