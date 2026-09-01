#!/usr/bin/env python
"""Run ONCE, locally, to mint a Garmin token blob for the GitHub Action.

    uv run --with garminconnect python bootstrap_token.py

Prompts for your Garmin email/password (and MFA code if enabled), then prints a
JSON blob. Put it in the repo's Actions secrets as GARMIN_TOKENS.

Nothing is written to disk. Your password is never stored. The blob contains a
long-lived DI refresh token (~1 year) - treat it like a password. Re-run this if
the Action starts failing auth.

Why local-only: Garmin's SSO endpoint is Cloudflare-gated and hostile to
datacenter IPs, so the interactive login must happen from your machine. The
Action only does token *refresh*, which is not gated the same way.
"""

import getpass
import sys

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit("pip/uv add 'garminconnect' first:  uv run --with garminconnect python bootstrap_token.py")


def main() -> int:
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")

    g = Garmin(email, password, prompt_mfa=lambda: input("MFA code: ").strip())
    g.login()  # no tokenstore path -> nothing touches disk

    blob = g.client.dumps()
    print("\n" + "=" * 70)
    print("GARMIN_TOKENS secret value (copy the single line below):")
    print("=" * 70)
    print(blob)
    print("=" * 70)
    print("Add it:  gh secret set GARMIN_TOKENS  (paste, then Ctrl-Z/Ctrl-D)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
