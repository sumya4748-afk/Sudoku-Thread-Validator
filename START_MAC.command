#!/bin/bash
cd "$(dirname "$0")"
python3 launch.py
status=$?
if [ "$status" -ne 0 ]; then
  echo "Launch failed. See README.md."
  read -r -p "Press Enter to close..." _
fi
exit "$status"
