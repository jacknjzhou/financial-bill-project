# 部署文档（对账系统一期 v1.0.0-phase1）

一套 Docker Compose 全栈：`postgres / redis / web(gunicorn) / worker(celery) / beat(celery) / frontend(nginx)`。
日常操作优先使用 Makefile 目标；脚本化部署用 `scripts/`。

## 1. 实体机要求

- Linux x86_64（Ubuntu 22.04 / Rocky 9 均可），4C / 8G 内存 / 50G 磁盘
- Docker ≥ 24 + Docker Compose 插件（`docker compose version` 可用）
- 开放 80 端口（内网）

## 2. 在线部署（推荐：一键脚本）

```bash
git clone <repo-url> recon && cd recon
git checkout v1.0.0-phase1
cp .env.example .env          # 修改 SECRET_KEY / DB_PASSWORD（见 §3）
./scripts/deploy.sh           # 构建 → 健康等待 → migrate → 验证
# SEED=1 ./scripts/deploy.sh  # 需要演示数据时（含 admin/Admin@123）
```

或用 Makefile（等价）：

```bash
make deploy           # 部署/升级
make seed             # 演示数据（幂等）
make health           # 健康检查
```

## 3. `.env` 配置项

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| SECRET_KEY | Django 密钥（**生产必须改**） | 随机 50 位 |
| DEBUG | 生产必须为 0 | 0 |
| FRONTEND_ORIGIN | 前端来源（CSRF 信任，多个逗号分隔） | http://10.x.x.x |
| DB_NAME / DB_USER / DB_PASSWORD | Postgres 凭据（**生产改密码**） | recon/recon/<强密码> |
| DB_HOST / DB_PORT | 容器内由 compose 覆盖为 postgres:5432 | localhost |
| REDIS_URL | 容器内由 compose 覆盖 | redis://localhost:6379/0 |
| FILES_ROOT | 账单文件存储根（容器内固定 /data/files，共享卷） | /data/files |
| CELERY_TASK_ALWAYS_EAGER | 必须 0（生产用真实 worker） | 0 |
| OIDC_ENABLED | SSO 开关 | 0（一期默认本地登录） |
| OIDC_ISSUER / CLIENT_ID / CLIENT_SECRET | SSO 参数（启用时填） | — |
| OIDC_ROLE_MAP | IdP claim → 角色 JSON | {"ops":"operator"} |
| EMAIL_BACKEND / EMAIL_HOST / … | 告警邮件（默认 console 打日志） | smtp |
| ALERT_EMAIL_TO | 告警邮箱（逗号分隔） | ops@corp.com |

## 4. 验证清单

1. `curl http://<host>/api/health` → `{"status":"ok","db":true}`
2. 浏览器开 `http://<host>/` → 登录页
3. `http://<host>/api/docs/` → Swagger UI 可打开；`/api/redoc/` 只读版
4. admin 登录（seed_demo 后初始密码 `Admin@123`）→ **强制改密** → 9 个页面均可打开（工作台/对账项目/对账结果/差错处理/对账运行/文件管理/数据查询/基础配置/系统管理）
5. 全链路（可选）：上传 11-01 夹具（`data/demo/`）→ 对账运行触发 → 结果计数 40 对平 / 10 单边A / 5 单边B / 10 错账

## 5. 备份与恢复

```bash
./scripts/backup.sh            # DB + 账单文件 → ./backups/<时间戳>/（默认保留 14 份）
DB_ONLY=1 ./scripts/backup.sh  # 仅数据库
```

建议 cron（每日 02:00 全量）：

```cron
0 2 * * * cd /opt/recon && ./scripts/backup.sh >> backups/backup.log 2>&1
```

恢复（**危险操作：DROP 现库后覆盖，脚本需输入 YES 确认**）：

```bash
./scripts/restore.sh backups/2026-11-03_020000/db.sql.gz
./scripts/restore.sh backups/2026-11-03_020000/db.sql.gz backups/2026-11-03_020000/files.tgz
```

> 文件备份与 DB 必须同频率：账单原始文件是审计依据（对账结果 PROTECT 引用），只备 DB 不备文件会导致历史结果无法回溯原文。

## 6. 升级与回滚

升级（数据卷保留）：

```bash
git fetch && git checkout <新tag>
./scripts/deploy.sh            # 重新构建 + migrate（幂等）
```

回滚：

```bash
git checkout <上一个tag>
./scripts/deploy.sh
# 若新版本执行过迁移，回滚后需人工评估 schema 差异（一期无破坏性迁移前置依赖）
```

## 7. 生产安全清单

- [ ] `DEBUG=0`（关闭 Django 调试页）
- [ ] `SECRET_KEY` 换为随机值（`python -c "import secrets;print(secrets.token_urlsafe(50))"`）
- [ ] `DB_PASSWORD` 强密码；postgres 端口不对内网以外开放（compose 的 ports 映射仅本机调试用，生产可删）
- [ ] `FRONTEND_ORIGIN` 填实际访问地址（否则登录后 POST 会 CSRF 403）
- [ ] 首次登录后立即修改 admin 密码（系统强制），或直接不 seed、用「系统管理」建号
- [ ] HTTPS：内网系统建议由统一 LB/网关终止 TLS 后反代到 80（应用本身只出 HTTP）
- [ ] `ALLOWED_HOSTS` 当前代码为 `["*"]`（内网定位）；如需收紧，改 `backend/src/financial_bill/settings.py` 后重新构建

## 8. 离线部署（无外网实体机）

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
cd recon && NO_BUILD=1 ./scripts/deploy.sh
```

## 9. 日常运维

```bash
make logs                                  # 全服务日志
docker compose logs -f --tail=100 worker   # 只看 worker（对账执行/解析）
docker compose up -d --scale worker=4      # 扩 worker（对账高峰期）
make backup                                # 手工备份
make health                                # 探活
```

- **时区**：系统按 Asia/Shanghai 展示，DB 存 UTC；对账日期（reconcile_date）为本地日期
- **对账节奏**：T+1（对账日期 = 今天-1），beat 每 30 分钟扫描到期项目；手工触发在对账运行页（可选任意日期）
- **扩容**：无状态服务（web/worker/beat/frontend）均可水平扩；postgres/redis 单点（一期定位）

## 10. 常见问题（FAQ）

| 现象 | 原因与处理 |
| --- | --- |
| 上传后一直「解析失败」 | worker 读不到文件：确认 compose 三服务均挂 `filedata:/data` 卷且 `FILES_ROOT=/data/files` 一致；`docker compose logs worker` 看具体报错 |
| 登录后首个 POST 403 CSRF | `FRONTEND_ORIGIN` 未配置或与实际访问地址（含端口）不一致；改 .env 后 `docker compose up -d web` |
| health 返回 `degraded` | DB 不可达：查 postgres 容器状态与 `DB_*` 凭据 |
| 对账触发报「前一日未对平」 | 连续性规则（D-1 需 success）。历史补跑用对账运行页的「重对」（跳过连续性） |
| 差异结果重复出现 | 重对幂等基于确定性 group_no；若手工改过 DB 才会出现，勿直接改 ReconcileResult/Dispute |
| 定时对账没跑 | beat 容器是否存活（`docker compose ps beat`）；项目 `exec_time` 是否已到且昨日无 success run |

## 11. 初始账号

- `seed_demo` 幂等创建 `admin / Admin@123`（演示用；生产上首次登录强制改密）
- 其他用户由 admin 在「系统管理」创建，或走 SSO（OIDC）自动建号
