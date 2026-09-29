Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Out = Join-Path $Root "runtime\aalto_native\model"
$Image = "lingsoft/aalto-kaldi-align:5.1.1-elg"
$Name = "zundanen-aalto-export-$([Guid]::NewGuid().ToString('N').Substring(0,8))"
$tmpScript = $null

function Require-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "$Name was not found in PATH." }
    return $cmd.Source
}

$docker = Require-Command "docker.exe"
Write-Host "Exporting Aalto model assets from $Image" -ForegroundColor Cyan
& $docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) {
    & $docker pull $Image
    if ($LASTEXITCODE -ne 0) { throw "Could not pull $Image" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
try {
    $id = (& $docker create --name $Name $Image).Trim()
    if (-not $id) { throw "docker create returned no container id." }

    $nnet3 = Join-Path $Out "nnet3"
    $conf = Join-Path $Out "conf"
    $g2p = Join-Path $Out "g2p"
    Remove-Item -Recurse -Force $nnet3,$conf,$g2p -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $nnet3,$conf,$g2p | Out-Null

    & $docker cp "${Name}:/opt/kaldi/egs/align/exp/nnet3/." $nnet3
    if ($LASTEXITCODE -ne 0) { throw "Could not export exp/nnet3 from Aalto image." }

    & $docker cp "${Name}:/opt/kaldi/egs/align/conf/." $conf
    if ($LASTEXITCODE -ne 0) { throw "Could not export Aalto conf directory." }

    & $docker cp "${Name}:/opt/kaldi/egs/align/aligning_with_Docker/bin/." $g2p
    if ($LASTEXITCODE -ne 0) { throw "Could not export Aalto G2P helper directory." }

    # Aalto's chain model uses frame_subsampling_factor=3.
    $fsf = Join-Path $nnet3 "chain\frame_subsampling_factor"
    if (-not (Test-Path $fsf)) {
        Set-Content -Path $fsf -Value "3" -Encoding Ascii
    }

    # Lingsoft's image creates lang/phones.txt dynamically. Recreate the exact
    # Finnish phone inventory with Kaldi prepare_lang.sh, then export phones.txt.
    $tmpScript = Join-Path $env:TEMP "zundanen_generate_phones_$([Guid]::NewGuid().ToString('N')).sh"
    $scriptText = @'
#!/usr/bin/env bash
set -euo pipefail

# Aalto's own alignment script runs Kaldi utilities from the WSJ s5 recipe.
# Run prepare_lang.sh from the same recipe root so all relative utils/* calls
# resolve exactly as they do in the original Docker pipeline.
s5_dir=/opt/kaldi/egs/wsj/s5
if [ ! -f "$s5_dir/utils/prepare_lang.sh" ]; then
  echo "Kaldi prepare_lang.sh was not found at $s5_dir/utils/prepare_lang.sh" >&2
  exit 20
fi
cd "$s5_dir"

rm -rf /tmp/zundanen_dict /tmp/zundanen_lang_tmp /tmp/zundanen_lang
mkdir -p /tmp/zundanen_dict
cat > /tmp/zundanen_dict/silence_phones.txt <<'EOF'
NSN
SIL
SPN
EOF
cat > /tmp/zundanen_dict/optional_silence.txt <<'EOF'
SIL
EOF
cat > /tmp/zundanen_dict/nonsilence_phones.txt <<'EOF'
2
A
I
N
U
b
d
e
f
g
h
j
k
l
m
n
o
p
r
s
t
v
y
{
EOF
: > /tmp/zundanen_dict/extra_questions.txt
cat > /tmp/zundanen_dict/lexicon.txt <<'EOF'
<UNK> SPN
probe A
EOF

utils/prepare_lang.sh --num-extra-phone-disambig-syms 3 \
  /tmp/zundanen_dict '<UNK>' /tmp/zundanen_lang_tmp /tmp/zundanen_lang
cp /tmp/zundanen_lang/phones.txt /tmp/zundanen_phones.txt
'@
    [IO.File]::WriteAllText($tmpScript, ($scriptText -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))
    & $docker cp $tmpScript "${Name}:/tmp/zundanen_generate_phones.sh"
    if ($LASTEXITCODE -ne 0) { throw "Could not copy phones.txt generation helper into container." }
    & $docker start $Name *> $null
    & $docker exec $Name bash /tmp/zundanen_generate_phones.sh
    if ($LASTEXITCODE -ne 0) { throw "Could not generate Aalto phones.txt." }
    & $docker cp "${Name}:/tmp/zundanen_phones.txt" (Join-Path $nnet3 "chain\phones.txt")
    if ($LASTEXITCODE -ne 0) { throw "Could not export generated phones.txt." }
    Remove-Item -Force $tmpScript -ErrorAction SilentlyContinue
    $tmpScript = $null

    $finnishMap = Join-Path $g2p "phone-finnish-finnish.csv"
    if (-not (Test-Path $finnishMap)) {
        throw "Expected Finnish G2P mapping was not found: $finnishMap"
    }

    Write-Host "[OK] Aalto model/G2P assets exported to:" -ForegroundColor Green
    Write-Host "     $Out"
    Write-Host "[OK] Finnish phones.txt generated and phone-finnish-finnish.csv verified." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: run build_kaldi_windows.ps1 to build/copy native Kaldi executables." -ForegroundColor Yellow
}
finally {
    if ($tmpScript) { Remove-Item -Force $tmpScript -ErrorAction SilentlyContinue }
    & $docker rm -f $Name *> $null
}
