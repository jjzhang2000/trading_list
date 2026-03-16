# 股票筛选系统

## 项目概述

本项目是一个基于技术指标的股票筛选系统，主要用于分析上证A股股票，通过多维度技术指标筛选出具有多头趋势的股票，并根据趋势强度进行评分排序。

## 核心功能

- **多指标筛选**：SuperTrend、Vegas通道、布林带、OCC、VP Slope 五个技术指标
- **趋势强度评分**：综合评分系统，量化多头趋势强弱
- **持仓股票管理**：自动加入持仓股票到筛选结果
- **ST股票过滤**：自动过滤名称含ST的股票
- **双界面支持**：命令行(CLI)和图形界面(GUI)

## 项目结构

```
trading_list/
├── trading_list.py       # 股票筛选主程序（命令行）
├── list_gui.py           # 股票筛选主程序（图形界面）
├── shareholding.txt      # 持仓股票列表
├── requirements.txt      # 依赖项文件
├── .gitignore            # Git忽略文件
├── tech/                 # 技术指标模块目录
│   ├── __init__.py       # 模块初始化文件
│   ├── supertrend.py     # SuperTrend指标计算模块
│   ├── vegas.py          # Vegas通道指标计算模块
│   ├── bollingerband.py  # 布林带指标计算模块
│   ├── occross.py        # Open/Close Cross指标计算模块
│   ├── vp_slope.py       # VolumeProfile Slope指标计算模块
│   └── trend_score.py    # 综合趋势强度评分模块
├── data/
│   ├── __init__.py       # 模块初始化文件
│   ├── extract_data.py   # 前复权价格数据获取脚本
│   ├── init_db.py        # 数据库初始化脚本
│   ├── read_data.py      # 数据库读取模块
│   ├── batch_fetch.py    # 批量数据获取模块
│   └── stock_data.db     # 股票数据库
├── utils/
│   ├── __init__.py       # 模块初始化文件
│   └── logger.py         # 日志模块
└── logs/                 # 日志和输出文件目录
    └── listing-*.csv     # 筛选结果CSV文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行图形界面（推荐）

```bash
python list_gui.py
```

### 3. 运行命令行版本

```bash
# 默认跳过数据更新，直接筛选
python trading_list.py

# 更新数据后筛选
python trading_list.py --update

# 指定日期筛选
python trading_list.py -d 2025-03-07

# 完整参数
python trading_list.py -d 2025-03-07 -b 10.0 --update
```

## 筛选流程

```
全部股票
    ↓
过滤ST股票（名称含ST）
    ↓
[1/5] SuperTrend筛选 → 多头趋势
    ↓
[2/5] Vegas通道筛选 → EMA多头排列
    ↓
[3/5] 布林带筛选 → 开口率>阈值 且 收盘价>中轨
    ↓
[4/5] OCC指标筛选 → 多头趋势
    ↓
[5/5] VP Slope筛选 → 斜率>0
    ↓
加入持仓股票（不参与筛选）
    ↓
计算趋势强度评分
    ↓
按评分降序排列，输出CSV
```

## 技术指标详解

### 1. SuperTrend

趋势跟踪指标，基于ATR计算支撑/阻力位。

| 参数 | 默认值 |
|------|--------|
| ATR周期 | 10 |
| ATR乘数 | 3.0 |

**判断规则**：
- trend_direction = 1: 多头
- trend_direction = -1: 空头

### 2. Vegas通道

由6条EMA组成的多层通道系统。

| 通道类型 | EMA周期 |
|----------|---------|
| 短期 | 12, 26 |
| 中期 | 144, 169 |
| 长期 | 576, 676 |

**多头排列条件**：
```
EMA12 > EMA26 > EMA144 > EMA169 > EMA576 > EMA676
```

### 3. 布林带

波动率指标，由中轨和上下轨组成。

| 参数 | 默认值 |
|------|--------|
| 周期 | 21 |
| 标准差倍数 | 2.0 |

**筛选条件**：
- 开口率 > 阈值（默认10%）
- 收盘价 > 中轨

**开口率计算**：
```
开口率 = (上轨 - 下轨) / 中轨 × 100%
```

### 4. OCC (Open/Close Cross)

通过开盘价和收盘价的移动平均交叉判断趋势。

| 参数 | 默认值 |
|------|--------|
| 周期 | 8 |
| MA类型 | TMA（三角移动平均） |

**支持的MA类型**：SMA, EMA, DEMA, TEMA, WMA, VWMA, SSMA, TMA

**判断规则**：
- occ_close > occ_open: 多头
- occ_close < occ_open: 空头

### 5. VP Slope

通过线性回归计算价格趋势斜率。

| 参数 | 默认值 |
|------|--------|
| 长期周期 | 100 |
| 短期周期 | 10 |

**判断规则**：
- slope > 0: 上升趋势
- slope < 0: 下降趋势

## 综合趋势强度评分

### 评分指标

| 指标 | 计算方式 | 权重 |
|------|----------|------|
| SuperTrend | 收盘价高于supertrend线的幅度(%) | 1.0 |
| Vegas通道 | 收盘价高于EMA144的幅度(%) | **2.0** |
| 布林带 | 开口率(%) | 1.0 |
| OCC | occ_close高于occ_open的幅度(%) | 1.0 |
| VP Slope | 长期斜率值 | 1.0 |

### 标准化公式

每个指标标准化到0-10分：

```python
st_score = min(st_above_pct / 10, 10)      # 高于10%得满分
vegas_score = min(vegas_above_pct / 20, 10) # 高于20%得满分
bb_score = min(bandwidth / 10, 10)          # 开口率>10%得满分
occ_score = min(occ_above_pct / 5 * 10, 10) # 高于0.5%得满分
slope_score = min(slope_long * 100, 10)     # 斜率>0.1得满分
```

### 综合评分

```
总分 = (st_score×1 + vegas_score×2 + bb_score×1 + occ_score×1 + slope_score×1) / 6
```

### 强度标签

| 分数范围 | 标签 |
|----------|------|
| 8-10分 | 极强 |
| 6-8分 | 很强 |
| 4-6分 | 较强 |
| 2-4分 | 一般 |
| 0-2分 | 较弱 |

## 持仓股票管理

### 配置文件

在项目根目录创建 `shareholding.txt` 文件，每行一个股票代码：

```
600426
600498
600522
```

### 功能说明

- 持仓股票**不参与筛选**，直接加入结果列表
- 在结果中用 `★` 标记
- CSV文件中名称前加 `*` 号
- 按趋势强度与其他股票一起排序

## 输出结果

### CSV文件

文件名格式：`listing-YYYY-MM-DD_HHMMSS.csv`

输出列：

| 列名 | 说明 |
|------|------|
| rank | 排名 |
| stock_code | 股票代码 |
| stock_name | 股票名称（持仓股票前有*号） |
| strength_score | 综合强度评分 |
| st_score | SuperTrend标准化评分 |
| vegas_score | Vegas标准化评分 |
| bb_score | 布林带标准化评分 |
| occ_score | OCC标准化评分 |
| slope_score | VP Slope标准化评分 |
| st_above_pct | SuperTrend高于线幅度(%) |
| vegas_above_pct | Vegas高于EMA144幅度(%) |
| bandwidth | 布林带开口率(%) |
| occ_above_pct | OCC高于幅度(%) |
| slope_long | VP Slope长期斜率 |
| is_shareholding | 是否持仓股票 |

### 示例输出

```csv
rank,stock_code,stock_name,strength_score,st_score,vegas_score,...
1,600426,*华鲁恒升,7.50,5.00,8.50,...
2,600036,招商银行,6.20,4.00,7.00,...
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-d, --date` | 筛选日期 | 今天 |
| `-b, --bandwidth` | 布林带开口率阈值 | 10.0 |
| `-p, --proxy` | 代理服务器地址 | 无 |
| `--update` | 更新股票数据 | 跳过 |

## 数据来源

- **股票列表**：新浪财经API（上证A股60开头股票）
- **历史K线数据**：新浪财经API
- **复权因子**：新浪财经API
- **前复权价格计算**：前复权价格 = 原始价格 / 后复权因子

## 注意事项

1. **数据完整性**：确保网络连接正常，以便获取最新的股票数据
2. **API限制**：系统会添加适当的延迟，避免触发API频率限制
3. **复权因子更新**：系统会自动检测复权因子变动并重新下载数据
4. **EMA收敛**：Vegas通道的EMA576/676需要足够历史数据才能收敛

## 扩展方向

- 添加更多技术指标
- 实现更复杂的评分算法
- 添加数据可视化功能
- 实现自动交易策略
- 添加回测功能
- 添加风险管理模块

## 许可证

本项目仅供学习和研究使用，不得用于商业用途。
