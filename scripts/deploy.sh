#!/usr/bin/env bash
# 一键部署/升级：构建起栈 → 等待健康 → 迁移 → （可选）seed → 健康验证
#
# 用法：
#   ./scripts/deploy.sh              # 常规部署/升级（不动数据）
#   SEED=1 ./scripts/deploy.sh       # 部署并灌入演示数据（含 admin/Admin@123）
#   NO_BUILD=1 ./scripts/deploy.sh   # 跳过镜像构建（仅重建容器）
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=${COMPOSE:-docker compose}

if ! $COMPOSE version >/dev/null 2>&1; then
  echo "[x] 未检测到 docker compose 插件，请先安装 Docker ≥ 24" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "[!] 缺少 .env，已从 .env.example 复制——请修改 SECRET_KEY / DB_PASSWORD 后重跑"
  cp .env.example .env
  exit 1
fi

echo "==> [1/5] 构建并启动全栈"
if [ "${NO_BUILD:-0}" = "1" ]; then
  $COMPOSE up -d
else
  $COMPOSE up -d --build
fi

echo "==> [2/5] 等待 web 健康检查通过"
for i in $(seq 1 30); do
  if $COMPOSE exec -T web python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" >/dev/null 2>&1; then
    break
  fi
  [ "$i" = 30 ] && { echo "[x] web 未在 150s 内就绪，查看日志：$COMPOSE logs web" >&2; exit 1; }
  sleep 5
done
echo "    web healthy"

echo "==> [3/5] 数据库迁移"
$COMPOSE exec -T web sh -c "cd /app && python manage.py migrate --noinput"

if [ "${SEED:-0}" = "1" ]; then
  echo "==> [4/5] 灌入演示数据（seed_demo：10-31 已对平样例 + 11-01 夹具 + admin/Admin@123）"
  $COMPOSE exec -T web sh -c "cd /app && python manage.py seed_demo"
else
  echo "==> [4/5] 跳过 seed（SEED=1 可启用）"
fi

echo "==> [5/5] 验证"
STATUS=$($COMPOSE exec -T web python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3))['status'])")
$COMPOSE ps
echo
echo "[√] 部署完成（health=${STATUS}）"
echo "    前端:   http://<host>/          （默认 80 端口）"
echo "    API 文档: http://<host>/api/docs/"
[ "${SEED:-0}" = "1" ] && echo "    演示账号: admin / Admin@123（首次登录强制改密）"
