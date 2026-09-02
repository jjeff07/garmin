# garmin-ssi — dive `.fit` → MySSI logbook

Log a scuba dive into your [MySSI](https://my.divessi.com) web logbook straight
from the dive's `.fit` file. No Garmin API, no `garminconnect`, no tokens. One
pure dependency (`fitparse`); HTTP is stdlib `urllib`, so it also runs on iOS in
[a-Shell](https://github.com/holzschu/a-shell).

```
dive.fit  ──parse──▶  Dive  ──▶  dive site from GPS  (public SSI locator)
                                 │  FIT surface fix → phone location → SSI_DIVE_SITE_ID
                                 ▼
                       log in to MySSI  ──▶  POST /code/process/mydivelog_18.php
                                 ▼
                       dive in your logbook  (+ sha256 in state/pushed_fits.json)
```

> Scrapes MySSI's undocumented PHP logbook (a captured form POST) and its public
> dive-site locator. Unsupported, breaks if SSI changes their site. Personal use,
> your own account.

## Run it

```bash
uv run --extra dev pytest
uv run garmin-ssi-fit path/to/dive.fit --dry-run     # parse + resolve site, no push
uv run garmin-ssi-fit path/to/dive.fit               # real: log in + POST
```

Auth + identity come from the environment (a Shortcut env-file, a shell, or CI
secrets):

| var | |
|---|---|
| `SSI_EMAIL` + `SSI_PASSWORD` | MySSI login (preferred) |
| `SSI_COOKIE` | whole `Cookie:` header from a logged-in `my.divessi.com` request (alternative) |
| `SSI_USER_ID` | your MySSI member id (Profile screen) |
| `SSI_DIVE_SITE_ID` | fallback site id when GPS finds nothing — `1018800` North Olmsted, `1965` White Star Quarry |
| `SSI_DIVETYPE_ID` | `24` Fun Dive (default) · 23 Education · 138 Scientific · 139 Work |
| `SSI_COMMENT` | note on each dive (default "Imported from Garmin Descent") |
| `SSI_API_KEY` | optional; the locator self-fetches one |

Copy [`sample.env`](sample.env) to `.ssienv` and fill it in.

CLI flags: `--env-file <file>` (load the vars), `--lat/--lng` (override coords),
`--force` (ignore the pushed-fits ledger), `--dry-run`, `--ledger <path>`.

## On the phone (a-Shell + a Shortcut)

No servers — export the `.fit` from Garmin Connect, a Shortcut hands it to
a-Shell with your location, a-Shell runs `garmin-ssi-fit`.
**→ [docs/phone-a-shell.md](docs/phone-a-shell.md)**

## Dive site resolution

1. **FIT surface fix** — `session`/`lap` `start_position` / `end_position`
   (semicircles). A Descent only fixes GPS at the surface, so a pool dive won't
   have one.
2. **Phone location** — `--lat/--lng`, or a `dive-<epoch>.json` sidecar
   `{"lat": …, "lng": …}` next to the FIT.
3. Coords → `POST www.divessi.com/api/locationServices.php` (public locator,
   `ssi_sites.py`; bootstraps its own cookie + `SSI_APIKEY`) → nearest site
   within 5 km, real `id`.
4. Nothing found → `SSI_DIVE_SITE_ID`. Still nothing → the dive is skipped (MySSI
   silently drops a site-less POST).

## Layout

| Path | What |
|---|---|
| `src/garmin_ssi/fit.py` | parse a `.fit` → `Dive` |
| `src/garmin_ssi/ssi_sites.py` | lat/lng → SSI dive-site id (public locator) |
| `src/garmin_ssi/ssi_push.py` | `Dive` → add-dive form + `SSIClient` login/POST |
| `src/garmin_ssi/fit_push.py` | CLI `garmin-ssi-fit` |
| `src/garmin_ssi/_http.py` | tiny stdlib-`urllib` HTTP session |
| `sample.env` | copy to `.ssienv` |
| `scripts/ashell-install.sh` | a-Shell one-liner: pip + fetch code + scaffold `.ssienv` |
| `reference/ssi_logbook_api.md` | reverse-engineered logbook + locator API |
| `tests/data/*.fit` | `sample_dive.fit` (no GPS), `dive_with_gps.fit` (lap end fix) |

## What gets logged

`Dive` → the MySSI add-dive form. Full 82-field spec + enum tables:
[reference/ssi_logbook_api.md](reference/ssi_logbook_api.md).

| MySSI field | from |
|---|---|
| `dive_type` = `0` (SCUBA) | fixed |
| `date_sel2_*` + `entry_time` | dive start (local) |
| `dive_nr` | FIT `dive_summary.dive_number` |
| `var_divetype_id` | `SSI_DIVETYPE_ID` |
| `divetime` | `session.total_elapsed_time` → min |
| `depth_m` / `_ft`, `avg_depth_m` | `dive_summary.max_depth` / `avg_depth` |
| `watertemp_c` / `_f` | min `record.temperature` |
| `var_watertype_id` (4 fresh / 5 salt) | `dive_settings.water_type` |
| `dive_sites_id` | resolved from GPS, else `SSI_DIVE_SITE_ID` |
| `user_master_id` | `SSI_USER_ID` |
| `comment` | `SSI_COMMENT` |

`airtemp`, `vis`, buddies, gas/nitrox, conditions: not sent — add in MySSI.
