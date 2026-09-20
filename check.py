"""check.py -- every selftest, then pyflakes. Exit 1 on any failure."""
import subprocess
import sys

MODULES = ["scoring", "sports", "weeks", "sync", "records", "stats"]
fails = 0
for m in MODULES:
    r = subprocess.run([sys.executable, "-m", f"atlas.{m}", "--selftest"], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip().splitlines()[-1])
    fails += r.returncode != 0
r = subprocess.run([sys.executable, "-m", "pyflakes", "atlas", "check.py", "setup.py"], capture_output=True, text=True)
print(r.stdout.strip() or "pyflakes: clean")
fails += r.returncode != 0
print("OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
