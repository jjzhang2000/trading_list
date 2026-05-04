# AGENTS.md - 股票筛选系统开发规范

## 项目概述

基于技术指标的上证A股筛选系统，通过多维度技术指标筛选多头趋势股票，并按趋势强度排序。

## 项目结构

```
trading_list/
├── trading_list.py       # CLI筛选程序
├── list_gui.py           # GUI筛选程序（tkinter）
├── tech/                 # 技术指标模块
│   ├── supertrend.py     # SuperTrend指标
│   ├── vegas.py          # Vegas通道
│   ├── bollingerband.py  # 布林带
│   ├── occross.py        # OCC指标
│   ├── vp_slope.py       # VP斜率
│   └── trend_score.py    # 趋势评分（ST-Slope截面排序）
├── data/                 # 数据模块
│   ├── extract_data.py   # 新浪API数据获取
│   ├── init_db.py        # 数据库初始化
│   ├── read_data.py      # 数据库读取
│   └── batch_fetch.py    # 批量数据更新
└── utils/
    └── logger.py         # 日志模块
```

## 运行命令

```bash
# GUI（推荐）
python list_gui.py

# CLI
python trading_list.py

# 指定日期
python trading_list.py -d 2025-03-07

# 更新数据
python trading_list.py --update
```

## 数据库操作

```bash
# 初始化数据库
python -c "from data.init_db import init_db; init_db()"

# 提取数据
python -c "from data.extract_data import main; main()"

# 查看数据
sqlite3 data/stock_data.db ".tables"
sqlite3 data/stock_data.db "SELECT * FROM stock_daily LIMIT 10"
```

## 代码规范

### 通用规范

- Python 3.8+
- 文件头：`# -*- coding: utf-8 -*-`
- 模块、函数使用docstring
- 中文注释用于业务逻辑

### 导入顺序

标准库 → 第三方库（pandas, numpy, pandas_ta）→ 本地模块

使用 `sys.path.insert(0, ...)` 处理跨模块导入。

### 命名规范

| 类型 | 规范 | 示例 |
| --- | --- | --- |
| 函数 | snake_case | `calculate_supertrend` |
| 变量 | snake_case | `stock_code` |
| 常量 | UPPER_CASE | `DB_PATH` |
| 类 | PascalCase | `StockFilterGUI` |
| 私有方法 | `_前缀` | `_init_session` |

### 类型注解

函数参数和返回值使用类型注解。

```python
def get_stock_supertrend(stock_code: str, end_date: str, days: int = 50) -> Optional[pd.DataFrame]:
```

### 异常处理

外部API和文件操作用 `try/except`，日志用 `logger.warning()`，失败返回 `None` 或空DataFrame。

### 日志

模块级logger：`logger = get_logger(__name__)`
- `info` 记录进度
- `warning` 记录可恢复问题
- `error` 记录失败

### DataFrame操作

- 总是 `df = df.copy()`
- 使用pandas-ta计算技术指标

## 配置文件

无外部配置文件，使用模块级常量：
- 数据库路径：`data/stock_data.db`
- CSV输出：`logs/` 目录

## 依赖

- `pandas` - 数据处理
- `numpy` - 数值计算
- `pandas-ta` - 技术指标
- `akshare` - 中文股票API
- `python-dotenv` - 环境变量

## 重要说明

1. **数据源**：新浪财经API（上证A股60开头）
2. **数据库**：SQLite，5年历史数据
3. **频率限制**：请求间隔0.3秒
4. **无单元测试**：依赖手动测试

### ST-Slope截面排序

评分公式：`composite = zscore(st_above_pct) - zscore(slope_60d)`

- `st_above_pct`：收盘价高于ST线的百分比（正向贡献）
- `slope_60d`：60日对数价格线性回归斜率（惩罚过度延伸）
- `st_above_pct` 越大 → 排名越高
- `slope_60d` 越大 → 排名越低（过度延伸）

### VP Slope筛选阈值

`(slope_long / close) > 0.005`（日均涨幅>0.5%）
