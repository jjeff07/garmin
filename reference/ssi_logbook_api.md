# MySSI web logbook — "Add Dive" API (reverse-engineered 2026-09-01)

Captured by walking `my.divessi.com/mydivelog/add` in a browser and reading the
`<form id="add_log">` element + the resulting request.

## Login

```
POST https://www.divessi.com/bridge/code/process/signin
Content-Type: multipart/form-data
```

Multipart fields: `username`, `password`, `rememberMe` (`on`/`off`), `auth=Portal`.
**No CSRF token.** A prior `PHPSESSID` (from any GET on the site) is sent but not
authoritative.

Response: `200` + a redirect stub to `/myssi`, with

```
Set-Cookie: PHPSESSID=<new>; path=/; domain=.divessi.com; secure
Set-Cookie: mid=<user_master_id>; Max-Age=86400; domain=.divessi.com
```

The `.divessi.com` domain means one session covers both `www.` (login) and `my.`
(logbook). Failure re-renders the login page (no `/myssi` redirect).

## Endpoint

```
POST https://my.divessi.com/code/process/mydivelog_18.php
Content-Type: application/x-www-form-urlencoded
Cookie: PHPSESSID=<session>; mid=<user_master_id>
```

- **Auth: the PHP session cookie only.** No CSRF token anywhere (no meta tag, no
  hidden token field, no nonce). A valid `PHPSESSID` for a logged-in member is
  sufficient to create a dive.
- **No `Origin`/`Referer` check observed** (normal form POST, same-origin).
- On success the server returns `200` and the SPA lands on `/mydivelog`
  (the overview). No JSON body; confirm success by re-reading the logbook.
- Related helper endpoints seen in the flow:
  - `POST /code/process/ajax_divelog_validate_dive_number.php` — dup-number check
  - `GET  /code/process/ds_infowindow_sd.php?a=selectsite&id=<siteId>` — resolves a
    dive-site id → name + `salt`/`fresh` (sets `dive_site_bow`)

## Create vs edit

| | create | edit |
|---|---|---|
| `source` | `mydl_18_add_AddDiveOnline` | `mydl_18_add_EditDiveOnline` |
| `odin_user_log_id` | *(omit)* | existing log id |

## Fields that matter for a Garmin import

`odin_user_log_` + the field name is the same key the MySSI **QR** format uses.

| Form field | Example | Source (Garmin) |
|---|---|---|
| `odin_user_log_user_master_id` | `4195537` | your SSI id (config) |
| `source` | `mydl_18_add_AddDiveOnline` | constant |
| `odin_user_log_dive_type` (radio) | `0` | 0 SCUBA · 2 XR · 4 SCR · 8 CCR · 6 Freediving |
| `date_sel2_dd` / `date_sel2_mm` / `date_sel2_yy` | `06` / `06` / `2026` | dive start (local), zero-padded |
| `odin_user_log_entry_time` | `17:10` | dive start (local), `HH:MM` 24h |
| `odin_user_log_dive_nr` | `10` | dive number (`number` from dive-summary) |
| `odin_user_log_var_divetype_id` | `24` | 23 Education · **24 Fun Dive** · 138 Scientific · 139 Work |
| `odin_user_log_divetime` | `24` | minutes, integer (`totalTime`/`bottomTime`) |
| `odin_user_log_depth_m` / `odin_user_log_depth_ft` | `3.8` / `12.5` | `maxDepth`; send both, consistent |
| `odin_user_log_avg_depth_m` / `_ft` | | `avgDepth` |
| `odin_user_log_watertemp_c` / `_f` | `27` / `81` | FIT min `record.temperature` |
| `odin_user_log_watertemp_max_c` / `_f` | | FIT max |
| `odin_user_log_airtemp_c` / `_f` | | optional |
| `odin_user_log_vis_m` / `_ft` | | optional |
| `odin_user_log_var_watertype_id` | `5` | **4 Fresh · 5 Salt** — from FIT `dive_settings.water_type` |
| `odin_user_log_var_entry_id` | `22` | 21 Shore/Beach · 22 Boat Dive · 35 Other |
| `odin_user_log_dive_sites_id` (hidden) | `1018800` | **REQUIRED** — SSI dive-site DB id. With this empty, `mydivelog_18.php` returns the success redirect but **silently creates nothing**. Not derivable from Garmin; store your home site's id in config. |
| `dive_site_bow` (hidden) | `` | optional — real dives have it empty; `salt`/`fresh` also accepted |
| `odin_user_log_ean` (checkbox) / `odin_user_log_ean_percent` | on / `32` | FIT gas: 21% O2 → air, leave off |
| `odin_user_log_buddy_ids[]` | | SSI buddy ids (config, optional) |
| `odin_user_log_leader_nr` | | dive-leader DivePro # (config, optional) |
| `log_linked_facility_id` | | training-center id (config, optional) |
| `odin_user_log_var_specialdive_id[]` | `25` | specialty tags (optional; 25 Boat, 43 Nitrox, 28 Deep, …) |
| `odin_user_log_comment` | `Imported from Garmin Descent Mk2` | free text |
| `submit` | `Submit` | required (name=`submit`, value=`Submit`) |

### Enum value tables

```
var_water_body_id : 13 Ocean · 16 Lake · 15 Quarry · 18 Artificial Lake · 54 Open Water ·
                    14 River · 123 Blue Hole · 124 Cave/Cavern · 125 Cavern/Cenote ·
                    52 Pool/Indoor · 53 Confined Water · 17 Indoor · 84 Dry/Land · 140 Spring
var_entry_id      : 21 Shore/Beach · 22 Boat Dive · 35 Other
var_watertype_id  : 4 Fresh Water · 5 Salt Water
var_current_id    : 6 None · 7 Light · 8 Strong · 9 Ripping
var_surface_id    : 10 Calm · 11 Moving · 12 Stormy
var_weather_id    : 1 Cloudless · 2 Cloudy · 3 Rainy · 121 Snow
var_tanktype_id   : 20 Aluminum · 19 Steel
gearconfiguration_id : 66 Single (back) · 67 Twinset (back) · 68 Sidemount Twinset · 141 Sidemount Single
```

## Full field list

The form submits **82 fields**; most can be empty strings but should be present.
See [ssi_add_dive_payload.json](ssi_add_dive_payload.json) for the complete
template captured from a real dive (values blanked except the ones we set).

## Dive-site lookup by coordinates (public locator API)

```
1. GET https://www.divessi.com/en/locator/divesites
   -> Set-Cookie: PHPSESSID=...   and   <script> var SSI_APIKEY = '<48 chars>'

2. POST https://www.divessi.com/api/locationServices.php
   Cookie: PHPSESSID=<from step 1>        (required)
   x-ssi-auth: <SSI_APIKEY from step 1>   (required - either alone -> 401 {})
   Content-Type: multipart/form-data, one field `request` =
     {"type":"BOUNDS_CHANGED","filter":{"targets":["DiveSites"],
      "geoBounds":{"south":..,"west":..,"north":..,"east":..},
      "viewportCenter":{"lat":..,"lng":..}}}
```

Reply: `{"stats":{"total":N},"result":{"elements":[{"ident":"divesite","data":
{"properties":{"id":"1965","name":"White Star Quarry","lat":"41.3716",
"lng":"-83.3155","distanceToCenter":"2.03", ...}}}]}}`. No login needed.
`SSI_APIKEY` is session-scoped (rotates); scrape it fresh each time.
`locationSearch.php` (geocode a "lat,lng" string -> a bbox) is not needed.

## Finding a dive-site id (manual)

The site-search widget on `/mydivelog/add` resolves names → ids, but the easy way
is to read `value="..." name="odin_user_log_dive_sites_id"` off any existing
dive's `/mydivelog/edit/<n>_<actid>_<uid>` page. Known ids for this account:
`1018800` = North Olmsted Rec Center, `1965` = White Star Quarry.

## Confirmed behaviour

- **`odin_user_log_dive_sites_id` is mandatory** (see field table). Verified: a
  POST from a fully-authenticated same-origin session with everything *except* a
  site → 200 + redirect stub, logbook count unchanged. Add a real site id → dive
  created.
- **No CSRF / nonce.** Static form, no token field, no `X-Ssi-Auth` needed for
  the portal login or the logbook POST.
- **Auth:** `www.divessi.com/bridge/code/process/signin` (see Login) sets a
  `.divessi.com` `PHPSESSID` that also works on `my.`. `curl_cffi`'s jar carries
  it cross-host once the login itself succeeds.
- Success detection: the 376-byte redirect stub is returned even when the POST is
  dropped, so the client counts `/mydivelog/show/` links before/after.

## Open questions

1. `PHPSESSID` lifetime when logging in fresh each run (probably a non-issue
   since we re-auth every run).
2. Behaviour for a dive at a site not in SSI's DB (no id to send).
