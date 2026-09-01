# Run it on the phone (a-Shell + Shortcuts) — no GitHub

The FIT path (`garmin_ssi.fit_push`) never touches Garmin, so it needs only
`fitparse` plus HTTP to `divessi.com`. `divessi.com` doesn't need browser-
fingerprint impersonation, so `src/garmin_ssi/_http.py` falls back to stdlib
`urllib` when `curl_cffi` isn't installed — which is the case in
[a-Shell](https://github.com/holzschu/a-shell) on iOS.

## One-time setup in a-Shell

```sh
pip install fitparse
mkdir -p ~/Documents/garmin_ssi
# then copy src/garmin_ssi/*.py into ~/Documents/garmin_ssi/
#   - Files.app drag & drop, or
#   - a Shortcut "Put File" of a zip, unzip in a-Shell, or
#   - pip install --no-deps "git+https://<TOKEN>@github.com/jjeff07/garmin"
```

Store your SSI login where the script can read it (a-Shell keeps `~/Documents`
between runs):

```sh
cat > ~/Documents/.ssienv <<'EOF'
export SSI_EMAIL='you@example.com'
export SSI_PASSWORD='...'
export SSI_USER_ID='4195537'
export SSI_DIVE_SITE_ID='1018800'   # fallback (indoor pool etc.)
EOF
chmod 600 ~/Documents/.ssienv
```

## The run command

```sh
cd ~/Documents && . ./.ssienv && python -m garmin_ssi.fit_push "$1"
```

`$1` is the `.fit` file a-Shell received. If a `<same-stem>.json` file with
`{"lat": .., "lng": ..}` sits next to it, the dive site is looked up from those
coords; otherwise `SSI_DIVE_SITE_ID` is used. The FIT's own surface fix is used
first if it has one.

Output on success: `MySSI: {'ok': True, 'detail': 'created (logbook N -> N+1 dives)'}`.
A sha256 ledger at `~/Documents/state/pushed_fits.json` stops a re-run
duplicating a dive (`--force` to override).

## The Shortcut

1. **Receive** the dive `.fit` (share sheet from Garmin Connect, or pick in Files).
2. **Get Current Location** → build `{"lat": …, "lng": …}` text.
3. **a-Shell → Put File**: the `.fit` as `dive.fit` into a-Shell's `~/Documents`.
4. **a-Shell → Put File**: the location JSON as `dive.json` (same stem).
5. **a-Shell → Execute Command** (run *In Extension* to stay in the background):
   `cd ~/Documents && . ./.ssienv && python -m garmin_ssi.fit_push dive.fit`
6. **a-Shell → Get File** / read the command output; show a notification with the
   `ok` / `detail` line.

No repo, no PAT, no Actions, no cron. The only moving part is a-Shell + this
folder of `.py` files.

## Updating the code

Re-copy `src/garmin_ssi/*.py` into `~/Documents/garmin_ssi/` whenever it changes.
`_http.py`, `fit.py`, `fit_push.py`, `ssi_push.py`, `ssi_sites.py`, `ssi.py`,
`model.py`, `config.py`, `__init__.py` — that's the whole FIT path. `garmin.py`
and `refresh.py` are not needed on the phone (they're the Garmin-API path and do
need `curl_cffi`).
