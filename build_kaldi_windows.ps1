Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Work = Join-Path $Root "runtime\aalto_native_build"
$Kaldi = Join-Path $Work "kaldi"
$Build = Join-Path $Kaldi "build"
$Out = Join-Path $Root "runtime\aalto_native\bin"

function Require-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "$Name was not found in PATH. Install it and retry." }
    return $cmd.Source
}

$git = Require-Command "git.exe"
$cmake = Require-Command "cmake.exe"

if (-not $env:MKLROOT) {
    $mklCandidates = @(
        "C:\Program Files (x86)\Intel\oneAPI\mkl\latest",
        "C:\Program Files\Intel\oneAPI\mkl\latest"
    )
    foreach ($candidate in $mklCandidates) {
        if (Test-Path $candidate) {
            $env:MKLROOT = $candidate
            break
        }
    }
}
if (-not $env:MKLROOT -or -not (Test-Path $env:MKLROOT)) {
    throw "Intel oneMKL was not found. Install it first, e.g. winget install --id Intel.oneMKL -e"
}
Write-Host "Using MKLROOT=$env:MKLROOT" -ForegroundColor DarkGray

New-Item -ItemType Directory -Force -Path $Work | Out-Null
if (-not (Test-Path (Join-Path $Kaldi ".git"))) {
    Write-Host "Cloning Kaldi..." -ForegroundColor Cyan
    & $git clone --depth 1 https://github.com/kaldi-asr/kaldi.git $Kaldi
    if ($LASTEXITCODE -ne 0) { throw "Kaldi clone failed." }
}

# Current Kaldi CMake excludes online2bin on MSVC. Zundanen needs only
# ivector-extract-online2 from that directory, and it builds successfully on
# Windows/MSVC, so enable online2bin while keeping onlinebin unchanged.
$topCmake = Join-Path $Kaldi "CMakeLists.txt"
$cmakeText = Get-Content -Raw -Path $topCmake
$pattern = 'if\(NOT MSVC\)\s*add_subdirectory\(src/onlinebin\)\s*add_subdirectory\(src/online2bin\)\s*endif\(\)'
if ($cmakeText -match $pattern) {
    $replacement = @"
if(NOT MSVC)
    add_subdirectory(src/onlinebin)
endif()
add_subdirectory(src/online2bin)
"@
    $cmakeText = [regex]::Replace($cmakeText, $pattern, $replacement, 1)
    [IO.File]::WriteAllText($topCmake, $cmakeText, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Enabled src/online2bin for MSVC." -ForegroundColor DarkGray
}

New-Item -ItemType Directory -Force -Path $Build | Out-Null
Push-Location $Build
try {
    Write-Host "Configuring Kaldi CMake build..." -ForegroundColor Cyan
    $cmakeArgs = @(
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5"
        "-DMATHLIB=MKL"
        "-DKALDI_BUILD_TEST=OFF"
        "-DKALDI_BUILD_EXE=ON"
        ".."
    )
    & $cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Kaldi CMake configure failed. Visual Studio C++ Build Tools and oneMKL are required."
    }

    $targets = @(
        "compute-mfcc-feats",
        "copy-feats",
        "compute-cmvn-stats",
        "apply-cmvn",
        "ivector-extract-online2",
        "compile-train-graphs-without-lexicon",
        "nnet3-align-compiled",
        "ali-to-phones"
    )
    foreach ($target in $targets) {
        Write-Host "Building $target..." -ForegroundColor Cyan
        & $cmake --build . --target $target --config Release -- /m:8
        if ($LASTEXITCODE -ne 0) { throw "Kaldi target failed: $target" }
    }
}
finally {
    Pop-Location
}

$Needed = @(
    "compute-mfcc-feats.exe",
    "copy-feats.exe",
    "compute-cmvn-stats.exe",
    "apply-cmvn.exe",
    "ivector-extract-online2.exe",
    "compile-train-graphs-without-lexicon.exe",
    "nnet3-align-compiled.exe",
    "ali-to-phones.exe"
)
New-Item -ItemType Directory -Force -Path $Out | Out-Null
foreach ($name in $Needed) {
    $hit = Get-ChildItem -Path $Build -Recurse -File -Filter $name | Where-Object { $_.FullName -match '\\Release\\' } | Select-Object -First 1
    if (-not $hit) { throw "Built Kaldi executable not found: $name" }
    Copy-Item -Force $hit.FullName (Join-Path $Out $name)
}

Get-ChildItem -Path $Build -Recurse -File -Filter "*.dll" -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item -Force $_.FullName (Join-Path $Out $_.Name) }

Write-Host "" 
Write-Host "[OK] Native Kaldi executables copied to:" -ForegroundColor Green
Write-Host "     $Out"
Write-Host "Run: python .\aalto_native_probe.py" -ForegroundColor Yellow
Write-Host "If the probe reports a DLL error, install oneMKL or package its redistributable runtime DLLs beside the Kaldi executables." -ForegroundColor Yellow
