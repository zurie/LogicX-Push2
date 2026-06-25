#!/usr/bin/env bash
# apply_icon.sh — (re)attach Push2.app's custom Finder icon.
#
# WHY THIS EXISTS
# Push2.app is an AppleScript ("Script Editor") applet. For these bundles macOS
# IGNORES CFBundleIconFile/applet.icns in Finder and substitutes the generic
# AppleScript scroll icon. The ONLY thing that overrides that is a true
# "custom icon" override: an `Icon\r` resource fork plus the kHasCustomIcon
# FinderInfo bit on the bundle. git cannot store a resource fork or FinderInfo
# bit, so a fresh `git clone` always loses the icon — this script rebuilds it
# from the tracked Contents/Resources/applet.icns.
#
# Usage: tools/apply_icon.sh [path/to/Push2.app]   (defaults to ./Push2.app)
set -euo pipefail

BUNDLE="${1:-Push2.app}"
BUNDLE="${BUNDLE%/}"
ICNS="$BUNDLE/Contents/Resources/applet.icns"

[ -d "$BUNDLE" ] || { echo "✗ bundle not found: $BUNDLE" >&2; exit 1; }
[ -f "$ICNS" ]   || { echo "✗ icns not found: $ICNS" >&2; exit 1; }

applied=0

# Preferred: NSWorkspace.setIcon (no Xcode toolchain assumptions beyond /usr/bin/swift).
if command -v swift >/dev/null 2>&1; then
    if swift - "$ICNS" "$BUNDLE" <<'SWIFT'
import Cocoa
let a = CommandLine.arguments
guard let img = NSImage(contentsOfFile: a[1]) else { FileHandle.standardError.write("bad icns\n".data(using: .utf8)!); exit(1) }
exit(NSWorkspace.shared.setIcon(img, forFile: a[2], options: []) ? 0 : 1)
SWIFT
    then
        applied=1
    fi
fi

# Fallback: classic Rez/SetFile recipe (Xcode Command Line Tools).
if [ "$applied" -eq 0 ] && command -v Rez >/dev/null 2>&1 && command -v SetFile >/dev/null 2>&1; then
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    cp "$ICNS" "$tmp/icon.icns"
    sips -i "$tmp/icon.icns" >/dev/null            # add 'icns' resource to the icns' own fork
    DeRez -only icns "$tmp/icon.icns" > "$tmp/icon.rsrc"
    iconfile="$BUNDLE/Icon"$'\r'
    rm -f "$iconfile"
    Rez -append "$tmp/icon.rsrc" -o "$iconfile"
    SetFile -a C "$BUNDLE"                          # kHasCustomIcon on the bundle
    SetFile -a V "$iconfile"                        # hide the Icon^M file
    applied=1
fi

if [ "$applied" -eq 0 ]; then
    echo "✗ no icon-setting tool available (need /usr/bin/swift or Rez+SetFile)" >&2
    exit 1
fi

echo "✓ custom icon applied to $BUNDLE"
