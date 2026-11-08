# 实验八 · 测试与 AI Code Review 报告

## 一、测试金字塔落地情况

| 层级 | 工具 | 文件 | 覆盖内容 |
| --- | --- | --- | --- |
| 单元测试 | pytest | `tests/test_services.py` | 划价四舍五入、数量 0/负数、库存为 1 的边界、FIFO 扣减、退号释放号源 |
| API 测试 | FastAPI TestClient | `tests/test_registration_api.py`、`tests/test_pharmacy_api.py`、`tests/test_auth.py` | 401/403/409/400、金额后端计算、重复收费、库存不足回滚、发药状态机 |
| 数据导入测试 | pytest | `tests/test_csv_import.py` | 表头缺失、空文件、非法单价、重复行、错误行不影响合法行、GBK 编码 |
| 审计/报表测试 | pytest | `tests/test_audit_report.py` | 写操作留痕、按用户/动作过滤、报表金额与操作一致 |
| E2E | Playwright | `tests/e2e/test_main_flow.py` | 登录 → 建档 → 挂号 → 开方 → 收费 → 发药 → 报表 全流程（`RUN_E2E=1` 时执行） |

## 二、运行结果

```text
python -m pytest tests -q --ignore=tests/e2e
.........................................                                [100%]
41 passed
```

E2E（真实浏览器，服务需先在 8000 端口运行）：

```text
pip install -r requirements-dev.txt
python -m playwright install chromium
set RUN_E2E=1
python -m pytest tests/e2e -q
.                                                                        [100%]
1 passed
```

全量（含 E2E）：`42 passed`。E2E 最近一次实测时间 2026-11-08，覆盖 4 个角色连续登录与状态机流转。

覆盖率（`--cov=app`）：

| 模块 | 覆盖率 |
| --- | --- |
| `services/pricing.py` | 93% |
| `services/inventory.py` | 90% |
| `services/pharmacy.py` | 85% |
| `services/csv_import.py` | 80% |
| `services/registration.py` | 76% |
| 全项目 | 66% |

说明：路由页面分支覆盖率偏低，因为测试以 API 为主；核心业务 service 覆盖率均 ≥76%。总覆盖率 66%（覆盖率 ≥70% 为实验八加分项，本次不作为必做）。

## 三、测试有效性验证（故意改错能变红）

| 改错 | 预期 | 实际 |
| --- | --- | --- |
| 把划价 `ROUND_HALF_UP` 改为直接截断 | 金额测试失败 | 失败（红） |
| 去掉收费事务中的库存校验 | `test_insufficient_stock...` 失败 | 失败（红） |
| 把发药状态判断改为 `status != '待收费'` | 发药测试失败 | 失败（红） |

恢复实现后重新运行，全部转绿。

## 四、AI Code Review 发现的问题（按严重程度）

| # | 问题 | 严重度 | 修复方式 | 人工复核 |
| --- | --- | --- | --- | --- |
| 1 | 退号不检查处方状态，可能留下待收费处方 | 高 | `cancel_registration` 增加处方状态检查，存在有效处方则 409 | 已复核：符合“先处理处方再退号”业务规则；补 `test_cancel_registration_with_prescription_is_blocked` |
| 2 | 403 异常页状态码被模板响应重置为 200 | 中 | 异常处理器渲染后显式设置 `status_code` | 已复核：越权必须返回 403，不能“页面正确但状态码 200” |
| 3 | 测试夹具与种子排班同日冲突 | 中 | fixture 改用 +5 天；满号用例 +6 天 | 已复核：测试隔离，避免依赖种子数据日期 |
| 4 | 测试断言 POST 返回 303，但 TestClient 默认跟随重定向 | 中 | 相关用例显式 `follow_redirects=False` | 已复核：断言应针对服务端响应，而非最终页面 |
| 5 | 参数化查询写成 `(presc["presc_id"])`（不是元组） | 低 | 改为 `(presc["presc_id"],)` | 已复核：避免 `sqlite3.ProgrammingError` |
| 6 | 遗留 `app.py` / 根目录 `db.py` / `init_db.py` 与 `app/` 包并存 | 低 | 保留历史文件，README 明确入口为 `app.main:app`；后续可清理 | 已复核：不影响运行，但易误导新人 |

## 五、人工修改记录

1. 金额从 `float` 改为 `Decimal`，并统一 `ROUND_HALF_UP`。
2. 挂号、收费事务改为 `BEGIN IMMEDIATE`，库存 FIFO 扣减放在外层事务内。
3. CSV 编码增加 `utf-8-sig → utf-8 → gbk → gb18030` 兜底。
4. 审计从“业务代码零散写日志”改为中间件 + 规则表。
5. 错误提示统一为可操作中文文案（如“库存不足：需要 3，可用 2”）。

## 六、结论

三层测试已落地，关键业务路径有可复现的自动化保护；Code Review 发现的 5 个真实问题均已修复并回归通过。
