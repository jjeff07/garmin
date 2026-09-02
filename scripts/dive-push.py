#!/usr/bin/env python
"""a-Shell launcher: run from any directory, no cd / PYTHONPATH needed.

    python ~/Documents/dive-push.py dive.fit --lat 41.37 --lng -83.31

Installs to ~/Documents/dive-push.py (ashell-install.sh). Expects the code at
~/Documents/garmin_ssi/ and (optionally) ~/Documents/.ssienv.
"""

import os
import sys

HOME = os.path.expanduser("~/Documents")
sys.path.insert(0, HOME)
os.chdir(HOME)
os.environ.setdefault("PYTHONUNBUFFERED", "1")

print(f"[dive-push] cwd={os.getcwd()} python={sys.version.split()[0]}", flush=True)

try:
    from garmin_ssi.fit_push import main
except ModuleNotFoundError as e:
    print(f"[dive-push] cannot import garmin_ssi ({e}) - is {HOME}/garmin_ssi/ populated?")
    sys.exit(2)

argv = sys.argv[1:]
env = os.path.join(HOME, ".ssienv")
if "--env-file" not in argv and os.path.exists(env):
    argv += ["--env-file", env]

sys.exit(main(argv))
