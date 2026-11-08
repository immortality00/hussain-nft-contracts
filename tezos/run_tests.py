"""Run every SmartPy test file; exit 1 if any fails.

    tezos/.venv/bin/python tezos/run_tests.py

Each file runs in its own process, from tezos/build/, where SmartPy writes
each scenario's compiled contracts and log.
"""

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")


def main():
    os.makedirs(BUILD, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=HERE)
    failed = 0
    for path in sorted(glob.glob(os.path.join(HERE, "tests", "test_*.py"))):
        result = subprocess.run(
            [sys.executable, path], cwd=BUILD, env=env, capture_output=True, text=True
        )
        name = os.path.basename(path)
        if result.returncode == 0:
            print("ok      " + name)
            continue
        failed += 1
        print("FAILED  " + name)
        lines = [l for l in result.stderr.splitlines() if "is deprecated" not in l]
        print("\n".join("        " + l for l in lines[-15:]))
    print("%d failed" % failed if failed else "all passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
