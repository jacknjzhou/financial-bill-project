#!/usr/bin/env bash
# 恢复：从 backup.sh 的产物恢复数据库（及可选的账单文件）。
# ⚠️ 危险操作：将 DROP 现有数据库后重建恢复，请确认备份文件路径无误。
#
# 用法：
#   ./scripts/restore.sh backups/2026-11-03_020000/db.sql.gz
#   ./scripts/restore.sh backups/2026-11-03_020000/db.sql.gz backups/2026-11-03_020000/files.tgz
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=${COMPOSE:-docker compose}
SQL=$1
FILES_TGZ=${2:-}

[ -f "$SQL" ] || { echo "[x] 备份文件不存在：$SQL" >&2; exit 1; }
if [ -n "$FILES_TGZ" ] && [ ! -f "$FILES_TGZ" ]; then
  echo "[x] 文件包不存在：$FILES_TGZ" >&2
  exit 1
fi

DB_NAME=$(grep -E '^DB_NAME=' .env 2>/dev/null | cut -d= -f2 || true)
DB_USER=$(grep -E '^DB_USER=' .env 2>/dev/null | cut -d= -f2 || true)
DB_NAME=${DB_NAME:-recon}
DB_USER=${DB_USER:-recon}

echo "⚠️  此操作将 DROP 数据库「${DB_NAME}」并用 $SQL 覆盖恢复，现有数据将全部丢失！"
read -r -p "确认请输入大写 YES：" ok
[ "$ok" = "YES" ] || { echo "已取消"; exit 1; }

$COMPOSE up -d postgres >/dev/null 2>&1 || true
until $COMPOSE exec -T postgres pg_isready -U "$DB_USER" -d postgres >/dev/null 2>&1; do sleep 2; done

echo "==> 重建数据库 $DB_NAME"
$COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" \
  -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"

echo "==> 恢复数据"
gunzip -c "$SQL" | $COMPOSE exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -q -v ON_ERROR_STOP=1

if [ -n "$FILES_TGZ" ]; then
  echo "==> 恢复账单文件（覆盖容器 /data/files）"
  $COMPOSE up -d web >/dev/null 2>&1 || true
  until $COMPOSE exec -T web python -c "import pathlib;pathlib.Path('/data').exists()" >/dev/null 2>&1; do sleep 2; done
  # 通过 stdin 解包到 web 容器
  $COMPOSE exec -T web sh -c "mkdir -p /data && tar xzf - -C /data" < "$FILES_TGZ"
fi

echo "==> 迁移对齐（备份版本较旧时补齐 schema）"
$COMPOSE exec -T web sh -c "cd /app && python manage.py migrate --noinput"

echo "[√] 恢复完成，建议执行 health 验证：make health"
