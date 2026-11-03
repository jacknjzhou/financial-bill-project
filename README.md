# 对账系统（财务对账 · 一期）

一套自研财务对账系统：自有支付流水 vs 渠道清算账单的 **交易对账**，覆盖「解析 → 上传入库 → 定时/手工对账 → 结果 → 差异处理 SOP」全生命周期。

![架构](docs/reference/images/01.png)

## 快速开始

```bash
cp .env.example .env                       # 按需修改（开发可先不改）
make up                                    # 起 postgres/redis/web/worker/beat/frontend 全栈（:80）
make seed                                  # 演示数据 + admin 账号（幂等）
make smoke                                 # 全链路 Playwright 冒烟（上传→对账→结果→差错→工作台）
```

打开 http://localhost/ ，账号 `admin / Admin@123`（seed_demo 后，首次登录强制改密）。

生产/实体机部署见 **[DEPLOY.md](DEPLOY.md)**（一键脚本 `./scripts/deploy.sh`、离线部署、备份恢复、安全清单）。

## 能力（一期）

- **认证**：本地账号密码 + OIDC SSO（自动建号/角色映射），admin/operator 双角色，强制改密闸门
- **配置域**：渠道/资金账户/业务类型/差错处理类型/解析规则（列映射+值映射+编码回退）/获取任务/对账项目（A/B 源+筛选+状态集+b_sum）
- **数据接入**：xlsx/csv/txt 解析（Decimal quantize 转分、整批校验回滚）、上传防重/覆盖重传（PROTECT 保护已对账数据）
- **对账引擎**：连续性控制（D-1 success）、行锁并发抢占（唯一约束兜底 409）、beat 定时扫描（T+1）、手工触发（任意日期）、匹配算法（对平/单边/错账/1vN 汇总，确定性 group_no 幂等重对）
- **差错处理**：按组物化、SOP 类型处理、全量留痕时间线、重对安全（superseded/reopened）
- **工作台**：总览三卡片、站内+邮件告警、失败重跑
- **可观测**：OpenAPI 全端点类型化（`/api/docs/` Swagger、`/api/redoc/`）、`/api/health` 探针

## 项目结构

```
├── backend/                  # Django 5 + DRF + Celery（src layout）
│   ├── src/apps/
│   │   ├── core/             #   公共：错误信封、分页、中间件
│   │   ├── accounts/         #   认证/SSO/用户管理
│   │   ├── meta/             #   基础字典（渠道/账户/业务/差错类型）
│   │   ├── rules/            #   解析规则/获取任务/对账项目
│   │   ├── dataio/           #   文件上传 + 解析引擎 + 数据入库
│   │   ├── engine/           #   对账引擎（控制/匹配/结果/告警/定时）
│   │   └── disputes/         #   差错物化 + SOP 处理 + 留痕
│   └── tests/                #   100 个后端测试（pytest）
├── frontend/                 # Vue3 + Element Plus + Vite（单页）
│   └── e2e/                  #   Playwright 全链路冒烟
├── scripts/
│   ├── deploy.sh             #   一键部署/升级（构建→健康→迁移）
│   ├── backup.sh             #   DB + 账单文件备份（保留 N 份）
│   └── restore.sh            #   恢复（二次确认）
├── docker-compose.yml        # 全栈编排（共享 filedata 卷）
├── Makefile                  # up/deploy/seed/test/smoke/backup/…
└── DEPLOY.md                 # 部署/运维/FAQ
```

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `make up` / `make down` | 起全栈（含构建）/ 停止（数据卷保留） |
| `make deploy` | 一键部署/升级（等价 `./scripts/deploy.sh`） |
| `make seed` | 灌演示数据（幂等） |
| `make test` / `make test-docker` | 本地 venv pytest / 容器内 pytest（验收口径） |
| `make smoke` | Playwright 全链路冒烟 |
| `make backup` / `make health` | 备份 / 探活 |
| `make logs` | 全服务日志 |

## 核心概念速览

- **对账项目**：定义 A 源（自有支付）/ B 源（渠道清算）、匹配键列映射、金额容差与状态集规则
- **对账日期**：T+1 自动（beat 每 30 分钟扫描），也支持在「对账运行」页选任意日期手工触发
- **结果四态**：对平 / 单边A / 单边B / 错账（1vN 按组聚合，`group_no` 确定性生成，重对幂等）
- **差错处理**：差异自动物化为差错单 → 选 SOP 类型处理 → 时间线留痕；重对后未复现的差错标 superseded，仍存在的标 reopened

## 文档索引

- 规格：`docs/superpowers/specs/2026-10-31-对账系统-design.md`
- 一期计划：`docs/superpowers/plans/2026-10-31-对账系统一期.md`
- 计划评审：`docs/superpowers/reviews/2026-11-03-一期plan评审报告.md`
- 部署与运维：`DEPLOY.md`
- 领域参考：`docs/reference/一文搞懂对账系统-正文.md`

## 路线图

- **一期（本仓库 v1.0.0-phase1）**：交易对账全链路（上文能力）
- **二期**：资金对账（清算 vs 结算）、余额调节、差错统计报表
- **三期**：获取方式扩展（API/SFTP）、自动重对、差错处理工作流审批

## 技术栈

Django 5 + DRF + Celery + PostgreSQL 16 + Redis 7 + Vue3 + Element Plus + Vite + Playwright。
