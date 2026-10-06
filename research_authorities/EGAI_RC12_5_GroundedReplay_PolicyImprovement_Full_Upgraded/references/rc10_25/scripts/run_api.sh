#!/usr/bin/env bash
set -euo pipefail
uvicorn kvcontinual.api:app --host 127.0.0.1 --port 8088
