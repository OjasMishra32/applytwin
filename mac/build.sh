#!/usr/bin/env bash
# Builds ApplyTwin.app and ApplyTwin.dmg (the Mac download) into mac/build.
# Signs with the Developer ID in the keychain and notarizes with the notarytool profile "applytwin" if it exists
# (one time: xcrun notarytool store-credentials applytwin --apple-id <id> --team-id X452LG6K72).
set -euo pipefail
cd "$(dirname "$0")"
OUT=build; APP="$OUT/ApplyTwin.app"; VER="$(cat ../VERSION)"
IDENT="${APPLYTWIN_SIGN:-$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1)}"
rm -rf "$OUT" && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

for arch in arm64 x86_64; do
  swiftc -O -target "$arch-apple-macos12" -o "$OUT/ApplyTwin-$arch" ApplyTwin.swift
done
lipo -create -output "$APP/Contents/MacOS/ApplyTwin" "$OUT"/ApplyTwin-arm64 "$OUT"/ApplyTwin-x86_64 && rm "$OUT"/ApplyTwin-*
sed "s/__VERSION__/$VER/g" Info.plist > "$APP/Contents/Info.plist"
cp setup.sh setup.html "$APP/Contents/Resources/"
cp ../scripts/seo/icon-512.png "$APP/Contents/Resources/icon.png"

swift icon.swift ../scripts/seo/icon-512.png "$OUT/icon-1024.png"
IS="$OUT/AppIcon.iconset"; mkdir -p "$IS"
for s in 16 32 128 256 512; do
  sips -z $s $s "$OUT/icon-1024.png" --out "$IS/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$OUT/icon-1024.png" --out "$IS/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$IS" -o "$APP/Contents/Resources/AppIcon.icns" && rm -rf "$IS"

if [ -n "$IDENT" ]; then
  codesign --force --options runtime --timestamp -s "$IDENT" "$APP"
else
  echo "! no Developer ID in the keychain: signing for this Mac only"; codesign --force -s - "$APP"
fi
codesign --verify --strict "$APP"

# the DMG: the app and an Applications shortcut to drag it onto
STAGE="$OUT/dmg"; mkdir -p "$STAGE" && cp -R "$APP" "$STAGE/" && ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname ApplyTwin -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$OUT/ApplyTwin.dmg" && rm -rf "$STAGE"
[ -n "$IDENT" ] && codesign --force --timestamp -s "$IDENT" "$OUT/ApplyTwin.dmg"

if [ -n "$IDENT" ] && xcrun notarytool history --keychain-profile applytwin >/dev/null 2>&1; then
  xcrun notarytool submit "$OUT/ApplyTwin.dmg" --keychain-profile applytwin --wait
  xcrun stapler staple "$OUT/ApplyTwin.dmg"
  echo "notarized"
else
  echo "! not notarized (no 'applytwin' notarytool profile): other Macs will warn before opening it"
fi
echo "built $OUT/ApplyTwin.dmg ($(du -h "$OUT/ApplyTwin.dmg" | cut -f1)), version $VER"
