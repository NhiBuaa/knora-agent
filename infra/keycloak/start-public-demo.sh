#!/usr/bin/env bash
set -Eeuo pipefail

exec /opt/keycloak/bin/kc.sh start --optimized --import-realm \
    --http-enabled=true --http-host=0.0.0.0 --http-port="${PORT:-10000}"
