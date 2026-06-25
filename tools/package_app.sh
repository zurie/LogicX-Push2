#!/usr/bin/env bash
# package_app.sh — build Push2.app + Push2.app.zip for a release.
#
# Steps:
#   1. Compile launcher/Push2.applescript -> Push2.app/Contents/Resources/Scripts/main.scpt
#   2. Sync CFBundleShortVersionString to the launcher's `appVersion` property
#   3. Re-apply the custom Finder icon (tools/apply_icon.sh)
#   4. Re-adhoc-sign the bundle
#   5. Zip with `ditto --sequesterRsrc --keepParent` so the icon resource fork
#      and FinderInfo bit survive (plain `zip` strips them; the launcher's
#      auto-update extracts with `ditto -x -k`, which restores them).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

BUNDLE="Push2.app"
ZIP="Push2.app.zip"
SRC="launcher/Push2.applescript"
SCPT="$BUNDLE/Contents/Resources/Scripts/main.scpt"
PLIST="$BUNDLE/Contents/Info.plist"

[ -f "$SRC" ] || { echo "✗ missing $SRC" >&2; exit 1; }

# Single source of truth for the launcher version: the .applescript property.
VERSION="$(sed -n 's/^property appVersion : "\(.*\)"/\1/p' "$SRC" | head -1)"
[ -n "$VERSION" ] || { echo "✗ could not parse appVersion from $SRC" >&2; exit 1; }
echo "► Launcher version: $VERSION"

echo "► Compiling launcher -> main.scpt"
osacompile -o "$SCPT" "$SRC"

echo "► Syncing Info.plist version"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST"

# Ship the icon applier inside the bundle so the launcher can re-run it after an
# auto-update (zips can't carry the kHasCustomIcon FinderInfo bit, so it must be
# re-applied on the target machine). Copied before signing so it's sealed.
echo "► Bundling apply_icon.sh"
cp tools/apply_icon.sh "$BUNDLE/Contents/Resources/apply_icon.sh"
chmod +x "$BUNDLE/Contents/Resources/apply_icon.sh"

# Sign BEFORE applying the icon: the custom-icon override lives at the bundle
# root (Icon^R + FinderInfo), outside the sealed Contents/. codesign rejects a
# resource fork that's already present ("detritus not allowed"), so the order
# matters — sign clean, then attach the icon (signature stays valid-on-disk).
echo "► Re-adhoc-signing"
xattr -rc "$BUNDLE" 2>/dev/null || true
rm -f "$BUNDLE/Icon"$'\r'
codesign --force --deep --sign - "$BUNDLE"

echo "► Applying custom icon"
tools/apply_icon.sh "$BUNDLE"

echo "► Verifying signature"
codesign --verify --verbose=1 "$BUNDLE"

echo "► Zipping with ditto (preserving resource fork)"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$BUNDLE" "$ZIP"

echo ""
echo "✓ Built $BUNDLE and $ZIP (v$VERSION)"
ls -lh "$ZIP"
