#!/usr/bin/env bash
set -euo pipefail
: "${ECHORA_BACKUP_DIR:?Configure o diretório de backup}"
: "${ECHORA_BACKUP_RECIPIENT:?Configure o destinatário GPG}"
: "${PGPASSWORD:?Configure a senha da conta echora_backup no ambiente protegido}"
ECHORA_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PGPASSWORD
umask 077
mkdir -p -- "$ECHORA_BACKUP_DIR"
backup_tmp=$(mktemp "$ECHORA_BACKUP_DIR/.echora.XXXXXXXX")
trap 'rm -f -- "$backup_tmp"' EXIT
backup_name="echora-$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$backup_tmp").dump.gpg"
docker compose --env-file "$ECHORA_ROOT/deploy/compose.env" -f "$ECHORA_ROOT/compose.prod.yml" exec -T --user 70:70 -e PGPASSWORD postgres \
  pg_dump -h 127.0.0.1 -U echora_backup -d echora --format=custom --no-owner --no-acl \
  | gpg --batch --yes --encrypt --recipient "$ECHORA_BACKUP_RECIPIENT" > "$backup_tmp"
mv -- "$backup_tmp" "$ECHORA_BACKUP_DIR/$backup_name"
trap - EXIT
