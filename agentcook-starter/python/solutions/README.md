# 章节参考答案

教程第 23、24 讲让你亲手给 Agent 加工具。先自己写，写完再来这里对照。

| 文件                        | 章节 | 内容                                               |
| --------------------------- | ---- | -------------------------------------------------- |
| `ch23/weather.py`           | 23   | 第一个工具：Mock 天气查询                          |
| `ch24/weather.py`           | 24   | 天气查询接真实 API（和风天气），没配 Key 时用 Mock |
| `ch24/sales_query.py`       | 24   | 只读查询 SQLite 销售库（Agent 不写 SQL）           |
| `ch24/seed_sales_db.py`     | 24   | 生成最近 30 天的测试销售数据                       |
| `ch24/competitor.py`        | 24   | 竞品分析：调第三方爬虫服务                         |
| `ch24/listing_optimizer.py` | 24   | Listing 优化：纯规则引擎，不调外部服务             |
| `ch24/calculator.py`        | 24   | 练习：计算器（安全求值，不用 `eval`）              |

## 怎么用

把文件复制到 `app/tools/`，然后在 `app/main.py` 的工具导入行加上它：

```python
from app.tools import data_query, mock_search, weather  # noqa: F401
```

> 注意：用 `from app.tools import weather`，不要写 `import app.tools.weather`。
> 后者会把 `main.py` 里的变量名 `app` 覆盖成 `app` 包，uvicorn 就找不到 FastAPI 实例了。

也可以不复制，直接从这里导入试用：

```python
from solutions.ch24 import calculator, listing_optimizer  # noqa: F401
```

`sales_query` 需要先生成数据库：

```bash
python -m solutions.ch24.seed_sales_db   # 写入 data/sales.db
```

这些参考答案都有测试：`tests/test_solutions.py`。
