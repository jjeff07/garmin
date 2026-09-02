# Run it on the phone (a-Shell + Shortcuts) — no GitHub

`garmin_ssi.fit_push` needs only `fitparse` plus stdlib `urllib` for HTTP to
`divessi.com` — so it runs unchanged in
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

The installer also drops **`~/Documents/dive-push.py`** — a launcher that fixes
`sys.path`, `chdir`s to `~/Documents` and loads `.ssienv` itself, so you never
need `cd` or `PYTHONPATH` (the Shortcut's a-Shell command does **not** start in
`~/Documents`).

**Smoke test** (no push) — run from any directory:

```sh
python ~/Documents/dive-push.py some-dive.fit --lat 41.37 --lng -83.31 --dry-run
```

---

## 2. The Shortcut

New Shortcut in the Shortcuts app, these actions in order:

| # | Action | Settings |
|---|--------|----------|
| 1 | **Get File** | Turn on *Show Document Picker*. (Or set the shortcut to *Receive Files from Share Sheet* and skip this.) |
| 2 | **Base64 Encode** | input = step 1's file |
| 3 | **Replace Text** | Find `\n` (**regex on**), Replace *(empty)*; input = step 2. Set variable **B64**. |
| 4 | **Get Current Location** | — |
| 5 | **Run a-Shell command** — **Input: None** | Command: <br>`printf %s "B64" \| base64 -d > ~/Documents/dive.fit && python ~/Documents/dive-push.py ~/Documents/dive.fit --lat LAT --lng LNG 2>&1` <br> insert **B64** and the **Latitude** / **Longitude** magic variables. Turn on **Run in Extension**. |
| 6 | **Show Alert** (not Show Notification — it truncates) | Message: the output of step 5. |

This writes the FIT *inside* a-Shell from the base64 text — no *Save File* /
Files-picker dance. Your Connect exports are ~650 bytes (~900 base64 chars), so
the command stays small.

Add the Shortcut to the Share Sheet (Shortcut settings → *Show in Share Sheet*,
accept *Files*) so you can run it straight from a `.fit` you exported.

### If `printf %s` misbehaves in a-Shell

Use a plain here-string via `echo` instead:
`echo "B64" | base64 -d > ~/Documents/dive.fit && ...` — base64's alphabet has no
`"`, `$` or backticks so double-quotes are safe. If output is still empty, run
just `echo hi && python --version` (Input: None) + Show Alert to confirm a-Shell
runs at all.

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

Re-run the step-1 one-liner. It re-fetches the code + `dive-push.py` and keeps
your `.ssienv`.

## Debugging

- `python ~/Documents/dive-push.py dive.fit --lat .. --lng .. --dry-run` in
  a-Shell directly — full traceback, no Shortcut in the way.
- The launcher prints `[dive-push] cwd=… python=…` first; if you don't see even
  that, a-Shell isn't running the command (check the action's **Input: None**,
  and Settings ▸ Shortcuts ▸ *Allow Running Scripts*).
- `2>&1` on the command sends Python errors back too; show them with **Show
  Alert** / **Quick Look**, never Show Notification.
