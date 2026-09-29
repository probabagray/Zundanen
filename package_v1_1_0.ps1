Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Parent = Split-Path -Parent $Root
$Stage = Join-Path $Parent "Zundanen-v1.1.0-stage"
$Zip = Join-Path $Parent "Zundanen-v1.1.0.zip"

Remove-Item -Recurse -Force $Stage -ErrorAction SilentlyContinue
Remove-Item -Force $Zip -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Write-Host "Staging Zundanen v1.1.0 source/application package..." -ForegroundColor Cyan
Get-ChildItem -Force $Root | ForEach-Object {
    if ($_.Name -in @('.git','temp','outputs','__pycache__')) { return }
    if ($_.Name -eq 'runtime') {
        # runtime is generated locally and can be very large. The public native
        # Aalto payload is distributed as Zundanen-Aalto-Native-v1.1.0.zip and
        # downloaded automatically by setup.bat through the Accent helper.
        New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'runtime\aalto_native') | Out-Null
        $placeholder = Join-Path $_.FullName 'aalto_native\README.txt'
        if (Test-Path $placeholder) {
            Copy-Item -Force $placeholder (Join-Path $Stage 'runtime\aalto_native\README.txt')
        }
        return
    }
    Copy-Item -Recurse -Force $_.FullName $Stage
}

Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $Zip -CompressionLevel Optimal
Remove-Item -Recurse -Force $Stage
Write-Host "[OK] Main v1.1.0 package:" -ForegroundColor Green
Write-Host "     $Zip"
Write-Host "Create/upload the native runtime asset with package_native_aalto_runtime.ps1 before publishing v1.1.0; setup.bat downloads it automatically." -ForegroundColor Yellow
