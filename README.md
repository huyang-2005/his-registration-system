# 门诊挂号与收费发药分系统（HIS）

课程：医院信息系统实验 · A 路线业务闭环
技术栈：FastAPI + Jinja2 + SQLite + JWT/bcrypt

## 功能闭环

登录权限 → 患者建档 → 排班号源 → 挂号/退号/挂号收费 → 医生开方（后端划价）
→ 收费台（收费 + FIFO 扣库存，同一事务）→ 药房发药 → 审计日志 → 统计报表

附加：药品字典 CSV 批量导入、AI 智能分诊（可降级）。

## 快速开始（本地）

```bash
python -m pip install -r requirements.txt
python scripts/refresh_demo_data.py
python -m uvicorn app.main:app --reload --port 8000
```

浏览器打开 http://127.0.0.1:8000/login

演示账号（统一密码 `His@123456`）：

| 用户名 | 角色 | 可用功能 |
| --- | --- | --- |
| admin | 管理员 | 全部功能、基础数据、审计日志 |
| doctor | 医生 | 挂号查询、开方、药品查询、AI 分诊 |
| cashier | 收费员 | 建档、挂号/退号/挂号收费、处方收费、报表 |
| pharmacist | 药师 | 药品字典、入库、药房发药 |

## Docker 一键启动

```bash
copy .env.example .env
# 编辑 .env，至少填写 SECRET_KEY
docker compose up --build
```

访问 http://127.0.0.1:8000，SQLite 数据存放在 `his_data` 数据卷。

## 公网部署（Render）

1. 把代码推到 GitHub（`.env` 已被忽略，不会泄露密钥）。
2. Render → New → Web Service → 连接仓库；仓库内 `render.yaml` 已写好构建/启动命令。
3. Build：`pip install -r requirements.txt`；Start：`python scripts/refresh_demo_data.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`。
4. 在 Render 后台配置 `SECRET_KEY`（Generate）、`HIS_DB_PATH=/tmp/his.db`、`HIS_DATA_DIR=/tmp/data`、`DEEPSEEK_API_KEY`。
5. 部署完成后访问 `https://你的服务名.onrender.com/login`。

完整 8 步操作与免费层注意事项见 `docs/实验09-部署说明.md`。当前本机已配置 `.env`（不提交仓库），真实 AI 分诊已验证可用。

## 目录结构

```
app/
  main.py         应用工厂、中间件、异常处理
  config.py       环境变量配置
  db.py           SQLite 连接、迁移、事务
  security.py     bcrypt + JWT
  deps.py         登录用户解析、角色鉴权
  middleware.py   用户上下文、写操作审计
  migrations/     增量迁移脚本（禁止删库重建）
  routers/        页面路由 + JSON API
  services/       业务规则（挂号事务/划价/库存/发药/导入/分诊）
  schemas/        Pydantic 入参模型
templates/        Jinja2 页面
static/           样式与 CSV 演示文件
tests/            pytest（单元 + API），e2e/ 为 Playwright
scripts/          迁移、演示数据、RBAC 验证、CSV 生成
docs/             验收、答辩与实验提交文档
```

## 关键业务规则

1. 金额只由后端按药品档案单价计算，前端传价格一律不采信。
2. 挂号：`BEGIN IMMEDIATE` 事务内扣号源 + 生成挂号单，满号 409。
3. 处方收费：写收费单 + 处方置“已收费” + FIFO 扣库存，任一步失败整体回滚；库存不足 400。
4. 发药：仅“已收费”可发药，重复操作 409。
5. 密码 bcrypt 哈希；JWT 放 HttpOnly Cookie，同时支持 Bearer。
6. 写操作由中间件自动写审计日志（用户/动作/对象/IP/详情）。

## 测试

```bash
python -m pytest tests -q --ignore=tests/e2e
python scripts/verify_rbac.py
```

E2E（Playwright，需先启动 8000 端口服务）：

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
set RUN_E2E=1
python -m pytest tests/e2e -q
```

## 文档索引

- `docs/实验12-功能点清单核验表.md`
- `docs/实验12-演示脚本.md`
- `docs/答辩手册.md`
- `docs/实验07-安全审查报告.md`
- `docs/实验08-测试与CodeReview报告.md`
- `docs/实验09-部署说明.md`
- `docs/实验10-数据字典与审计说明.md`
- `docs/实验11-AI功能合规自查表.md`
- `docs/AI协作开发日志（实验05-11）.md`
- `docs/实验12-复盘与个人总结模板.md`
