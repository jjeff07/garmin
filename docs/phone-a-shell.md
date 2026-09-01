# Run it on the phone (a-Shell + Shortcuts) — no GitHub

The FIT path (`garmin_ssi.fit_push`) never touches Garmin, so it needs only
`fitparse` plus HTTP to `divessi.com`. `divessi.com` doesn't need browser-
fingerprint impersonation, so `src/garmin_ssi/_http.py` falls back to stdlib
`urllib` when `curl_cffi` isn't installed — which is the case in
[a-Shell](https://github.com/holzschu/a-shell) on iOS.

---

## 1. One-time setup in a-Shell

Make a **fine-grained PAT** (github.com → Settings → Developer settings →
Fine-grained tokens): repo access = `jjeff07/garmin` only, permission
**Contents: Read-only**.

In a-Shell, one command — pip-installs `fitparse`, fetches the code into
`~/Documents/garmin_ssi/`, and scaffolds `~/Documents/.ssienv`:

```sh
GH_PAT=github_pat_xxx; curl -sfL -H "Authorization: Bearer $GH_PAT" \
  https://raw.githubusercontent.com/jjeff07/garmin/main/scripts/ashell-install.sh \
  | GH_PAT=$GH_PAT sh
```

(Use `BRANCH=fit-only` before `sh` if that branch isn't merged yet:
`... | GH_PAT=$GH_PAT BRANCH=fit-only sh`.)

Then fill in `~/Documents/.ssienv`:

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

**Updating later:** re-run the same one-liner (it re-fetches the `.py` files and
leaves your `.ssienv` alone).

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

Re-run the step-1 one-liner (or `sh ~/Documents/garmin_ssi/../ashell-install.sh`
if you saved it). It re-fetches the nine `.py` files and keeps your `.ssienv`.
