#!/usr/bin/env bash
set -euo pipefail
: "${ECHORA_BACKUP_DIR:?Configure o diretório de backup}"
: "${ECHORA_BACKUP_RECIPIENT:?Configure a chave pública GPG do destinatário}"
: "${PGSERVICE:?Configure um serviço libpq protegido para backup}"
umask 077
mkdir -p -- "$ECHORA_BACKUP_DIR"
backup_tmp=$(mktemp "$ECHORA_BACKUP_DIR/.echora.XXXXXXXX")
trap 'rm -f -- "$backup_tmp"' EXIT
backup_name="echora-$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$backup_tmp").dump.gpg"
pg_dump --format=custom | gpg --batch --yes --encrypt --recipient "$ECHORA_BACKUP_RECIPIENT" > "$backup_tmp"
mv -- "$backup_tmp" "$ECHORA_BACKUP_DIR/$backup_name"
trap - EXIT
