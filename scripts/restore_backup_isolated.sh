#!/usr/bin/env bash
set -euo pipefail

# Manual operator procedure: only disposable Podman resources on an internal network.
: "${ECHORA_RESTORE_APPROVE:?Set ECHORA_RESTORE_APPROVE=YES after reviewing this procedure}"
test "$ECHORA_RESTORE_APPROVE" = YES
START_EPOCH=$(date +%s)

ROOT=${ECHORA_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}
BACKUP=${1:-/srv/echora/backups/echora-pre-v2-20261119-215505.dump}
POSTGRES_IMAGE=${POSTGRES_IMAGE:-postgres:16.16-alpine3.24}
VALIDATOR_IMAGE=${VALIDATOR_IMAGE:-localhost/echora-backend-check:latest}

case "$BACKUP" in
  /*) ;;
  *) echo 'backup deve usar caminho absoluto' >&2; exit 2 ;;
esac
test -f "$BACKUP"
test "$(basename "$BACKUP")" = echora-pre-v2-20261119-215505.dump

INSTANCE="echora-restore-$(openssl rand -hex 8)"
NETWORK="echora-restore-net-$(openssl rand -hex 8)"
DB="echora_restore_$(openssl rand -hex 8)"
PG_ALIAS="echora-restore-postgres"
VALIDATOR="echora-restore-validator-${INSTANCE##*-}"
REPORT="${TMPDIR:-/tmp}/${INSTANCE}.report"

created_network=0
created_instance=0
created_validator=0
cleanup() {
  set +e
  if [ "$created_validator" = 1 ]; then
    purpose=$(podman inspect "$VALIDATOR" --format '{{index .Config.Labels "io.echora.restore-purpose"}}' 2>/dev/null || true)
    label=$(podman inspect "$VALIDATOR" --format '{{index .Config.Labels "io.echora.restore-instance"}}' 2>/dev/null || true)
    [ "$purpose" = disposable ] && [ "$label" = "$INSTANCE" ] && podman rm -f "$VALIDATOR" >/dev/null 2>&1 || true
  fi
  if [ "$created_instance" = 1 ]; then
    purpose=$(podman inspect "$INSTANCE" --format '{{index .Config.Labels "io.echora.restore-purpose"}}' 2>/dev/null || true)
    label=$(podman inspect "$INSTANCE" --format '{{index .Config.Labels "io.echora.restore-instance"}}' 2>/dev/null || true)
    [ "$purpose" = disposable ] && [ "$label" = "$INSTANCE" ] && podman rm -f "$INSTANCE" >/dev/null 2>&1 || true
  fi
  if [ "$created_network" = 1 ]; then
    podman network inspect "$NETWORK" >/dev/null 2>&1 && podman network rm "$NETWORK" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

umask 077
{
  echo "backup=$(basename "$BACKUP")"
  sha256sum "$BACKUP"
  podman image inspect "$POSTGRES_IMAGE" --format 'postgres_image={{.Id}} {{index .RepoDigests 0}}'
  podman run --rm --network none "$POSTGRES_IMAGE" pg_restore --version
  podman run --rm --network none "$POSTGRES_IMAGE" postgres --version
} | tee "$REPORT"

podman image inspect "$VALIDATOR_IMAGE" >/dev/null
podman network create --internal \
  --label io.echora.restore-purpose=disposable \
  --label io.echora.restore-instance="$INSTANCE" \
  "$NETWORK" >/dev/null
created_network=1

podman run -d --rm \
  --name "$INSTANCE" \
  --label io.echora.restore-purpose=disposable \
  --label io.echora.restore-instance="$INSTANCE" \
  --network "$NETWORK" \
  --network-alias "$PG_ALIAS" \
  --tmpfs /var/lib/postgresql/data:rw,size=4g \
  --tmpfs /restore-tmp:rw,size=4g \
  -e POSTGRES_DB="$DB" \
  -e POSTGRES_USER=echora_restore_admin \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  "$POSTGRES_IMAGE" postgres >/dev/null
created_instance=1

for attempt in $(seq 1 60); do
  if podman exec "$INSTANCE" pg_isready -h 127.0.0.1 -U echora_restore_admin -d "$DB" >/dev/null 2>&1; then
    break
  fi
  test "$attempt" -lt 60 || { echo 'PostgreSQL descartável não ficou pronto' >&2; exit 1; }
  sleep 1
done

actual=$(podman exec "$INSTANCE" psql -X -A -t -F '|' -U echora_restore_admin -d "$DB" \
  -c "SELECT current_database(), current_user;" | tr -d '\r')
test "$actual" = "$DB|echora_restore_admin" || {
  echo 'identidade do banco temporário não corresponde ao destino' >&2
  exit 1
}
echo "identity=$actual" | tee -a "$REPORT"

# PostgreSQL 16.16 supports these options; -X is intentionally not passed.
# The custom dump format requires a seekable input file. Copy it only into
# the disposable container's tmpfs; it is removed before container cleanup.
podman cp "$BACKUP" "$INSTANCE:/restore-tmp/backup.dump"
podman exec --user 0 "$INSTANCE" pg_restore \
  --exit-on-error \
  --no-owner \
  --no-acl \
  -h 127.0.0.1 \
  -U echora_restore_admin \
  -d "$DB" \
  /restore-tmp/backup.dump 2>&1 | tee -a "$REPORT"
podman exec --user 0 "$INSTANCE" rm -f /restore-tmp/backup.dump
echo 'pg_restore=OK' | tee -a "$REPORT"

podman exec "$INSTANCE" psql -X -v ON_ERROR_STOP=1 -A -t -F '|' \
  -U echora_restore_admin -d "$DB" <<SQL | tee -a "$REPORT"
SELECT current_database(), current_user, current_setting('server_version');
SELECT to_regclass('public.alembic_version'),
       to_regclass('public.feedbacks'),
       to_regclass('public.maya_analyses'),
       to_regclass('public.maya_questions'),
       to_regclass('public.maya_hmac_control');
SELECT version_num FROM public.alembic_version;
SELECT 'users', count(*) FROM public.users
UNION ALL SELECT 'feedbacks', count(*) FROM public.feedbacks
UNION ALL SELECT 'maya_analyses', count(*) FROM public.maya_analyses
UNION ALL SELECT 'maya_questions', count(*) FROM public.maya_questions;
SELECT
 (SELECT count(*) FROM public.maya_questions q LEFT JOIN public.maya_conversations c ON c.id=q.conversation_id WHERE c.id IS NULL),
 (SELECT count(*) FROM public.maya_conversations c LEFT JOIN public.maya_analyses a ON a.id=c.analysis_id WHERE a.id IS NULL);
SQL
echo 'integrity_queries=OK' | tee -a "$REPORT"

read -r -s -p 'DATA_ENCRYPTION_KEY (cofre): ' KEY_V1; echo >&2
read -r -s -p 'DATA_ENCRYPTION_KEYS JSON (cofre): ' KEY_RING; echo >&2
read -r -s -p 'DATA_ENCRYPTION_ACTIVE_KEY (cofre): ' KEY_ACTIVE; echo >&2

# Rootless/SELinux hosts may deny a bind mount of the workspace. Copy only
# source code (never .env or keys) into the validator's disposable filesystem.
podman run -d --rm \
  --name "$VALIDATOR" \
  --label io.echora.restore-purpose=disposable \
  --label io.echora.restore-instance="$INSTANCE" \
  --network "$NETWORK" \
  --entrypoint sh \
  "$VALIDATOR_IMAGE" -c 'sleep 300' >/dev/null
created_validator=1
podman exec --user 0 "$VALIDATOR" mkdir -p /restore-src/backend
podman cp "$ROOT/backend/." "$VALIDATOR:/restore-src/backend/" >/dev/null
podman cp "$ROOT/scripts/validate_restore_crypto.py" "$VALIDATOR:/restore-src/" >/dev/null

printf '%s\n%s\n%s\n' "$KEY_V1" "$KEY_RING" "$KEY_ACTIVE" \
  | podman exec -i --user 0 \
      -e APP_ENV=test \
      -e DATABASE_URL=sqlite:///:memory: \
      -e ECHORA_RESTORE_ALLOWED_HOST="$PG_ALIAS" \
      -e ECHORA_RESTORE_DATABASE_URL="postgresql+psycopg://echora_restore_admin@${PG_ALIAS}:5432/$DB" \
      "$VALIDATOR" \
      python /restore-src/validate_restore_crypto.py --keys-stdin \
  | tee -a "$REPORT"

echo "report=$REPORT"
echo "elapsed_seconds=$(( $(date +%s) - START_EPOCH ))" | tee -a "$REPORT"
echo 'restore isolated validation completed'
