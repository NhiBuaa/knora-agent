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

cleanup() {
    kill -TERM "$KEYCLOAK_PID" 2>/dev/null || true
    wait "$KEYCLOAK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

until /opt/keycloak/bin/kcadm.sh config credentials \
    --server "http://127.0.0.1:$port" \
    --realm master \
    --user "$admin_user" \
    --password "$admin_password" >/dev/null 2>&1; do
    if ! kill -0 "$KEYCLOAK_PID" 2>/dev/null; then
        wait "$KEYCLOAK_PID" || exit $?
    fi
    sleep 2
done

/opt/keycloak/bin/kcadm.sh update realms/knora-dev \
    -s 'eventsListeners=["jboss-logging","knora-default-capabilities"]' \
    >/dev/null
echo "[Knora Keycloak] Public-demo realm capabilities listener reconciled."

wait "$KEYCLOAK_PID"
