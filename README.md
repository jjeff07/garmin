# garmin-dive → MySSI logbook

A GitHub Action fetches your most recent Garmin dive and **logs it straight into
your MySSI web logbook** — no watch app, no QR code, no scanning.

```
GitHub Action (every 6h + on demand)
  ├─ garminconnect: resume token (self-refreshing) or email/password login
  ├─ GET /gcsalt-api/diving/v1/dive/summary     → newest dive
  ├─ GET /download-service/files/activity/<id>  → FIT (water temp, water type)
  ├─ POST my.divessi.com/code/process/mydivelog_18.php   ← dive appears in MySSI
  └─ commit public/latest.json                  (debug snapshot + dedup ledger)
```

> Scrapes two **undocumented private web APIs** (Garmin Connect via the community
> `garminconnect` package; the MySSI PHP logbook via a captured form POST).
> Unsupported, breaks when either vendor changes their site, and arguably against
> their ToS. Fine for a personal tool on your own accounts.

## Layout

| Path | What |
|---|---|
| `src/garmin_ssi/garmin.py` | fetch newest dive (`GarminConnectSource` token/login, `CookieSource`) |
| `src/garmin_ssi/fit.py` | parse a dive `.fit` → normalised `Dive` |
| `src/garmin_ssi/ssi_push.py` | map `Dive` → MySSI add-dive form + `SSIClient` login/POST |
| `src/garmin_ssi/ssi.py` | build the compact `dive;noid;…` summary written to `latest.json` |
| `src/garmin_ssi/refresh.py` | CLI `garmin-ssi` — fetch newest dive from Garmin, push |
| `src/garmin_ssi/fit_push.py` | CLI `garmin-ssi-fit` — push a dive from a local `.fit`, no Garmin |
| `src/garmin_ssi/ssi_sites.py` | lat/lng → SSI dive-site id via the public locator API |
| `bootstrap_token.py` | run once locally to mint the `GARMIN_TOKENS` secret |
| `reference/` | reverse-engineered MySSI logbook API spec + field template |
| `tests/` | pure-mapping tests against `tests/data/sample_dive.fit` |

## Local dev (no accounts needed)

```bash
uv run --extra dev pytest
uv run garmin-ssi --from-fit tests/data/sample_dive.fit --dry-run
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
gh secret set SSI_DIVE_SITE_ID    # REQUIRED - see below
# optional:
gh secret set SSI_FIRST_NAME
gh secret set SSI_LAST_NAME
```

**`SSI_DIVE_SITE_ID` is required.** `mydivelog_18.php` returns a success
redirect but **silently creates nothing** if the dive has no site. Every import
is logged against this one site; re-assign in MySSI afterwards if it was
somewhere else. Find an id by opening any existing dive's edit page and reading
`odin_user_log_dive_sites_id`, or search the site on the add-dive form. Known for
this account: `1018800` (North Olmsted Rec Center), `1965` (White Star Quarry).

Non-secret knobs are `workflow_dispatch` **inputs** (shown on the "Run workflow"
form):

| Input | Default | |
|---|---|---|
| `ssi_dive_site_id` | *(blank)* | overrides the `SSI_DIVE_SITE_ID` secret for one manual run |
| `ssi_divetype_id` | `24` | 23 Education / 24 Fun Dive / 138 Scientific / 139 Work |
| `ssi_comment` | `Imported from Garmin Descent` | note on each imported dive |
| `force_push` | `false` | log the dive even if it was already logged |

`ssi_divetype_id` / `ssi_comment` fall back to those defaults on
`schedule` / `repository_dispatch` runs (handled in `refresh.py`).

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
| `dive_sites_id` | **`SSI_DIVE_SITE_ID`** (required; site-less dives are silently dropped) |
| `user_master_id` | `SSI_USER_ID` |
| `comment` | `ssi_comment` input |

`airtemp`, `vis`, buddies, gas/nitrox, conditions: not sent — add in MySSI.

`public/latest.json` also carries the same data as a one-line `dive;noid;…`
string (the MySSI QR-import format) — handy for eyeballing a run and, if MySSI's
web login ever breaks, feeding a QR the phone app can scan. Git history has the
earlier Connect IQ watch-app notes.

## Alternative: FIT upload, no Garmin API

`.github/workflows/fit-to-ssi.yml` + `garmin-ssi-fit` log a dive straight from a
`.fit` file — no `garminconnect`, no 429s, no token to babysit. You supply the
FIT; an Apple Shortcut can do it hands-free.

> Or skip GitHub entirely and run it **on the phone** in a-Shell — the FIT path
> falls back to stdlib `urllib` (no `curl_cffi`). See
> [docs/phone-a-shell.md](docs/phone-a-shell.md).

```
Garmin Connect app  → share the dive .fit → Shortcut base64-encodes it
Shortcut → PUT .../contents/incoming/dive-<epoch>.fit    {content: <base64>, message: "dive [skip ci]"}
        (+ if the pool/site has no GPS in the FIT, also PUT
           .../contents/incoming/dive-<epoch>.json        {"lat": <Current Location>, "lng": ...})
        Authorization: Bearer <fine-grained PAT, Contents: write, THIS repo>
push to incoming/**.fit  → workflow runs garmin-ssi-fit  → dive in MySSI
                         → moves the file(s) to processed/ [skip ci]
```

Pool dives have no GPS in the FIT, so the `.json` sidecar (Shortcut's **Get
Current Location**) is what places them. Same `dive-<epoch>` stem for both files.

- **Unique filename per dive** (`dive-<epoch>.fit`) so the Contents API always
  *creates* (no `sha` fetch needed).
- **`[skip ci]`** in the commit message is required so the workflow's own
  archive commit doesn't loop.
- Same SSI secrets as above (`SSI_EMAIL`/`SSI_PASSWORD`, `SSI_USER_ID`,
  **`SSI_DIVE_SITE_ID`**). No Garmin secrets.
- **Dedup:** a sha256 of each FIT is recorded in `state/pushed_fits.json`;
  re-running or re-pushing the same file is a no-op (`--force` overrides).
- Test without a Shortcut: `gh workflow run fit-to-ssi -f path=tests/data/sample_dive.fit`,
  or locally `uv run garmin-ssi-fit tests/data/sample_dive.fit --dry-run`.

### Dive site — resolved from GPS

`fit_push.py` picks the dive site automatically:

1. **The FIT's surface fix** — `session`/`lap` `start_position` / `end_position`
   (a Descent only fixes GPS at the surface, but it's usually there). Failing
   that, a `dive-<epoch>.json` sidecar `{"lat": …, "lng": …}` from the phone.
2. Those coords → `POST www.divessi.com/api/locationServices.php` (the public
   dive-site locator, `src/garmin_ssi/ssi_sites.py`) → nearest site within 5 km,
   with its real `id`. No login; it self-fetches the `SSI_APIKEY` + session
   cookie from the locator page.
3. If there's no fix and no site within range → falls back to
   `SSI_DIVE_SITE_ID`. If that's unset too, the dive is skipped (a site-less POST
   is silently dropped by MySSI).

`SSI_API_KEY` secret is optional (the locator fetches its own). `SSI_DIVE_SITE_ID`
is now just the fallback — handy for a home pool that isn't in the public DB.
