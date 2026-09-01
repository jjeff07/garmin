# Run it on the phone (a-Shell + Shortcuts) — no GitHub

The FIT path (`garmin_ssi.fit_push`) never touches Garmin, so it needs only
`fitparse` plus HTTP to `divessi.com`. `divessi.com` doesn't need browser-
fingerprint impersonation, so `src/garmin_ssi/_http.py` falls back to stdlib
`urllib` when `curl_cffi` isn't installed — which is the case in
[a-Shell](https://github.com/holzschu/a-shell) on iOS.

---

## 1. One-time setup in a-Shell

Open a-Shell and run:

```sh
pip install fitparse
mkdir -p ~/Documents/garmin_ssi
```

**Copy the code in.** In the Files app: `On My iPhone ▸ a-Shell ▸ garmin_ssi`,
and drop in these files from `src/garmin_ssi/`:

```
__init__.py  _http.py  config.py  fit.py  fit_push.py
model.py  ssi.py  ssi_push.py  ssi_sites.py
```

(`garmin.py` and `refresh.py` are the Garmin-API path — not needed here.)

**Credentials file** — `~/Documents/.ssienv`, one `KEY=VALUE` per line:

```sh
cat > ~/Documents/.ssienv <<'EOF'
SSI_EMAIL=you@example.com
SSI_PASSWORD=your-myssi-password
SSI_USER_ID=4195537
SSI_DIVE_SITE_ID=1018800
EOF
chmod 600 ~/Documents/.ssienv
```

`SSI_DIVE_SITE_ID` is the fallback used when there are no coordinates near a
known public dive site (e.g. an indoor pool). `1018800` = North Olmsted Rec
Center, `1965` = White Star Quarry.

**Smoke test** (no push):

```sh
cd ~/Documents
python -m garmin_ssi.fit_push some-dive.fit --env-file .ssienv --dry-run
```

---

## 2. The Shortcut

New Shortcut in the Shortcuts app, these actions in order:

| # | Action | Settings |
|---|--------|----------|
| 1 | **Get File** | Turn on *Show Document Picker*. (Or set the shortcut to *Receive Files from Share Sheet* and skip this.) |
| 2 | **Get Current Location** | — |
| 3 | **Save File** | File: the output of step 1. *Ask Where to Save* → **off**. Destination: `On My iPhone ▸ a-Shell ▸ dive.fit`. *Overwrite If File Exists* → **on**. |
| 4 | **Text** | `cd ~/Documents && python -m garmin_ssi.fit_push dive.fit --env-file .ssienv --lat LAT --lng LNG 2>&1` — replace `LAT`/`LNG` by inserting the **Latitude** and **Longitude** magic variables from step 2. |
| 5 | **Run a-Shell command** (a-Shell's action; may be *Execute Command*) | Command: the **Text** from step 4. Turn on **Run in Extension** (runs in the background, no app switch). |
| 6 | **Show Notification** (or **Show Alert**) | Body: the output of step 5. |

Add the Shortcut to the Share Sheet (Shortcut settings → *Show in Share Sheet*,
accept *Files*) so you can run it straight from a `.fit` you exported.

### Getting the `.fit` out of Garmin

Garmin Connect app → the dive → **⋯ / Share** → **Export Original** (`.fit`) →
save to Files, or share directly into the Shortcut.

---

## 3. What a run does

```
parse dive.fit  →  lat/lng from --lat/--lng (else the FIT's own surface fix,
                    else SSI_DIVE_SITE_ID)
             →  POST divessi.com locator  →  nearest dive-site id
             →  log in to MySSI  →  POST the dive
             →  record sha256 in ~/Documents/state/pushed_fits.json
```

Success prints `MySSI: {'ok': True, 'detail': 'created (logbook N -> N+1 dives)'}`.
Re-running the same file is a no-op (`--force` to override).

## 4. Updating

Re-copy the nine `.py` files into `~/Documents/garmin_ssi/` whenever they change.
