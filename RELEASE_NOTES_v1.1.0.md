# Zundanen v1.1.0

## Main change

Accent forced alignment now uses a **Windows-native Aalto/Kaldi backend**. `setup.bat` installs the Accent engine together with the normal environment, so there is no separate Accent-install step and no WSL2/Docker Desktop requirement for normal use.

## Included changes

- Native Windows Aalto/Kaldi forced alignment backend.
- Same result interface as the previous backend: words, phones, syllables, and timestamps.
- Finnish G2P is explicitly fixed to `phone-finnish-finnish.csv`.
- Windows subprocess pipe fix discovered during real alignment testing.
- Native runtime probe with file and executable checks.
- Automatic lookup of common Intel oneMKL runtime folders.
- Accent installer installs PyWORLD and, when required, Intel oneMKL for the native backend.
- `setup.bat` now installs PyWORLD, the native Aalto/Kaldi runtime, and Intel oneMKL when required.
- The old Docker backend remains in the codebase only as a developer/compatibility fallback; normal setup no longer installs WSL2 or Docker Desktop.
- Updated Finnish, Japanese, and English UI/help text and README files.
- Updated Kaldi build helper for current CMake/MSVC and `ivector-extract-online2`.
- Updated developer asset-export helper, including deterministic Aalto `phones.txt` generation.

## Validated Finnish alignment

A Windows 11 test using the sentence:

```text
Tässä videossa näytän, miten minut saa puhumaan suomea.
```

completed with the native backend and produced correct Finnish phone/syllable sequences such as:

```text
Tässä     -> Täs | sä
näytän    -> näy | tän
miten     -> mi | ten
minut     -> mi | nut
puhumaan  -> pu | hu | maan
suomea    -> suo | me | a
```

## Packaging note

The generated `runtime/aalto_native` payload is machine-built and is not present in the v1.0.0 source archive used to create this update. Build it on the validated Windows machine with `package_native_aalto_runtime.ps1` and upload `Zundanen-Aalto-Native-v1.1.0.zip` to the GitHub `v1.1.0` release. `setup.bat` downloads that asset automatically through the bundled Accent helper. See `AALTO_NATIVE_WINDOWS.md`.
