"""Entry point: fetch the latest Garmin dive, push it into the MySSI logbook,
and write latest.json (kept for debugging / the optional QR path).

    uv run dive-qr-refresh                   # normal run
    uv run dive-qr-refresh --from-fit f.fit  # offline: build from a local .fit, no Garmin auth
    uv run dive-qr-refresh --probe           # dump raw dive-summary JSON, do nothing else
    uv run dive-qr-refresh --dry-run         # print what would happen, no write, no push
    uv run dive-qr-refresh --no-push         # write latest.json only, skip the logbook
    uv run dive-qr-refresh --force-push      # push even if this dive was already pushed
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .config import Config
from .ssi import Identity, build_ssi


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dive_key(dive) -> str:
    """Stable id for dedup: Garmin activity id, else date+number."""
    if dive.activity_id:
        return str(dive.activity_id)
    return f"{dive.start_local:%Y%m%d}_{dive.dive_number or 0}"


def _payload(dive, identity: Identity, source: str, pushed: dict | None) -> dict:
    p = {
        "ssi": build_ssi(dive, identity),
        "dive": dive.to_public_dict(),
        "diveKey": dive_key(dive),
        "source": source,
        "generatedAt": _now_iso(),
        "schema": 2,
    }
    if pushed:
        p["pushed"] = pushed
    return p


def _read_existing(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _write(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def persist_token(src, token_out: str | None) -> bool:
    if not token_out or not getattr(src, "token_changed", False):
        return False
    Path(token_out).write_text(src.token_blob, encoding="utf-8")
    print(f"token refreshed -> wrote {token_out} (workflow will update GARMIN_TOKENS)")
    return True


def push_to_logbook(dive, cfg: Config) -> dict:
    """Log in (if needed) and POST the dive into the MySSI web logbook.

    Never raises: a push failure returns a result dict so `main` can still write
    latest.json / save a refreshed Garmin token before exiting non-zero.
    """
    from .ssi_push import dive_to_form

    body = dive_to_form(
        dive,
        cfg.identity,
        dive_site_id=cfg.ssi_dive_site_id,
        divetype_id=cfg.ssi_divetype_id,
        comment=cfg.ssi_comment,
    )
    try:
        return cfg.make_ssi_client().create_dive(body)
    except Exception as e:  # noqa: BLE001 - report, don't crash the run
        return {"ok": False, "status": None, "bytes": 0, "detail": f"{type(e).__name__}: {e}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dive-qr-refresh")
    ap.add_argument("--from-fit", metavar="PATH", help="build from a local .fit, skip Garmin")
    ap.add_argument("--probe", action="store_true", help="print raw dive-summary JSON and exit")
    ap.add_argument("--dry-run", action="store_true", help="print plan, no write, no push")
    ap.add_argument("--no-fit", action="store_true", help="skip FIT download (no water temp)")
    ap.add_argument("--no-push", action="store_true", help="write latest.json only, skip logbook")
    ap.add_argument("--force-push", action="store_true", help="push even if already pushed")
    args = ap.parse_args(argv)

    cfg = Config.from_env()

    if args.from_fit:
        from .fit import parse_fit_file

        dive = parse_fit_file(args.from_fit)
        source = "fit"
    else:
        src = cfg.make_source()
        if args.probe:
            summaries = src.list_dive_summaries()
            json.dump(summaries[0] if summaries else {}, sys.stdout, indent=2, default=str)
            print()
            persist_token(src, cfg.token_out)
            return 0
        from .garmin import build_latest_dive

        dive = build_latest_dive(src, use_fit=cfg.use_fit and not args.no_fit)
        source = cfg.source_name
        persist_token(src, cfg.token_out)

    if not cfg.identity.user_master_id:
        print("WARNING: SSI_USER_ID unset - the dive may not attach to your MySSI profile.")

    key = dive_key(dive)
    prev = _read_existing(cfg.output_path)
    already_pushed = (prev.get("pushed") or {}).get("key") == key

    want_push = (
        cfg.push_enabled
        and cfg.ssi_auth_configured
        and not args.no_push
        and not args.dry_run
        and (not already_pushed or args.force_push)
    )

    if args.dry_run:
        from .ssi_push import dive_to_form

        print(f"dive {key}: {build_ssi(dive, cfg.identity)}")
        print(f"already pushed: {already_pushed}")
        if cfg.ssi_auth_configured:
            print("would POST to MySSI logbook:")
            json.dump(dive_to_form(dive, cfg.identity, dive_site_id=cfg.ssi_dive_site_id,
                                   divetype_id=cfg.ssi_divetype_id, comment=cfg.ssi_comment),
                      sys.stdout, indent=1)
            print()
        return 0

    pushed = prev.get("pushed")
    if want_push:
        res = push_to_logbook(dive, cfg)
        print(f"MySSI logbook: {res}")
        if not res["ok"]:
            _write(cfg.output_path, _payload(dive, cfg.identity, source, pushed))
            return 1
        pushed = {"key": key, "activityId": dive.activity_id, "at": _now_iso()}
    elif already_pushed and not args.no_push:
        print(f"dive {key} already pushed at {pushed.get('at') if pushed else '?'} - skipping")
    elif not cfg.ssi_auth_configured and not args.no_push:
        print("no SSI auth (SSI_EMAIL/SSI_PASSWORD or SSI_COOKIE) - skipping logbook push")

    _write(cfg.output_path, _payload(dive, cfg.identity, source, pushed))
    print(f"wrote {cfg.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
