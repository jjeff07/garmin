# garmin-dive → MySSI logbook

A GitHub Action fetches your most recent Garmin dive and **logs it straight into
your MySSI web logbook** — no watch app, no QR code, no scanning.

```
GitHub Action (every 6h + on demand)
  ├─ garminconnect: resume token (self-refreshing) or email/password login
  ├─ GET /gcsalt-api/diving/v1/dive/summary     → newest dive
  ├─ GET /download-service/files/activity/<id>  → FIT (water temp, water type)
  ├─ POST my.divessi.com/code/process/mydivelog_18.php   ← dive appears in MySSI
  └─ commit public/latest.json                  (debug snapshot + optional QR payload)
```

> Scrapes two **undocumented private web APIs** (Garmin Connect via the community
> `garminconnect` package; the MySSI PHP logbook via a captured form POST).
> Unsupported, breaks when either vendor changes their site, and arguably against
> their ToS. Fine for a personal tool on your own accounts.

## Layout

| Path | What |
|---|---|
| `src/dive_qr/garmin.py` | fetch newest dive (`GarminConnectSource` token/login, `CookieSource`) |
| `src/dive_qr/fit.py` | parse a dive `.fit` → normalised `Dive` |
| `src/dive_qr/ssi_push.py` | map `Dive` → MySSI add-dive form + `SSIClient` POST |
| `src/dive_qr/ssi.py` | build the `dive;noid;…` QR string (kept for the optional watch path) |
| `src/dive_qr/refresh.py` | CLI entry point (`dive-qr-refresh`) |
| `bootstrap_token.py` | run once locally to mint the `GARMIN_TOKENS` secret |
| `reference/` | reverse-engineered MySSI logbook API spec + field template |
| `tests/` | pure-mapping tests against `tests/data/sample_dive.fit` |

## Local dev (no accounts needed)

```bash
uv run --extra dev pytest
uv run dive-qr-refresh --from-fit tests/data/sample_dive.fit --dry-run
```

`--from-fit` runs the whole pipeline from a local `.fit` — no Garmin, no SSI.
`--dry-run` prints the exact form body that would be POSTed.

## Going live

### 1. Make the repo private
It will contain your dive data. Settings → General → Change visibility → Private.

### 2. Garmin auth — pick one

| Secrets | How | Notes |
|---|---|---|
| `GARMIN_TOKENS` | `uv run --with garminconnect python bootstrap_token.py` → paste blob | preferred; ~1-year token, no per-run login |
| `GARMIN_EMAIL` + `GARMIN_PASSWORD` | full SSO login | no-MFA accounts; first run stores a token (see self-refresh) |
| `GARMIN_COOKIE` (+ `GARMIN_CSRF`, `GARMIN_APP_VER`) | DevTools → any `gc-api` request → Copy as cURL | expires ~3 months |

`refresh.py` tries them in that order. **Self-refresh:** when a run's token blob
changes (proactive refresh or fallback login) it's written to `garmin_tokens.new`
and the workflow pushes it back into `GARMIN_TOKENS` — so seeding with only
email/password works, and password login becomes the rare recovery path. That
secret write needs `GH_PAT` (fine-grained PAT, this repo, **Secrets: read+write**);
without it the run still works but the token isn't persisted.

### 3. MySSI auth + identity

```bash
gh secret set SSI_EMAIL           # your MySSI login email
gh secret set SSI_PASSWORD        # your MySSI password
gh secret set SSI_USER_ID         # your MySSI member id (Profile screen; a 7-digit number)
# optional:
gh secret set SSI_FIRST_NAME
gh secret set SSI_LAST_NAME
```

Non-secret knobs are `workflow_dispatch` **inputs** (shown on the "Run workflow"
form), not secrets:

| Input | Default | |
|---|---|---|
| `ssi_dive_site_id` | *(blank)* | SSI dive-site DB id to log against; blank = none, pick the site in MySSI |
| `ssi_divetype_id` | `24` | 23 Education / 24 Fun Dive / 138 Scientific / 139 Work |
| `ssi_comment` | `Imported from Garmin Descent` | note on each imported dive |
| `force_push` | `false` | log the dive even if it was already logged |

On `schedule` / `repository_dispatch` runs these fall back to the same defaults
(handled in `refresh.py`).

`refresh.py` logs in each run at `www.divessi.com/bridge/code/process/signin`
(multipart POST, no CSRF; the session cookie is `.divessi.com`-scoped so it also
covers the `my.` logbook host). Nothing to expire.

**Override:** set `SSI_COOKIE` (the whole `Cookie:` header from a logged-in
`my.divessi.com` request) instead, if you'd rather not store the password. It
expires (PHP session; lifetime unverified) — re-copy when the push logs
`session rejected`.

`SSI_EMAIL`+`SSI_PASSWORD` wins over `SSI_COOKIE`. With neither, the Action still
runs and writes `latest.json`, just skipping the push.

### 4. Enable the workflow
`.github/workflows/refresh.yml` runs every 6h + `gh workflow run
refresh-latest-dive` + `repository_dispatch {event_type: dive}` (phone shortcut,
right after a dive). GitHub pauses cron after 60 days of no commits.

**Dedup:** `latest.json` records the `pushed` dive key; a run whose newest dive
matches it skips the push. `--force-push` overrides; `--no-push` writes
`latest.json` only.

## What gets logged

`Dive` → MySSI add-dive form (`odin_user_log_*`). Full spec + enum tables +
82-field template: [reference/ssi_logbook_api.md](reference/ssi_logbook_api.md).

| MySSI field | From |
|---|---|
| `dive_type` = `0` (SCUBA) | fixed |
| `date_sel2_*` + `entry_time` | dive start, local |
| `dive_nr` | dive number |
| `var_divetype_id` = `24` Fun Dive | `ssi_divetype_id` input |
| `divetime` | totalTime → min |
| `depth_m` / `_ft`, `avg_depth_m` | maxDepth / avgDepth |
| `watertemp_c` / `_f` | FIT min `record.temperature` |
| `var_watertype_id` (4 fresh / 5 salt) | FIT `dive_settings.water_type` |
| `dive_sites_id` | `ssi_dive_site_id` input (else blank — pick in MySSI) |
| `user_master_id` | `SSI_USER_ID` |
| `comment` | `ssi_comment` input |

`airtemp`, `vis`, buddies, gas/nitrox, conditions: not sent — add in MySSI.

## Optional: the QR / watch path

`latest.json` still carries a `dive;noid;…` string. If you later want a Garmin
watch widget to show it as a QR (e.g. MySSI auth breaks), it's there; see git
history for the Connect IQ Contents-API fetch notes.
