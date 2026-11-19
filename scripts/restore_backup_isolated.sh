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
EXPECTED_ALEMBIC_REVISION=${ECHORA_EXPECTED_ALEMBIC_REVISION:-a7d41e6b2c90}

case "$EXPECTED_ALEMBIC_REVISION" in
  [a-f0-9]*) ;;
  *) echo 'ECHORA_EXPECTED_ALEMBIC_REVISION inválida' >&2; exit 2 ;;
esac

REPORT="${TMPDIR:-/tmp}/echora-restore-pending-$$.report"
pending=0
record() {
  local state=$1 name=$2 detail=$3
  printf '%s %s: %s\n' "$state" "$name" "$detail" | tee -a "$REPORT"
  if [ "$state" = PENDING ]; then pending=1; fi
  return 0
}

case "$BACKUP" in
  /*) ;;
  *) echo 'backup deve usar caminho absoluto' >&2; exit 2 ;;
esac
if [ ! -f "$BACKUP" ]; then
  record FAIL backup "arquivo ausente"
  exit 1
fi
if [ "$(basename "$BACKUP")" != echora-pre-v2-20261119-215505.dump ]; then
  record FAIL backup "nome inesperado"
  exit 1
fi

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
  unset KEY_V1 KEY_RING KEY_ACTIVE
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
    purpose=$(podman network inspect "$NETWORK" --format '{{index .Labels "io.echora.restore-purpose"}}' 2>/dev/null || true)
    label=$(podman network inspect "$NETWORK" --format '{{index .Labels "io.echora.restore-instance"}}' 2>/dev/null || true)
    if [ "$purpose" = disposable ] && [ "$label" = "$INSTANCE" ]; then
      podman network rm "$NETWORK" >/dev/null 2>&1 || true
    else
      echo 'FAIL network cleanup: ownership labels did not match; network preserved' >&2
    fi
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
record PASS tools "PostgreSQL e pg_restore disponíveis"

if ! podman image inspect "$VALIDATOR_IMAGE" >/dev/null; then
  record FAIL validator_image "imagem ausente"
  exit 1
fi
if ! podman run --rm --network none --entrypoint python "$VALIDATOR_IMAGE" -c \
  'import cryptography, pydantic, pydantic_settings, psycopg, sqlalchemy'; then
  record FAIL validator_dependencies "dependência ausente na imagem"
  exit 1
fi
record PASS validator_dependencies "cryptography, pydantic, psycopg e sqlalchemy presentes"
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
if ! podman exec --user 0 "$INSTANCE" pg_restore \
  --exit-on-error \
  --no-owner \
  --no-acl \
  -h 127.0.0.1 \
  -U echora_restore_admin \
  -d "$DB" \
  /restore-tmp/backup.dump 2>&1 | tee -a "$REPORT"; then
  record FAIL pg_restore "restauração falhou"
  exit 1
fi
podman exec --user 0 "$INSTANCE" rm -f /restore-tmp/backup.dump
record PASS pg_restore "restauração concluída sem erro"

if ! podman exec "$INSTANCE" psql -X -v ON_ERROR_STOP=1 \
  -v expected_revision="$EXPECTED_ALEMBIC_REVISION" \
  -A -t -F '|' -U echora_restore_admin -d "$DB" <<'SQL' | tee -a "$REPORT"
DO $$
DECLARE required text;
BEGIN
  FOREACH required IN ARRAY ARRAY[
    'alembic_version','users','feedbacks','maya_analyses',
    'maya_conversations','maya_questions','maya_daily_quotas'
  ] LOOP
    IF to_regclass('public.' || required) IS NULL THEN
      RAISE EXCEPTION 'required table missing: %', required;
    END IF;
  END LOOP;
END $$;

DO $$
DECLARE actual text;
BEGIN
  SELECT version_num INTO actual FROM public.alembic_version;
  IF actual IS DISTINCT FROM :'expected_revision' THEN
    RAISE EXCEPTION 'unexpected Alembic revision';
  END IF;
END $$;

DO $$
DECLARE bad bigint;
BEGIN
  SELECT count(*) INTO bad
  FROM pg_constraint
  WHERE connamespace='public'::regnamespace AND NOT convalidated;
  IF bad <> 0 THEN RAISE EXCEPTION 'unvalidated constraints'; END IF;
END $$;

DO $$
DECLARE fk record; n bigint; child_cols text; parent_cols text; joins text; notnulls text; probe text; q text;
BEGIN
  FOR fk IN
    SELECT conname, conrelid, confrelid, conkey, confkey
    FROM pg_constraint
    WHERE contype='f' AND connamespace='public'::regnamespace
  LOOP
    SELECT string_agg(format('c.%I', ca.attname), ', ' ORDER BY x.ord),
           string_agg(format('p.%I', pa.attname), ', ' ORDER BY x.ord),
           string_agg(format('p.%I = c.%I', pa.attname, ca.attname), ' AND ' ORDER BY x.ord),
           string_agg(format('c.%I IS NOT NULL', ca.attname), ' AND ' ORDER BY x.ord),
           format('p.%I IS NULL', min(pa.attname))
    INTO child_cols, parent_cols, joins, notnulls, probe
    FROM unnest(fk.conkey) WITH ORDINALITY AS x(attnum, ord)
    JOIN pg_attribute ca ON ca.attrelid=fk.conrelid AND ca.attnum=x.attnum
    JOIN unnest(fk.confkey) WITH ORDINALITY AS y(attnum, ord) ON y.ord=x.ord
    JOIN pg_attribute pa ON pa.attrelid=fk.confrelid AND pa.attnum=y.attnum;
    q := format('SELECT count(*) FROM %s c LEFT JOIN %s p ON %s WHERE %s AND %s',
                fk.conrelid::regclass, fk.confrelid::regclass, joins, notnulls, probe);
    EXECUTE q INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'foreign key violation: %', fk.conname; END IF;
  END LOOP;
END $$;

DO $$
DECLARE t text; c text;
BEGIN
  FOREACH t IN ARRAY ARRAY['feedbacks','maya_analyses'] LOOP
    FOREACH c IN ARRAY ARRAY['content_encrypted','nonce'] LOOP
      IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=t AND column_name=c) THEN RAISE EXCEPTION 'required AES column missing'; END IF;
    END LOOP;
  END LOOP;
  FOREACH c IN ARRAY ARRAY['question_encrypted','question_nonce','answer_encrypted','answer_nonce'] LOOP
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='maya_questions' AND column_name=c) THEN RAISE EXCEPTION 'required Maya AES column missing'; END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM public.feedbacks WHERE content_encrypted IS NULL OR nonce IS NULL)
     OR EXISTS (SELECT 1 FROM public.maya_analyses WHERE content_encrypted IS NULL OR nonce IS NULL)
     OR EXISTS (SELECT 1 FROM public.maya_questions WHERE question_encrypted IS NULL OR question_nonce IS NULL)
     OR EXISTS (SELECT 1 FROM public.maya_questions WHERE (answer_encrypted IS NULL) <> (answer_nonce IS NULL))
  THEN RAISE EXCEPTION 'invalid AES nullability'; END IF;
END $$;

SELECT current_database(), current_user, current_setting('server_version');
SELECT 'users', count(*) FROM public.users
UNION ALL SELECT 'feedbacks', count(*) FROM public.feedbacks
UNION ALL SELECT 'maya_analyses', count(*) FROM public.maya_analyses
UNION ALL SELECT 'maya_questions', count(*) FROM public.maya_questions;
SQL
then
  record FAIL integrity "tabelas, revisão, constraints, relações ou nulabilidade inválidas"
  exit 1
fi
record PASS required_tables "tabelas obrigatórias presentes"
record PASS alembic_revision "revisão esperada confirmada"
record PASS constraints "constraints validadas"
record PASS declared_constraints "constraints referenciais validadas; verificações semânticas seguem"
record PASS aes_columns "campos AES presentes e nulabilidade consistente"
record PASS row_counts "contagens obtidas após as validações"

ORPHANS=$(podman exec "$INSTANCE" psql -X -v ON_ERROR_STOP=1 -A -t -F '|' \
  -U echora_restore_admin -d "$DB" -c "
SELECT
  (SELECT count(*) FROM public.maya_questions q
   LEFT JOIN public.maya_conversations c ON c.id=q.conversation_id
   WHERE c.id IS NULL),
  (SELECT count(*) FROM public.maya_conversations c
   LEFT JOIN public.maya_analyses a ON a.id=c.analysis_id
   WHERE a.id IS NULL);
" | tr -d '\r')
if [ "$ORPHANS" != '0|0' ]; then
  record FAIL foreign_keys "violações de relação Maya detectadas"
  exit 1
fi
record PASS foreign_keys "nenhum órfão Maya; relações nullable não foram rejeitadas"

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
for module in \
  backend/app/__init__.py \
  backend/app/core/__init__.py \
  backend/app/core/config.py \
  backend/app/core/crypto.py \
  backend/scripts/__init__.py \
  backend/scripts/rotate_data_encryption.py
do
  test -f "$ROOT/$module" || { record FAIL validator_source "módulo ausente: $module"; exit 1; }
  destination="/restore-src/$module"
  podman exec --user 0 "$VALIDATOR" mkdir -p "$(dirname "$destination")"
  podman cp "$ROOT/$module" "$VALIDATOR:$destination" >/dev/null
done
podman cp "$ROOT/scripts/validate_restore_crypto.py" "$VALIDATOR:/restore-src/" >/dev/null

set +e
printf '%s\n%s\n%s\n' "$KEY_V1" "$KEY_RING" "$KEY_ACTIVE" \
  | podman exec -i --user 0 \
      -e APP_ENV=test \
      -e DATABASE_URL=sqlite:///:memory: \
      -e ECHORA_RESTORE_ALLOWED_HOST="$PG_ALIAS" \
      -e ECHORA_RESTORE_DATABASE_URL="postgresql+psycopg://echora_restore_admin@${PG_ALIAS}:5432/$DB" \
      "$VALIDATOR" \
      python /restore-src/validate_restore_crypto.py --keys-stdin \
  | tee -a "$REPORT"
validator_rc=${PIPESTATUS[1]}
set -e
if [ "$validator_rc" -eq 2 ]; then
  unset KEY_V1 KEY_RING KEY_ACTIVE
  record PENDING aes_decryption "chaves ausentes ou validação não concluída"
  exit 3
elif [ "$validator_rc" -ne 0 ]; then
  unset KEY_V1 KEY_RING KEY_ACTIVE
  record FAIL aes_decryption "validação AES falhou"
  exit 1
fi
unset KEY_V1 KEY_RING KEY_ACTIVE
record PASS aes_decryption "todos os campos AES validados sem expor conteúdo"

echo "report=$REPORT"
echo "elapsed_seconds=$(( $(date +%s) - START_EPOCH ))" | tee -a "$REPORT"
if [ "$pending" -ne 0 ]; then
  record PENDING final "há validações pendentes; não autorizar restauração"
  exit 3
fi
record PASS final "restauração isolada aprovada pelo procedimento"
