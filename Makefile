.PHONY: up down ps logs test test-docker smoke

up:            ## 启动全部服务（含构建）
	docker compose up -d --build

down:          ## 停止（数据卷保留）
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

test:          ## 本地 venv 跑测试（快速开发回路；需 .env 与 postgres/redis 已 up）
	cd backend && ../.venv/bin/python -m pytest

test-docker:   ## web 容器内跑测试（验收口径）
	docker compose exec -T web sh -c "cd /app && python -m pytest"

smoke:         ## 全链路冒烟：起栈 → seed → Playwright
	docker compose up -d --build
	docker compose exec -T web sh -c "cd /app && python manage.py migrate --noinput && python manage.py seed_demo"
	cd frontend && (npm ls @playwright/test >/dev/null 2>&1 || npm i -D @playwright/test) && (npx playwright install chromium --with-deps 2>/dev/null || npx playwright install chromium)
	cd frontend && npx playwright test -c e2e/playwright.config.ts e2e/smoke.spec.ts
