.PHONY: up down ps logs seed test test-docker smoke deploy backup restore health

up:            ## 启动全部服务（含构建）
	docker compose up -d --build

down:          ## 停止（数据卷保留）
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

seed:          ## 灌入演示数据（幂等）：10-31 样例 + 11-01 夹具 + admin/Admin@123
	docker compose exec -T web sh -c "cd /app && python manage.py seed_demo"

test:          ## 本地 venv 跑测试（快速开发回路；需 .env 与 postgres/redis 已 up）
	cd backend && ../.venv/bin/python -m pytest

test-docker:   ## web 容器内跑测试（验收口径）
	docker compose exec -T web sh -c "cd /app && python -m pytest"

smoke:         ## 全链路冒烟：起栈 → seed → Playwright
	docker compose up -d --build
	docker compose exec -T web sh -c "cd /app && python manage.py migrate --noinput && python manage.py seed_demo"
	cd frontend && (npm ls @playwright/test >/dev/null 2>&1 || npm i -D @playwright/test) && (npx playwright install chromium --with-deps 2>/dev/null || npx playwright install chromium)
	cd frontend && npx playwright test -c e2e/playwright.config.ts e2e/smoke.spec.ts

deploy:        ## 一键部署/升级（构建 → 健康 → 迁移）；SEED=1 附带演示数据
	./scripts/deploy.sh

backup:        ## 备份 DB + 账单文件到 ./backups/<时间戳>/（KEEP=14 可改份数）
	./scripts/backup.sh

restore:       ## 恢复：make restore B=<db.sql.gz> [F=<files.tgz>]（危险，二次确认）
	./scripts/restore.sh $(B) $(F)

health:        ## 健康检查（web 探针 + 各容器状态）
	curl -fsS http://localhost/api/health && echo
	docker compose ps
