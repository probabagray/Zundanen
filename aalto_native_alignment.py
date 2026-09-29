from __future__ import annotations

"""Experimental Windows-native backend for Aalto Finnish Forced Alignment.

The existing Zundanen backend runs the Aalto/Kaldi stack inside Docker.  This
module keeps the same Aalto acoustic model, but executes Kaldi's Windows
binaries directly.  It is deliberately isolated from the stable Docker path:
`aalto_alignment.run_alignment()` only selects this backend when all native
runtime assets are present.

Expected runtime layout (relative to the Zundanen root):

runtime/aalto_native/
  bin/                         # Kaldi Windows executables
  model/
    nnet3/chain/{tree,final.mdl,phones.txt,...}
    nnet3/extractor/{final.ie,final.dubm,...}
    conf/mfcc_hires.conf
    g2p/                       # Aalto aligning_with_Docker/bin directory

`prepare_aalto_native_assets.ps1` can export the Aalto model/G2P assets from
Lingsoft's MIT-licensed Docker image on a developer machine.  End users do not
need Docker once those assets and the Windows Kaldi binaries are packaged.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


class NativeAlignmentError(RuntimeError):
    def __init__(self, message: str, code: str = "native_alignment_failed"):
        super().__init__(message)
        self.code = code


ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME = ROOT / "runtime" / "aalto_native"

_REQUIRED_BINS = [
    "compute-mfcc-feats.exe",
    "copy-feats.exe",
    "compute-cmvn-stats.exe",
    "apply-cmvn.exe",
    "ivector-extract-online2.exe",
    "compile-train-graphs-without-lexicon.exe",
    "nnet3-align-compiled.exe",
    "ali-to-phones.exe",
]

_REQUIRED_MODEL = [
    "model/nnet3/chain/tree",
    "model/nnet3/chain/final.mdl",
    "model/nnet3/chain/phones.txt",
    "model/nnet3/extractor/final.ie",
    "model/nnet3/extractor/final.dubm",
    "model/nnet3/extractor/global_cmvn.stats",
    "model/nnet3/extractor/splice_opts",
    "model/nnet3/extractor/online_cmvn.conf",
    "model/nnet3/extractor/final.mat",
    "model/conf/mfcc_hires.conf",
    "model/g2p/change_lex_pho.py",
    "model/g2p/phone-finnish-finnish.csv",
]

_SILENCE = {"SIL", "NSN", "SPN"}
_POSITION_SUFFIX_RE = re.compile(r"_[BIES]$")


def runtime_root() -> Path:
    override = os.environ.get("ZUNDANEN_AALTO_NATIVE_ROOT", "").strip()
    return Path(override).expanduser().resolve() if override else DEFAULT_RUNTIME


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def native_status(root: Path | None = None, *, check_executable: bool = True) -> dict:
    root = Path(root or runtime_root())
    missing: list[str] = []
    for name in _REQUIRED_BINS:
        if not (root / "bin" / name).exists():
            missing.append(f"bin/{name}")
    for rel in _REQUIRED_MODEL:
        if not (root / rel).exists():
            missing.append(rel)

    files_ready = not missing
    executable_ok = False
    runtime_error = ""
    if os.name == "nt" and files_ready and check_executable:
        try:
            probe = subprocess.run(
                [str(root / "bin" / "compute-mfcc-feats.exe"), "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=_native_env(root),
            )
            executable_ok = probe.returncode == 0
            if not executable_ok:
                runtime_error = f"compute-mfcc-feats.exe exited with code {probe.returncode}"
        except Exception as exc:
            runtime_error = str(exc)
    elif os.name == "nt" and files_ready:
        executable_ok = True

    ready = bool(os.name == "nt" and files_ready and executable_ok)
    return {
        "ready": ready,
        "files_ready": files_ready,
        "executable_ok": executable_ok,
        "windows": os.name == "nt",
        "root": str(root),
        "missing": missing,
        "runtime_error": runtime_error,
    }


def _native_env(root: Path | None = None) -> dict[str, str]:
    """Return an environment suitable for bundled Kaldi/oneMKL binaries."""
    env = os.environ.copy()
    root = Path(root or runtime_root())
    candidates = [root / "bin"]

    # oneMKL may be installed without its bin directory in PATH. setup.bat
    # installs the runtime when the packaged Kaldi build needs it, and these
    # common locations let the native backend find the DLLs immediately.
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(Path(base) / "Intel" / "oneAPI" / "mkl" / "latest" / "bin")
            candidates.append(Path(base) / "Intel" / "oneAPI" / "compiler" / "latest" / "bin")

    existing = env.get("PATH", "")
    prefix = [str(x) for x in candidates if x.exists()]
    if prefix:
        env["PATH"] = os.pathsep.join(prefix + ([existing] if existing else []))
    return env


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 180, text: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
        creationflags=_creationflags(),
        env=_native_env(),
    )
    if proc.returncode != 0:
        stdout = proc.stdout if isinstance(proc.stdout, str) else ""
        stderr = proc.stderr if isinstance(proc.stderr, str) else ""
        detail = (stderr or stdout or "").strip()
        raise NativeAlignmentError(
            f"Native Aalto command failed ({Path(args[0]).name}, exit {proc.returncode})"
            + (f":\n{detail[-5000:]}" if detail else ""),
            "native_command_failed",
        )
    return proc


def _pipeline(first: list[str], second: list[str], *, cwd: Path, timeout: int = 180) -> None:
    """Run two Kaldi executables connected by a binary stdout/stdin pipe."""
    env = _native_env()
    with tempfile.TemporaryFile() as err1_file, tempfile.TemporaryFile() as err2_file:
        p1 = subprocess.Popen(
            first,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=err1_file,
            creationflags=_creationflags(),
            env=env,
        )
        assert p1.stdout is not None
        p2 = subprocess.Popen(
            second,
            cwd=str(cwd),
            stdin=p1.stdout,
            stdout=subprocess.DEVNULL,
            stderr=err2_file,
            creationflags=_creationflags(),
            env=env,
        )

        # p2 owns the duplicated pipe handle now. Prevent communicate()/wait
        # from touching a closed stdout object on Windows.
        p1.stdout.close()
        p1.stdout = None

        try:
            p2.wait(timeout=timeout)
            p1.wait(timeout=max(10, timeout // 2))
        except subprocess.TimeoutExpired:
            p1.kill()
            p2.kill()
            p1.wait()
            p2.wait()
            raise NativeAlignmentError("Native Aalto pipeline timed out.", "native_timeout")

        err1_file.seek(0)
        err2_file.seek(0)
        err1 = err1_file.read()
        err2 = err2_file.read()
        if p1.returncode != 0 or p2.returncode != 0:
            detail = (err1 + b"\n" + err2).decode("utf-8", errors="replace").strip()
            raise NativeAlignmentError(
                f"Native Aalto pipeline failed (exit {p1.returncode}/{p2.returncode})"
                + (f":\n{detail[-5000:]}" if detail else ""),
                "native_command_failed",
            )

def _read_symbols(path: Path) -> tuple[dict[str, int], dict[int, str]]:
    by_name: dict[str, int] = {}
    by_id: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        try:
            idx = int(parts[1])
        except ValueError:
            continue
        by_name[parts[0]] = idx
        by_id[idx] = parts[0]
    return by_name, by_id


def _base_phone(symbol: str) -> str:
    return _POSITION_SUFFIX_RE.sub("", symbol)


def _with_word_positions(base_phones: list[str], phone_ids: dict[str, int]) -> list[str]:
    """Convert Aalto base-phone spellings to model phone symbols.

    Aalto's prepare_lang setup uses Kaldi's position-dependent phones.  Prefer
    _S/_B/_I/_E when present; fall back to the base symbol for a model that was
    built without position-dependent phones.
    """
    if not base_phones:
        return []
    result: list[str] = []
    n = len(base_phones)
    for i, base in enumerate(base_phones):
        if n == 1:
            candidate = f"{base}_S"
        elif i == 0:
            candidate = f"{base}_B"
        elif i == n - 1:
            candidate = f"{base}_E"
        else:
            candidate = f"{base}_I"
        if candidate in phone_ids:
            result.append(candidate)
        elif base in phone_ids:
            result.append(base)
        else:
            raise NativeAlignmentError(
                f"Aalto G2P produced phone '{base}', but it is not in the acoustic model phone table.",
                "native_phone_missing",
            )
    return result


def _parse_lexicon(path: Path) -> dict[str, list[str]]:
    lex: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            lex[parts[0].casefold()] = parts[1:]
    return lex


def _choose_g2p_csv(g2p_dir: Path, words: list[str], phone_ids: dict[str, int], work: Path) -> Path:
    # The Aalto assets contain several cross-language mappings. Zundanen aligns
    # Finnish speech against Finnish transcripts, so always use Finnish -> Finnish.
    csv_path = g2p_dir / "phone-finnish-finnish.csv"
    if not csv_path.exists():
        raise NativeAlignmentError(
            f"Finnish Aalto G2P mapping was not found: {csv_path}",
            "native_g2p_missing",
        )
    return csv_path


def _g2p_words(g2p_dir: Path, words: list[str], phone_ids: dict[str, int], work: Path) -> list[list[str]]:
    csv_path = _choose_g2p_csv(g2p_dir, words, phone_ids, work)
    corpus = work / "corpus"
    corpus.write_text(" ".join(words) + "\n", encoding="utf-8")
    lexicon = work / "lexicon.txt"
    if lexicon.exists():
        lexicon.unlink()
    _run([sys.executable, str(g2p_dir / "change_lex_pho.py"), str(corpus), str(csv_path)], cwd=work, timeout=30)
    if not lexicon.exists():
        raise NativeAlignmentError("Aalto G2P did not create lexicon.txt.", "native_g2p_failed")
    lex = _parse_lexicon(lexicon)
    result: list[list[str]] = []
    for word in words:
        phones = lex.get(word.casefold())
        if not phones:
            raise NativeAlignmentError(f"Aalto G2P did not return a pronunciation for '{word}'.", "native_g2p_failed")
        result.append(_with_word_positions(phones, phone_ids))
    return result


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _parse_ctm(path: Path, phone_names: dict[int, str]) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            start = float(parts[2])
            duration = float(parts[3])
            phone_id = int(parts[4])
        except ValueError:
            continue
        raw = phone_names.get(phone_id, str(phone_id))
        base = _base_phone(raw)
        rows.append({
            "phone": base,
            "raw_phone": raw,
            "is_silence": base in _SILENCE,
            "start": round(start, 4),
            "end": round(start + max(0.0, duration), 4),
            "duration": round(max(0.0, duration), 4),
        })
    return rows


def _reconstruct_words(source_words: list[str], expected: list[list[str]], phones: list[dict]) -> list[dict]:
    speech_phones = [p for p in phones if not p.get("is_silence")]
    cursor = 0
    words: list[dict] = []
    for word, expected_symbols in zip(source_words, expected):
        count = len(expected_symbols)
        if cursor + count > len(speech_phones):
            raise NativeAlignmentError("Phone alignment ended before all transcript words were consumed.", "native_phone_mismatch")
        chunk = speech_phones[cursor: cursor + count]
        for exp, actual in zip(expected_symbols, chunk):
            if _base_phone(exp) != str(actual.get("phone", "")):
                raise NativeAlignmentError(
                    f"Phone sequence mismatch near '{word}': expected {_base_phone(exp)}, got {actual.get('phone')}",
                    "native_phone_mismatch",
                )
        words.append({
            "word": word,
            "display_word": word,
            "start": round(float(chunk[0]["start"]), 4),
            "end": round(float(chunk[-1]["end"]), 4),
            "duration": round(float(chunk[-1]["end"]) - float(chunk[0]["start"]), 4),
        })
        cursor += count
    if cursor != len(speech_phones):
        # Do not silently hide a systematic model/G2P mismatch.
        raise NativeAlignmentError(
            f"Phone alignment produced {len(speech_phones) - cursor} unexpected non-silence phones.",
            "native_phone_mismatch",
        )
    return words


def _parse_option_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    result: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result.extend(shlex.split(line, posix=False))
    return result


def _make_ivector_config(extractor: Path, out_path: Path) -> None:
    splice_opts = extractor.joinpath("splice_opts").read_text(encoding="utf-8", errors="replace").strip()
    splice_conf = out_path.parent / "splice.conf"
    # Kaldi's shell recipe writes each splice option on its own line.
    _write_text(splice_conf, "\n".join(shlex.split(splice_opts)) + "\n")
    lines = [
        f"--cmvn-config={extractor / 'online_cmvn.conf'}",
        "--ivector-period=10",
        f"--splice-config={splice_conf}",
        f"--lda-matrix={extractor / 'final.mat'}",
        f"--global-cmvn-stats={extractor / 'global_cmvn.stats'}",
        f"--diag-ubm={extractor / 'final.dubm'}",
        f"--ivector-extractor={extractor / 'final.ie'}",
        "--num-gselect=5",
        "--min-post=0.025",
        "--posterior-scale=0.1",
        "--max-remembered-frames=1000",
        "--max-count=0",
    ]
    if (extractor / "online_cmvn_iextractor").exists():
        lines.append("--online-cmvn-iextractor=true")
    _write_text(out_path, "\n".join(lines) + "\n")


def run_native_alignment(normalized_wav: Path, transcript: str, *, root: Path | None = None) -> dict:
    if os.name != "nt":
        raise NativeAlignmentError("The native Aalto backend is Windows-only.", "native_windows_only")
    root = Path(root or runtime_root())
    status = native_status(root)
    if not status["ready"]:
        raise NativeAlignmentError(
            "Native Aalto runtime is incomplete:\n" + "\n".join(f"- {x}" for x in status["missing"]),
            "native_not_ready",
        )

    # Reuse Zundanen's transcript tokenization and syllable builder so the API
    # remains byte-compatible with the existing Docker backend.
    from aalto_alignment import _source_word_tokens, build_syllable_alignment, syllabify_transcript_for_display

    source_words = _source_word_tokens(transcript)
    if not source_words:
        raise NativeAlignmentError("No Finnish words were found in the transcript.", "transcript_missing")

    bindir = root / "bin"
    chain = root / "model" / "nnet3" / "chain"
    extractor = root / "model" / "nnet3" / "extractor"
    conf = root / "model" / "conf" / "mfcc_hires.conf"
    g2p_dir = root / "model" / "g2p"
    phone_ids, phone_names = _read_symbols(chain / "phones.txt")
    # compile-train-graphs-without-lexicon uses phone id 1 as the optional
    # inter-word silence/noise phone.  Kaldi language directories conventionally
    # reserve a silence-class phone there; Aalto may label it SIL or NSN.
    if 1 not in phone_names or _base_phone(phone_names[1]) not in _SILENCE:
        raise NativeAlignmentError(
            f"Aalto model phone id 1 is '{phone_names.get(1, '?')}', not a silence/noise phone.",
            "native_model_incompatible",
        )

    disambig_ids = sorted(idx for name, idx in phone_ids.items() if name.startswith("#"))
    if not disambig_ids:
        raise NativeAlignmentError("No Kaldi disambiguation phone symbols were found in phones.txt.", "native_model_incompatible")

    def exe(name: str) -> str:
        return str(bindir / name)

    with tempfile.TemporaryDirectory(prefix="zundanen_aalto_native_") as tmp_name:
        work = Path(tmp_name)
        wav = work / "input.wav"
        shutil.copy2(normalized_wav, wav)

        expected_symbols = _g2p_words(g2p_dir, source_words, phone_ids, work)

        # Minimal one-utterance Kaldi data files.
        utt = "zundanen"
        _write_text(work / "wav.scp", f"{utt} {wav}\n")
        _write_text(work / "utt2spk", f"{utt} zundanen_spk\n")
        _write_text(work / "spk2utt", f"zundanen_spk {utt}\n")

        # MFCC -> feats.ark + feats.scp
        _pipeline(
            [exe("compute-mfcc-feats.exe"), "--verbose=0", f"--config={conf}", f"scp:{work / 'wav.scp'}", "ark:-"],
            [exe("copy-feats.exe"), "--compress=true", "ark:-", f"ark,scp:{work / 'feats.ark'},{work / 'feats.scp'}"],
            cwd=work,
            timeout=180,
        )

        _run([
            exe("compute-cmvn-stats.exe"),
            f"--spk2utt=ark:{work / 'spk2utt'}",
            f"scp:{work / 'feats.scp'}",
            f"ark,scp:{work / 'cmvn.ark'},{work / 'cmvn.scp'}",
        ], cwd=work)

        cmvn_opts = _parse_option_file(chain / "cmvn_opts")
        _run([
            exe("apply-cmvn.exe"),
            *cmvn_opts,
            f"--utt2spk=ark:{work / 'utt2spk'}",
            f"scp:{work / 'cmvn.scp'}",
            f"scp:{work / 'feats.scp'}",
            f"ark,scp:{work / 'norm.ark'},{work / 'norm.scp'}",
        ], cwd=work)

        ivec_conf = work / "ivector_extractor.conf"
        _make_ivector_config(extractor, ivec_conf)
        _run([
            exe("ivector-extract-online2.exe"),
            f"--config={ivec_conf}",
            f"ark:{work / 'spk2utt'}",
            f"scp:{work / 'feats.scp'}",
            f"ark,scp:{work / 'ivectors.ark'},{work / 'ivectors.scp'}",
        ], cwd=work, timeout=240)

        # The graph compiler intentionally accepts a word-id sequence separately
        # from per-word phone sequences, so no dynamic L.fst/prepare_lang.sh is
        # needed.  This is the key to removing Bash from the Windows path.
        word_ids = list(range(1, len(source_words) + 1))
        _write_text(work / "words.int", utt + " " + " ".join(map(str, word_ids)) + "\n")
        phone_lines: list[str] = []
        for i, symbols in enumerate(expected_symbols):
            ids = [phone_ids[s] for s in symbols]
            phone_lines.append(f"{utt}.{i} " + " ".join(map(str, ids)))
        _write_text(work / "phones.int", "\n".join(phone_lines) + "\n")
        _write_text(work / "disambig.int", " ".join(map(str, disambig_ids)) + "\n")

        _run([
            exe("compile-train-graphs-without-lexicon.exe"),
            f"--read-disambig-syms={work / 'disambig.int'}",
            str(chain / "tree"),
            str(chain / "final.mdl"),
            f"ark,t:{work / 'words.int'}",
            f"ark,t:{work / 'phones.int'}",
            f"ark:{work / 'graphs.ark'}",
        ], cwd=work)

        try:
            frame_subsampling = int((chain / "frame_subsampling_factor").read_text(encoding="utf-8").strip())
        except Exception:
            frame_subsampling = 3

        _run([
            exe("nnet3-align-compiled.exe"),
            "--transition-scale=1.0",
            "--acoustic-scale=0.1",
            "--self-loop-scale=0.1",
            f"--online-ivectors=scp:{work / 'ivectors.scp'}",
            "--online-ivector-period=10",
            f"--frame-subsampling-factor={frame_subsampling}",
            "--frames-per-chunk=50",
            "--extra-left-context=0",
            "--extra-right-context=0",
            "--extra-left-context-initial=-1",
            "--extra-right-context-final=-1",
            "--use-gpu=no",
            "--beam=10",
            "--retry-beam=40",
            str(chain / "final.mdl"),
            f"ark:{work / 'graphs.ark'}",
            f"scp:{work / 'norm.scp'}",
            f"ark:{work / 'ali.ark'}",
        ], cwd=work, timeout=300)

        frame_shift = 0.01 * frame_subsampling
        phone_ctm = work / "phone.ctm"
        _run([
            exe("ali-to-phones.exe"),
            "--ctm-output=true",
            f"--frame-shift={frame_shift:.8f}",
            str(chain / "final.mdl"),
            f"ark:{work / 'ali.ark'}",
            str(phone_ctm),
        ], cwd=work)

        phones = _parse_ctm(phone_ctm, phone_names)
        if not phones:
            raise NativeAlignmentError("Native Aalto returned no phone intervals.", "empty_phone_alignment")
        words = _reconstruct_words(source_words, expected_symbols, phones)
        syllables = build_syllable_alignment(words, phones)

        return {
            "words": words,
            "phones": phones,
            "syllables": syllables,
            "syllabified_transcript": syllabify_transcript_for_display(transcript),
            "image": "Aalto/Kaldi native Windows",
            "image_downloaded": False,
            "source": "Finnish TTS (before RVC; 16 kHz native Aalto alignment copy)",
            "backend": "native",
        }
