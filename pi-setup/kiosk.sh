#!/bin/bash

set -euo pipefail

FRONTEND_URL="https://campus-copilot.com"

unclutter -idle 0.1 -root &

chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-translate \
  --disable-features=TranslateUI \
  --autoplay-policy=no-user-gesture-required \
  --disable-session-crashed-bubble \
  "$FRONTEND_URL"
