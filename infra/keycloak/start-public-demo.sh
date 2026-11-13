#!/usr/bin/env bash
set -Eeuo pipefail

port="${PORT:-10000}"
admin_user="${KC_BOOTSTRAP_ADMIN_USERNAME:-}"
admin_password="${KC_BOOTSTRAP_ADMIN_PASSWORD:-}"
if [[ -z "$admin_user" || -z "$admin_password" ]]; then
    echo "[Knora Keycloak] Admin bootstrap credentials are required for realm reconciliation." >&2
    exit 1
fi

/opt/keycloak/bin/kc.sh start --optimized --import-realm \
    --http-enabled=true --http-host=0.0.0.0 --http-port="$port" &
KEYCLOAK_PID=$!
KCADM_CONFIG="${KCADM_CONFIG:-/tmp/knora-kcadm.config}"
export KCADM_CONFIG
export KC_CLI_PASSWORD="$admin_password"

cleanup() {
    if [[ -n "${KEYCLOAK_PID:-}" ]]; then
        kill -TERM "$KEYCLOAK_PID" 2>/dev/null || true
        wait "$KEYCLOAK_PID" 2>/dev/null || true
    fi
    rm -f -- "$KCADM_CONFIG"
    unset KC_CLI_PASSWORD
}
trap cleanup EXIT
trap 'exit 0' INT TERM

until /opt/keycloak/bin/kcadm.sh config credentials \
    --config "$KCADM_CONFIG" \
    --server "http://127.0.0.1:$port" \
    --realm master \
    --user "$admin_user" >/dev/null 2>&1; do
    if ! kill -0 "$KEYCLOAK_PID" 2>/dev/null; then
        wait "$KEYCLOAK_PID" || exit $?
    fi
    sleep 2
done

/opt/keycloak/bin/kcadm.sh update \
    --config "$KCADM_CONFIG" \
    realms/knora-dev \
    -s 'eventsListeners=["jboss-logging","knora-default-capabilities"]' \
    >/dev/null
echo "[Knora Keycloak] Public-demo realm capabilities listener reconciled."

wait "$KEYCLOAK_PID"
