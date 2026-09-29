param(
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Native = Join-Path $Root "runtime\aalto_native"
$Probe = Join-Path $Root "aalto_native_probe.py"
$Licenses = Join-Path $Root "LICENSES"
$ThirdPartyNotices = Join-Path $Root "THIRD_PARTY_NOTICES.md"
if ($OutputPath) {
    $Out = [IO.Path]::GetFullPath($OutputPath)
}
else {
    $Out = Join-Path (Split-Path -Parent $Root) "Zundanen-Aalto-Native-v1.1.0.zip"
}

$RequiredBins = @(
    "compute-mfcc-feats.exe",
    "copy-feats.exe",
    "compute-cmvn-stats.exe",
    "apply-cmvn.exe",
    "ivector-extract-online2.exe",
    "compile-train-graphs-without-lexicon.exe",
    "nnet3-align-compiled.exe",
    "ali-to-phones.exe"
)

$RequiredModel = @(
    "model\nnet3\chain\tree",
    "model\nnet3\chain\final.mdl",
    "model\nnet3\chain\phones.txt",
    "model\nnet3\extractor\final.ie",
    "model\nnet3\extractor\final.dubm",
    "model\nnet3\extractor\global_cmvn.stats",
    "model\nnet3\extractor\splice_opts",
    "model\nnet3\extractor\online_cmvn.conf",
    "model\nnet3\extractor\final.mat",
    "model\conf\mfcc_hires.conf",
    "model\g2p\change_lex_pho.py",
    "model\g2p\phone-finnish-finnish.csv"
)

if (-not (Test-Path $Native -PathType Container)) {
    throw "Native runtime directory was not found: $Native"
}
if (-not (Test-Path $Probe -PathType Leaf)) {
    throw "aalto_native_probe.py is missing: $Probe"
}
if (-not (Test-Path $Licenses -PathType Container)) {
    throw "LICENSES directory is missing: $Licenses"
}
if (-not (Test-Path $ThirdPartyNotices -PathType Leaf)) {
    throw "THIRD_PARTY_NOTICES.md is missing: $ThirdPartyNotices"
}
$RequiredLicenseFiles = @(
    "AALTO-FINNISH-FORCED-ALIGNMENT-MIT.txt",
    "KALDI-APACHE-2.0.txt",
    "KALDI-NOTICE.txt",
    "LINGSOFT-AALTO-KALDI-ALIGN-NOTICE.txt"
)
foreach ($name in $RequiredLicenseFiles) {
    $path = Join-Path $Licenses $name
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Required runtime license/notice file is missing: $path"
    }
}

# Aalto's chain model uses a frame subsampling factor of 3.  Older local
# exports may be missing this tiny metadata file even though the model itself
# is otherwise complete, so repair that one known-safe omission before the
# strict file validation below.
$FrameSubsampling = Join-Path $Native "model\nnet3\chain\frame_subsampling_factor"
$ChainDir = Split-Path -Parent $FrameSubsampling
if (-not (Test-Path $FrameSubsampling -PathType Leaf)) {
    if (-not (Test-Path $ChainDir -PathType Container)) {
        throw "Aalto chain model directory is missing: $ChainDir"
    }
    Write-Host "frame_subsampling_factor is missing; writing the Aalto value 3." -ForegroundColor Yellow
    Set-Content -Path $FrameSubsampling -Value "3" -Encoding Ascii
}
$FrameValue = (Get-Content -Raw $FrameSubsampling).Trim()
if ($FrameValue -ne "3") {
    throw "Unexpected frame_subsampling_factor '$FrameValue'. Expected 3 for this Aalto chain model."
}

$Missing = New-Object System.Collections.Generic.List[string]
foreach ($name in $RequiredBins) {
    $path = Join-Path $Native ("bin\" + $name)
    if (-not (Test-Path $path -PathType Leaf)) {
        $Missing.Add("bin\$name")
    }
}
foreach ($rel in $RequiredModel) {
    $path = Join-Path $Native $rel
    if (-not (Test-Path $path -PathType Leaf)) {
        $Missing.Add($rel)
    }
}
if ($Missing.Count -gt 0) {
    throw ("Native Aalto runtime is incomplete. Missing:`n - " + ($Missing -join "`n - "))
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python was not found in PATH." }

Write-Host "Validating native Aalto runtime files..." -ForegroundColor Cyan
& $python.Source $Probe --files-only
if ($LASTEXITCODE -ne 0) {
    throw "Native Aalto runtime file validation failed."
}

Write-Host "Launching a Kaldi executable to verify DLL/runtime dependencies..." -ForegroundColor Cyan
& $python.Source $Probe
if ($LASTEXITCODE -ne 0) {
    throw "Native Aalto runtime files are present, but a Kaldi executable could not start. Check oneMKL/required DLLs before packaging."
}

$OutDir = Split-Path -Parent $Out
if ($OutDir) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
Remove-Item -Force $Out, ($Out + ".sha256.txt") -ErrorAction SilentlyContinue

# Stage the runtime payload plus the license/notice files that must travel
# with the redistributed Kaldi executables and Aalto model/G2P assets.
# setup.bat extracts everything directly under runtime\aalto_native.
$Stage = Join-Path $env:TEMP "zundanen-aalto-package-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
try {
    Copy-Item -Recurse -Force (Join-Path $Native "bin") $Stage
    Copy-Item -Recurse -Force (Join-Path $Native "model") $Stage
    Copy-Item -Recurse -Force $Licenses $Stage
    Copy-Item -Force $ThirdPartyNotices $Stage
    Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Out -CompressionLevel Optimal
}
finally {
    Remove-Item -Recurse -Force $Stage -ErrorAction SilentlyContinue
}

if (-not (Test-Path $Out -PathType Leaf)) {
    throw "Runtime ZIP was not created: $Out"
}

$hash = (Get-FileHash -Algorithm SHA256 $Out).Hash
Set-Content -Path ($Out + ".sha256.txt") -Value "$hash  $(Split-Path -Leaf $Out)" -Encoding Ascii

Write-Host "" 
Write-Host "[OK] Native runtime asset:" -ForegroundColor Green
Write-Host "     $Out"
Write-Host "SHA256: $hash"
Write-Host "Verified 8 Kaldi executables, generated Aalto phones.txt, required model/G2P assets, frame_subsampling_factor=3 metadata, executable startup, and bundled runtime license/notice files." -ForegroundColor Green
Write-Host "Upload this ZIP to GitHub release tag v1.1.0 with the exact asset name Zundanen-Aalto-Native-v1.1.0.zip." -ForegroundColor Yellow
