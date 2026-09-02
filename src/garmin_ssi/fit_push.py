"""Log a dive into the MySSI logbook straight from a .fit file - no Garmin API.

Intended trigger: an Apple Shortcut exports the dive .fit from the Garmin Connect
app and commits it to `incoming/` in the repo; the `fit-to-ssi` workflow runs
this over each new file.

    uv run garmin-ssi-fit incoming/dive-1234.fit
    uv run garmin-ssi-fit some.fit --dry-run      # parse + map, no login, no POST
    uv run garmin-ssi-fit some.fit --force        # ignore the pushed-fits ledger

A sha256 of each .fit is recorded in `state/pushed_fits.json` so a re-run (or a
re-pushed commit) does not create a duplicate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from .config import Config
from .fit import parse_fit_file
from .ssi_push import dive_to_form

LEDGER_PATH = "state/pushed_fits.json"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fit_sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def load_ledger(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_ledger(path: str, ledger: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_coords(fit_path: str | Path) -> tuple[float, float] | None:
    """Optional `<same-stem>.json` sidecar: {"lat": .., "lng": ..} from the phone."""
    side = Path(fit_path).with_suffix(".json")
    try:
        d = json.loads(side.read_text(encoding="utf-8"))
        return float(d["lat"]), float(d["lng"])
    except Exception:
        return None


def resolve_site_id(dive, cfg: Config, fit_path: str | Path) -> str | None:
    """SSI dive-site id from the dive's coords (FIT fix) / the `<stem>.json`
    sidecar / SSI_DIVE_SITE_ID, via the public locator."""
    from .ssi_sites import site_for_dive

    site_id, _ = site_for_dive(
        dive,
        fallback_id=cfg.ssi_dive_site_id,
        api_key=cfg.ssi_api_key,
        sidecar_coords=read_coords(fit_path),
    )
    return site_id


def load_env_file(path: str) -> None:
    """`KEY=VALUE` / `export KEY="VALUE"` lines -> os.environ (comments/blanks ok)."""
    import os

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip("'\"")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="garmin-ssi-fit")
    ap.add_argument("fit", nargs="+", help="one or more .fit files")
    ap.add_argument("--env-file", help="load SSI_* vars from a KEY=VALUE file")
    ap.add_argument("--lat", type=float, help="fallback latitude, used only if the FIT has no GPS fix")
    ap.add_argument("--lng", type=float, help="fallback longitude (with --lat)")
    ap.add_argument("--force-coords", action="store_true",
                    help="use --lat/--lng even when the FIT has its own fix")
    ap.add_argument("--ledger", default=LEDGER_PATH)
    ap.add_argument("--dry-run", action="store_true", help="parse + map only")
    ap.add_argument("--force", action="store_true", help="ignore the pushed-fits ledger")
    args = ap.parse_args(argv)

    if args.env_file:
        load_env_file(args.env_file)

    cfg = Config.from_env()
    ledger = load_ledger(args.ledger)
    client = None
    rc = 0

    for f in args.fit:
        sha = fit_sha(f)
        if sha in ledger and not args.force:
            print(f"{f}: already pushed {ledger[sha].get('at','?')} - skip")
            continue

        dive = parse_fit_file(f)
        if args.lat is not None and args.lng is not None:
            if dive.lat is None or dive.lng is None or args.force_coords:
                dive.lat, dive.lng = args.lat, args.lng
            else:
                print(f"  FIT has GPS {dive.lat:.4f},{dive.lng:.4f} - ignoring --lat/--lng "
                      "(pass --force-coords to override)")
        site_id = resolve_site_id(dive, cfg, f)
        body = dive_to_form(
            dive, cfg.identity,
            dive_site_id=site_id,
            divetype_id=cfg.ssi_divetype_id,
            comment=cfg.ssi_comment,
        )
        print(
            f"{f}: start={dive.start_local.isoformat()} "
            f"divetime={round(dive.divetime_s / 60)}min depth={dive.max_depth_m:.1f}m "
            f"water={dive.water_temp_c} -> site {site_id}"
        )
        if args.dry_run:
            continue

        if not site_id:  # no GPS -> no public site -> no fallback configured
            print("  no dive site (no coords near a known site, and SSI_DIVE_SITE_ID unset) - skipped")
            rc = 1
            continue

        if client is None:  # first real push - require auth now
            if not cfg.ssi_auth_configured:
                print("no SSI auth (SSI_EMAIL/SSI_PASSWORD or SSI_COOKIE)")
                return 2
            client = cfg.make_ssi_client()
        res = client.create_dive(body)
        print(f"  MySSI: {res}")
        if res["ok"]:
            ledger[sha] = {"at": _now_iso(), "file": Path(f).name,
                           "start": dive.start_local.isoformat()}
        else:
            rc = 1

    if not args.dry_run:
        save_ledger(args.ledger, ledger)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
