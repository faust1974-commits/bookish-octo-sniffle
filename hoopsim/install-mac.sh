#!/bin/bash
# Put hoopsim on a Mac desktop as a real double-clickable app.
#
#   curl -fsSL https://raw.githubusercontent.com/faust1974-commits/bookish-octo-sniffle/claude/upbeat-goldberg-m8elj1/hoopsim/install-mac.sh | bash
#
# Downloads one self-contained HTML file, wraps it in a .app bundle with an
# icon, and puts that on the Desktop. No Python, no Homebrew, no admin
# password, nothing to configure. Run it again any time to update.

set -euo pipefail

BRANCH="claude/upbeat-goldberg-m8elj1"
RAW="https://raw.githubusercontent.com/faust1974-commits/bookish-octo-sniffle/${BRANCH}/hoopsim/dist/hoopsim.html"
APP_NAME="Hoopsim"
SUPPORT="${HOME}/Library/Application Support/Hoopsim"
DESKTOP="${HOME}/Desktop"
APP="${DESKTOP}/${APP_NAME}.app"

say() { printf '%s\n' "$*"; }
die() { printf '\n%s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "This installer is for macOS. On anything else, just open hoopsim.html in a browser."

say ""
say "Installing ${APP_NAME} …"

# 1. Fetch the app itself -- one file, everything inlined.
mkdir -p "${SUPPORT}"
TMP="$(mktemp "${TMPDIR:-/tmp}/hoopsim.XXXXXX")"
trap 'rm -f "${TMP}"' EXIT
say "  downloading (about 800 KB) …"
curl -fsSL --retry 3 --retry-delay 2 "${RAW}" -o "${TMP}" \
  || die "Could not download it. Check the internet connection and try again."

# A truncated download would produce an app that opens to a blank page, so
# check for the closing tag rather than trusting the transfer.
grep -q "</html>" "${TMP}" || die "The download came through incomplete. Run this again."
mv "${TMP}" "${SUPPORT}/hoopsim.html"
trap - EXIT

# 2. Build the .app bundle. A macOS app is a folder with a launcher inside.
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"

cat > "${APP}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>local.hoopsim.app</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>${APP_NAME}</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "${APP}/Contents/MacOS/${APP_NAME}" <<'LAUNCH'
#!/bin/bash
# Open the bundled page in whatever the default browser is.
exec /usr/bin/open "${HOME}/Library/Application Support/Hoopsim/hoopsim.html"
LAUNCH
chmod +x "${APP}/Contents/MacOS/${APP_NAME}"

# 3. An icon, so it does not land as a blank sheet of paper. Drawn as a PDF
#    (which sips reads natively) rather than shipping a binary blob.
ICONDIR="$(mktemp -d "${TMPDIR:-/tmp}/hoopicon.XXXXXX")"
ICONSET="${ICONDIR}/AppIcon.iconset"
mkdir -p "${ICONSET}"
PDF="${ICONDIR}/icon.pdf"
cat > "${PDF}" <<'PDFEOF'
%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 512 512]/Contents 4 0 R>>endobj
4 0 obj<</Length momo>>
stream
0.85 0.37 0.11 rg
256 256 m
256 256 232 0 360 arc
f
0 0 0 RG
14 w
1 J
24 256 m 488 256 l S
256 24 m 256 488 l S
256 24 m 120 140 120 372 256 488 c S
256 24 m 392 140 392 372 256 488 c S
endstream
endobj
trailer<</Root 1 0 R>>
PDFEOF
# Length must be right or Preview/sips rejects the stream.
BODY_LEN=$(awk '/^stream$/{f=1;next}/^endstream$/{f=0}f{n+=length($0)+1}END{print n+0}' "${PDF}")
/usr/bin/sed -i '' "s/momo/${BODY_LEN}/" "${PDF}" 2>/dev/null || sed -i "s/momo/${BODY_LEN}/" "${PDF}"

icon_ok=1
for sz in 16 32 64 128 256 512; do
  sips -s format png -z "${sz}" "${sz}" "${PDF}" \
       --out "${ICONSET}/icon_${sz}x${sz}.png" >/dev/null 2>&1 || icon_ok=0
done
if [ "${icon_ok}" = "1" ]; then
  cp "${ICONSET}/icon_32x32.png"   "${ICONSET}/icon_16x16@2x.png"   2>/dev/null || true
  cp "${ICONSET}/icon_64x64.png"   "${ICONSET}/icon_32x32@2x.png"   2>/dev/null || true
  cp "${ICONSET}/icon_256x256.png" "${ICONSET}/icon_128x128@2x.png" 2>/dev/null || true
  cp "${ICONSET}/icon_512x512.png" "${ICONSET}/icon_256x256@2x.png" 2>/dev/null || true
  iconutil -c icns "${ICONSET}" -o "${APP}/Contents/Resources/AppIcon.icns" >/dev/null 2>&1 || true
fi
rm -rf "${ICONDIR}"

# Nudge Finder to notice the new bundle without restarting it -- killing
# Finder would close whatever windows are open, which is a rude thing to do
# to someone who just wanted a basketball app.
touch "${APP}" "${APP}/Contents/Info.plist" 2>/dev/null || true

say ""
say "Done. '${APP_NAME}' is on your Desktop — double-click it."
say ""
say "  the app      ${APP}"
say "  its data     ${SUPPORT}/hoopsim.html"
say ""
say "Run this installer again whenever you want the latest version."
say ""

# 4. Open it now so there is something to look at immediately.
/usr/bin/open "${APP}" >/dev/null 2>&1 || true
