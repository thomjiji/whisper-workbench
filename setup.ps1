[CmdletBinding()]
param(
    [Alias('m')]
    [string]$Model = 'large-v3',

    [Alias('h')]
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    @"
Usage: .\\setup.ps1 [--model <large-v3|large-v3-turbo|v3|turbo>] [-m <...>] [-h|--help]

Options:
  --model, -m
            Whisper model variant to download (default: large-v3)
            accepted: large-v3, v3, large-v3-turbo, turbo
  -h, --help
            Show this help message
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

switch ($Model.ToLowerInvariant()) {
    'large-v3' {
        $ModelVariant = 'large-v3'
        $ModelName = 'ggml-large-v3.bin'
    }
    'v3' {
        $ModelVariant = 'large-v3'
        $ModelName = 'ggml-large-v3.bin'
    }
    'large-v3-turbo' {
        $ModelVariant = 'large-v3-turbo'
        $ModelName = 'ggml-large-v3-turbo.bin'
    }
    'turbo' {
        $ModelVariant = 'large-v3-turbo'
        $ModelName = 'ggml-large-v3-turbo.bin'
    }
    default {
        Write-Error "unsupported model '$Model' (use large-v3/v3 or large-v3-turbo/turbo)"
        exit 2
    }
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VendorDir = Join-Path $ProjectRoot 'vendor'
$WhisperCppDir = Join-Path $VendorDir 'whisper.cpp'

Write-Host "==> Setting up whisper.cpp..."
Write-Host "==> Model variant: $ModelVariant ($ModelName)"

New-Item -ItemType Directory -Path $VendorDir -Force | Out-Null

if (-not (Test-Path -Path $WhisperCppDir -PathType Container)) {
    Write-Host '==> Cloning whisper.cpp...'
    git clone https://github.com/ggerganov/whisper.cpp.git $WhisperCppDir
} else {
    Write-Host '==> whisper.cpp already cloned, updating...'
    git -C $WhisperCppDir pull
}

Write-Host '==> Building whisper.cpp...'
Push-Location $WhisperCppDir
try {
    cmake -B build
    cmake --build build --config Release

    $ModelPath = Join-Path (Join-Path $WhisperCppDir 'models') $ModelName
    if (-not (Test-Path -Path $ModelPath -PathType Leaf)) {
        Write-Host "==> Downloading $ModelName model..."
        & (Join-Path $WhisperCppDir 'models\download-ggml-model.cmd') $ModelVariant
    } else {
        Write-Host "==> Model $ModelName already exists"
    }
}
finally {
    Pop-Location
}

$WhisperCliRelease = Join-Path $WhisperCppDir 'build\bin\Release\whisper-cli.exe'
$WhisperCliNoConfig = Join-Path $WhisperCppDir 'build\bin\whisper-cli.exe'

Write-Host ''
Write-Host '==> Setup complete!'
Write-Host ''
if (Test-Path -Path $WhisperCliRelease -PathType Leaf) {
    Write-Host "whisper.cpp built at: $WhisperCliRelease"
} elseif (Test-Path -Path $WhisperCliNoConfig -PathType Leaf) {
    Write-Host "whisper.cpp built at: $WhisperCliNoConfig"
} else {
    Write-Host "whisper.cpp build output is under: $(Join-Path $WhisperCppDir 'build\\bin')"
}
Write-Host "Model downloaded to:  $ModelPath"
Write-Host ''
Write-Host 'Optional environment overrides (PowerShell):'
Write-Host "  `$env:WHISPER_CPP_DIR = '$WhisperCppDir'"
Write-Host "  `$env:WHISPER_MODEL_PATH = '$ModelPath'"
