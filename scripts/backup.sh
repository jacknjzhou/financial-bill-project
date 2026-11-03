#!/usr/bin/env bash
# 备份：Postgres 逻辑备份 + 账单文件卷 → ./backups/<时间戳>/
#
# 用法：
#   ./scripts/backup.sh                 # 全量（DB + 文件）
#   DB_ONLY=1 ./scripts/backup.sh       # 仅数据库
#   KEEP=7 ./scripts/backup.sh          # 保留最近 7 份（默认 14）
#
# 建议 cron（每日 02:00）：
#   0 2 * * * cd /opt/recon && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=${COMPOSE:-docker compose}
BACKUP_DIR=${BACKUP_DIR:-./backups}
KEEP=${KEEP:-14}
STAMP=$(date +%F_%H%M%S)
DEST="$BACKUP_DIR/$STAMP"

mkdir -p "$DEST"

# 从 .env 取 DB 凭据（有默认值兜底，与 settings.py 一致）
DB_NAME=$(grep -E '^DB_NAME=' .env 2>/dev/null | cut -d= -f2 || true)
DB_USER=$(grep -E '^DB_USER=' .env 2>/dev/null | cut -d= -f2 || true)
DB_NAME=${DB_NAME:-recon}
DB_USER=${DB_USER:-recon}

echo "==> 备份数据库 $DB_NAME → $DEST/db.sql.gz"
$COMPOSE exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$DEST/db.sql.gz"

if [ "${DB_ONLY:-0}" != "1" ]; then
  echo "==> 备份账单文件 /data/files → $DEST/files.tgz"
  $COMPOSE exec -T web tar czf - /data/files > "$DEST/files.tgz"
fi

# 清理旧备份（只留最近 KEEP 份）
ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  echo "==> 清理过期备份：$old"
  rm -rf "$old"
done

echo "[√] 备份完成：$DEST"
du -sh "$DEST"/* 2>/dev/null || true
