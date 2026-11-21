from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid-file", required=True)
    args = parser.parse_args()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    payload = {"worker_pid": __import__("os").getpid(), "child_pid": child.pid}
    target = Path(args.pid_file).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    time.sleep(600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
