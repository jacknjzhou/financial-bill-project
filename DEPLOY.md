# 部署文档（对账系统一期 v1.0.0-phase1）

## 实体机要求

- Linux x86_64（Ubuntu 22.04 / Rocky 9 均可），4C / 8G 内存 / 50G 磁盘
- Docker ≥ 24 + Docker Compose 插件（`docker compose version` 可用）
- 开放 80 端口（内网）

## 在线部署

```bash
git clone <repo-url> recon && cd recon
git checkout v1.0.0-phase1
cp .env.example .env   # 若仓库未带示例，按下表逐项写 .env
docker compose up -d --build
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py seed_demo   # 可选：演示数据（含 admin 账号）
```

`.env` 关键项：

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| SECRET_KEY | Django 密钥（生产必须改） | 随机 50 位 |
| DEBUG | 必须 0 | 0 |
| FRONTEND_ORIGIN | 前端来源（CSRF 信任） | http://10.x.x.x |
| DB_NAME/USER/PASSWORD | Postgres 凭据 | recon/recon/<强密码> |
| REDIS_URL | Redis | redis://redis:6379/0 |
| FILES_ROOT | 账单文件存储根 | /data/files |
| OIDC_ENABLED | SSO 开关 | 0（一期默认本地登录） |
| OIDC_ISSUER/CLIENT_ID/CLIENT_SECRET | SSO 参数（启用时填） | — |
| ALERT_EMAIL_TO | 告警邮箱 | ops@corp.com |

### 验证清单

1. `curl http://<host>/api/health` → `{"status":"ok","db":true}`
2. 浏览器开 `http://<host>/` → 登录页
3. `http://<host>/api/docs/` → Swagger UI 可打开
4. admin 登录（seed_demo 后初始密码 `Admin@123`）→ **强制改密** → 9 个页面均可打开（工作台/对账项目/对账结果/差错处理/对账运行/文件管理/数据查询/基础配置/系统管理）

## 离线部署（无外网实体机）

有网机器上：

```bash
cd recon && git checkout v1.0.0-phase1
docker compose build
mkdir -p /tmp/recon-images
docker save $(docker compose config --images | tr '\n' ' ') -o /tmp/recon-images/recon-images.tar
# 同时拷贝：整个代码目录（不含 .git 可）+ .env
```

介质（tar 包 + 代码目录 + .env）拷到实体机：

```bash
docker load -i /tmp/recon-images/recon-images.tar
cd recon && docker compose up -d
docker compose exec web python manage.py migrate --noinput
```

## 日常运维

```bash
docker compose logs -f --tail=100 web worker beat   # 看日志
docker compose up -d --scale worker=4               # 扩 worker
docker compose exec postgres pg_dump -U recon recon > backup_$(date +%F).sql
docker compose exec -T web tar czf - /data/files > files_$(date +%F).tgz  # 账单文件备份（与 DB 同频率）
```

- **升级**：拉新 tag → `docker compose up -d --build` → migrate（数据卷保留）
- **时区**：系统按 Asia/Shanghai 展示，DB 存 UTC；对账日期（reconcile_date）为本地日期
- **对账节奏**：T+1（对账日期 = 今天-1），beat 每 30 分钟扫描到期项目

## 初始账号

- `seed_demo` 幂等创建 `admin / Admin@123`（演示用；生产上首次登录强制改密）
- 其他用户由 admin 在「系统管理」创建，或走 SSO（OIDC）自动建号
