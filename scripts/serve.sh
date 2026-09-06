#!/usr/bin/env bash
# Serve the built site locally. See SPEC.md section 14.4.
#   Desktop OPDS client: set site.base_url to http://localhost:8000/
#   The reader device:   set it to http://<this-machine-LAN-IP>:8000/
set -euo pipefail
exec python3 -m http.server 8000 --directory "${1:-public}"
