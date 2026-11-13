#!/bin/sh
# Legt für jeden Versions-Tag (vX.Y.Z) ein GitHub-Release an, falls es noch keins gibt.
#
# HACS zeigt Versionsnummern nur für GitHub-Releases an, ein Tag allein reicht nicht.
# Ohne Release sieht man in HACS nur Commit-Hashes. Bestehende Releases bleiben unverändert,
# darum darf das Skript bei jedem Lauf auf main und bei jedem Tag laufen.
# Titel und Text des Releases kommen aus der Nachricht des annotierten Tags.
#
# Benötigt: curl, jq, GITHUB_TOKEN (Contents: Read and write) und die Tags im Checkout.
set -eu

REPO="Sedrah87/HASS-CoffeeNerd"
API="https://api.github.com/repos/$REPO/releases"

for TAG in $(git tag -l 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$'); do
  STATUS=$(curl -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" \
    "$API/tags/$TAG")
  if [ "$STATUS" = "200" ]; then
    continue
  fi
  if [ "$STATUS" != "404" ]; then
    echo "❌ Release $TAG konnte nicht geprüft werden (HTTP $STATUS)"
    exit 1
  fi
  TITEL=$(git tag -l --format='%(contents:subject)' "$TAG")
  TEXT=$(git tag -l --format='%(contents:body)' "$TAG")
  jq -n --arg tag "$TAG" --arg name "${TITEL:-$TAG}" --arg body "$TEXT" \
    '{tag_name: $tag, name: $name, body: $body, draft: false, prerelease: false}' |
    curl -sS --fail-with-body -o /dev/null \
      -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" \
      -X POST "$API" -d @-
  echo "✅ Release $TAG angelegt"
done
