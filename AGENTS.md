# AGENTS.md — 项目协作与目录规范

本文件供 AI 助手与团队成员共同遵守，新增功能必须落在既有结构内。

## 目录约定

- `app/routers/`：只做 HTTP 层——参数接收、鉴权依赖、调用 service、渲染/返回 JSON。
- `app/services/`：业务规则与事务。所有涉及多表写入的逻辑必须放在 service。
- `app/schemas/`：Pydantic 入参模型，表单与 JSON 分开启用。
- `app/migrations/`：数据库结构变更只能新增迁移文件（m005_xxx.py），禁止删库重建。
- `templates/`：Jinja2 页面，继承 `base.html`，样式复用 `static/style.css` 的 class。
- `tests/`：pytest；API 用例使用 `tests/conftest.py` 的临时库夹具，不污染 `his.db`。

## 编码规则

1. 金额使用 `Decimal` + `ROUND_HALF_UP`，禁止前端传价格。
2. 事务统一用 `db.transaction()`（`BEGIN IMMEDIATE`），异常必须 rollback。
3. 角色鉴权统一 `Depends(require_roles(...))`，不允许在页面里手写角色判断做授权。
4. 新增写操作要在 `app/services/audit.py` 的 `WRITE_RULES` 增加分类规则。
5. 密钥、密码、API Key 只从环境变量读取，不写进代码与仓库。
6. 页面文案用中文；错误提示要能指导用户下一步操作。

## 验证要求

每次改动后至少执行：

```bash
python -m pytest tests -q --ignore=tests/e2e
python scripts/verify_rbac.py
```

提交信息建议：`feat: ...` / `fix: ...` / `docs: ...` / `test: ...`。
