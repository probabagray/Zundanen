# Windows-native Aalto backend (Zundanen v1.1.0)

Zundanen v1.1.0 adds a Windows-native forced-alignment path for the same Aalto Finnish/Kaldi acoustic model used by the previous Docker workflow.

## What changed

The normal Accent path is now:

```text
Finnish WAV + transcript
  -> Windows Kaldi executables
  -> Aalto Finnish acoustic model
  -> word / phone / syllable timestamps
  -> WORLD / PyWORLD Accent edit
  -> optional RVC conversion
```

Normal v1.1.0 setup uses the Windows-native backend. WSL2 and Docker Desktop are not installed or required for Accent editing. The old Docker backend remains only as a developer/compatibility fallback in the codebase.

## Validated status

The native pipeline was validated on Windows 11 with a Finnish TTS utterance. The test completed without Docker and returned:

- aligned words and timestamps
- Aalto phone intervals
- Finnish syllables such as `Täs | sä`, `näy | tän`, `mi | ten`, `pu | hu | maan`, and `suo | me | a`
- `backend: native`

Two Windows-specific issues found during validation are fixed in v1.1.0:

1. the binary Kaldi stdout/stdin pipe no longer calls `communicate()` on a closed stdout handle;
2. G2P is fixed to `phone-finnish-finnish.csv` instead of auto-selecting another cross-language mapping.

## Expected runtime layout

```text
runtime/aalto_native/
  bin/
    compute-mfcc-feats.exe
    copy-feats.exe
    compute-cmvn-stats.exe
    apply-cmvn.exe
    ivector-extract-online2.exe
    compile-train-graphs-without-lexicon.exe
    nnet3-align-compiled.exe
    ali-to-phones.exe
  model/
    nnet3/chain/tree
    nnet3/chain/final.mdl
    nnet3/chain/phones.txt
    nnet3/chain/frame_subsampling_factor
    nnet3/extractor/final.ie
    nnet3/extractor/final.dubm
    nnet3/extractor/global_cmvn.stats
    nnet3/extractor/splice_opts
    nnet3/extractor/online_cmvn.conf
    nnet3/extractor/final.mat
    conf/mfcc_hires.conf
    g2p/change_lex_pho.py
    g2p/phone-finnish-finnish.csv
    g2p/*.csv
  LICENSES/
    AALTO-FINNISH-FORCED-ALIGNMENT-MIT.txt
    KALDI-APACHE-2.0.txt
    KALDI-NOTICE.txt
    LINGSOFT-AALTO-KALDI-ALIGN-NOTICE.txt
  THIRD_PARTY_NOTICES.md
```

Check it with:

```powershell
python .\aalto_native_probe.py
```

A packaged runtime should report `"ready": true`.

## Developer preparation

On a development PC that has Docker available, export the Aalto assets once:

```powershell
.\prepare_aalto_native_assets.ps1
```

The helper also regenerates the position-dependent `phones.txt` used by the tested native graph compiler path and verifies that `phone-finnish-finnish.csv` exists.

Build only the required Kaldi Windows executables:

```powershell
winget install --id Intel.oneMKL -e
.\build_kaldi_windows.ps1
```

The build helper uses oneMKL, applies the CMake compatibility option needed by current CMake releases, enables `src/online2bin` for MSVC so `ivector-extract-online2.exe` can be built, and copies only the eight executables used by Zundanen.

## Backend selection

Default:

```text
ZUNDANEN_AALTO_BACKEND=auto
```

`auto` uses the native backend when it is ready. The Docker backend can still be selected explicitly for developer compatibility testing.

For development:

```powershell
$env:ZUNDANEN_AALTO_BACKEND = "native"
```

or:

```powershell
$env:ZUNDANEN_AALTO_BACKEND = "docker"
```

## Runtime math libraries

The tested Kaldi build links against Intel oneMKL. Zundanen automatically adds common oneMKL installation folders to the child-process `PATH`. The Accent installer can install `Intel.oneMKL` through WinGet when native files are present but the executable cannot start.

For a smaller end-user dependency footprint, a future release may instead package only the redistributable runtime DLLs or use another supported linkage strategy. Verify the applicable third-party redistribution terms before bundling external runtime DLLs.

## Release packaging requirement

The source archive itself does not contain the generated Kaldi binaries or Aalto model payload. Create the native runtime release asset on the validated Windows development machine. The packaging helper validates and bundles `LICENSES/` plus `THIRD_PARTY_NOTICES.md` together with `bin/` and `model/`:

```powershell
.\package_native_aalto_runtime.ps1
```

Upload the resulting file to GitHub release tag `v1.1.0` using the exact asset name:

```text
Zundanen-Aalto-Native-v1.1.0.zip
```

`setup.bat` downloads this asset automatically into `runtime/aalto_native`. The helper `install_accent_support.ps1` is retained for repair/testing and is called by setup. You can override the source during testing with the `ZUNDANEN_AALTO_NATIVE_URL` environment variable (a local ZIP path is also accepted). Verify the installed payload on a clean Windows test environment with `python .\aalto_native_probe.py`.

## About `phones.txt`

The original Aalto Docker pipeline generates `data/lang/phones.txt` for each alignment with Kaldi `utils/prepare_lang.sh` and removes the temporary `data` directory at the end. The Windows-native backend intentionally avoids running Bash/Kaldi helper scripts at runtime, so `prepare_aalto_native_assets.ps1` generates the same Finnish phone symbol table once during runtime packaging and stores it as `runtime/aalto_native/model/nnet3/chain/phones.txt`. `frame_subsampling_factor` is optional at runtime; when absent the native backend uses the Aalto Finnish model value `3`.
