#!/bin/sh
# Install / update garmin-ssi (FIT -> MySSI) inside a-Shell on iOS.
#
#   GH_PAT=github_pat_xxx sh ashell-install.sh
#
# GH_PAT: a GitHub fine-grained PAT for this private repo, Contents: Read-only.
# Re-run any time to update (it re-fetches the code; keeps your .ssienv).
#
# Env overrides: REPO (default jjeff07/garmin), BRANCH (default main),
#                DEST (default ~/Documents/garmin_ssi).

REPO="${REPO:-jjeff07/garmin}"
BRANCH="${BRANCH:-main}"
DEST="${DEST:-$HOME/Documents/garmin_ssi}"
ENVF="$HOME/Documents/.ssienv"

if [ -z "$GH_PAT" ]; then
  echo "set GH_PAT to a fine-grained PAT (Contents: read on $REPO)" >&2
  exit 1
fi

echo "== pip install fitparse =="
pip install fitparse || { echo "pip install failed" >&2; exit 1; }

echo "== fetch garmin_ssi/ from $REPO@$BRANCH -> $DEST =="
mkdir -p "$DEST"
for f in __init__ _http config fit fit_push model ssi ssi_push ssi_sites; do
  url="https://raw.githubusercontent.com/$REPO/$BRANCH/src/garmin_ssi/$f.py"
  if curl -sfL -H "Authorization: Bearer $GH_PAT" -o "$DEST/$f.py" "$url"; then
    echo "  $f.py"
  else
    echo "  FAILED $f.py ($url)" >&2
    exit 1
  fi
done

if [ ! -f "$ENVF" ]; then
  cat > "$ENVF" <<'EOF'
SSI_EMAIL=
SSI_PASSWORD=
SSI_USER_ID=
SSI_DIVE_SITE_ID=1018800
# SSI_DIVETYPE_ID=24
# SSI_COMMENT=Imported from Garmin Descent
EOF
  chmod 600 "$ENVF" 2>/dev/null
  echo "== created $ENVF - fill in SSI_EMAIL / SSI_PASSWORD / SSI_USER_ID =="
fi

echo
echo "done. test:"
echo "  cd ~/Documents && python -m garmin_ssi.fit_push --help"
echo "  cd ~/Documents && python -m garmin_ssi.fit_push some.fit --env-file .ssienv --dry-run"
