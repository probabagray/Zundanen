from __future__ import annotations

import argparse
import json
from aalto_native_alignment import native_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Zundanen Windows-native Aalto runtime.")
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Check only that packaged files exist; do not launch a Kaldi executable.",
    )
    args = parser.parse_args()
    status = native_status(check_executable=not args.files_only)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    key = "files_ready" if args.files_only else "ready"
    return 0 if status.get(key) else 1


if __name__ == "__main__":
    raise SystemExit(main())
