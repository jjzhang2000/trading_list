# 股票分析项目

## 项目概述

本项目是一个基于历史数据的股票分析系统，主要用于分析上证A股股票并进行排名，帮助投资者发现潜在的投资机会。项目从新浪财经获取历史前复权价格数据，并结合多种技术指标进行分析和筛选。

## 项目结构

```
trading_list/
├── trading_list.py       # 股票筛选主程序（命令行）
├── list_gui.py           # 股票筛选主程序（图形界面）
├── requirements.txt      # 依赖项文件
├── .gitignore            # Git忽略文件
├── tech/                 # 技术指标模块目录
│   ├── __init__.py       # 模块初始化文件
│   ├── supertrend.py     # SuperTrend指标计算模块
│   ├── vegas.py          # Vegas通道指标计算模块
│   ├── bollingerband.py  # 布林带指标计算模块
│   ├── occross.py        # Open/Close Cross指标计算模块
│   └── vp_slope.py       # VolumeProfile Slope指标计算模块
└── data/
    ├── extract_data.py    # 前复权价格数据获取脚本
    ├── init_db.py         # 数据库初始化脚本
    ├── read_data.py       # 数据库读取模块
    └── stock_data.db      # 股票数据库
```

## 文件功能说明

### 1. trading_list.py

**功能**：股票筛选主程序，整合所有技术指标模块进行股票筛选。

- **核心函数**：
  - `update_stock_data()`: 更新股票数据
  - `run_filter()`: 执行完整的股票筛选流程
  - `filter_by_supertrend()`: SuperTrend筛选
  - `filter_by_vegas()`: Vegas通道筛选
  - `filter_by_bollingerband()`: 布林带筛选
  - `filter_by_occross()`: OCC指标筛选
  - `filter_by_vp_slope()`: VP Slope筛选

- **筛选流程**：
  1. 更新股票数据（可选跳过）
  2. SuperTrend筛选 → 多头趋势
  3. Vegas通道筛选 → EMA多头排列
  4. 布林带筛选 → 开口率超过阈值
  5. OCC指标筛选 → 多头趋势
  6. VP Slope筛选 → 斜率大于0

- **命令行参数**：
  - `-d, --date`: 筛选日期（默认今天）
  - `-b, --bandwidth`: 布林带开口率阈值（默认10.0）
  - `-p, --proxy`: 代理服务器地址
  - `--skip-update`: 跳过数据更新步骤

### 2. list_gui.py

**功能**：股票筛选图形界面程序，提供可视化的操作界面。

- **界面布局**：
  - **上部**：数据操作区
    - 初始化数据库按钮：运行init_db，显示成功与否
    - 提取数据按钮：运行extract_data，显示提取结果
    - 运行结果文本框：显示操作日志
  - **中部**：筛选器设置区
    - 5个筛选器开关：SuperTrend、Vegas通道、布林带、OCC、VP Slope
    - 开始筛选按钮
  - **下部**：股票列表区
    - 左侧列表：显示提取数据后的所有股票
    - 右侧列表：显示筛选后的股票结果

- **使用方法**：
  ```bash
  python list_gui.py
  ```

### 3. supertrend.py (位于 tech/ 目录)

**功能**：SuperTrend指标计算模块，用于趋势判断和股票筛选。

- **核心函数**：
  - `calculate_supertrend()`: 计算SuperTrend指标
  - `get_stock_supertrend()`: 获取指定股票的SuperTrend值
  - `get_all_stocks_supertrend()`: 获取所有股票的SuperTrend值
  - `filter_bullish_stocks()`: 筛选多头趋势股票

- **计算参数**：
  - ATR周期：默认10
  - ATR乘数：默认3.0

- **趋势判断**：
  - trend_direction = 1: 多头
  - trend_direction = -1: 空头

### 4. vegas.py (位于 tech/ 目录)

**功能**：Vegas通道指标计算模块，用于长期趋势判断。

- **核心函数**：
  - `calculate_vegas()`: 计算Vegas通道指标
  - `get_stock_vegas()`: 获取指定股票的Vegas通道值
  - `filter_bullish_stocks()`: 筛选多头趋势股票

- **通道组成**：
  - 超短期通道：EMA 5, EMA 8
  - 短期通道：EMA 12, EMA 26
  - 长期通道：EMA 144, EMA 169

- **趋势判断**：
  - 多头：EMA5 > EMA8 > EMA12 > EMA26 > EMA144 > EMA169
  - 空头：EMA5 < EMA8 < EMA12 < EMA26 < EMA144 < EMA169

### 5. bollingerband.py (位于 tech/ 目录)

**功能**：布林带指标计算模块，用于波动率分析和股票筛选。

- **核心函数**：
  - `calculate_bollinger_band()`: 计算布林带指标
  - `get_stock_bollinger_band()`: 获取指定股票的布林带值
  - `filter_stocks_by_bandwidth()`: 筛选开口率超过阈值的股票

- **计算参数**：
  - 移动平均周期：默认20
  - 标准差倍数：默认2.0

- **开口率计算**：
  - 开口率 = (上轨 - 下轨) / 中轨 × 100%
  - 开口率越大，表示股价波动越大

### 6. occross.py (位于 tech/ 目录)

**功能**：Open/Close Cross (OCC) 指标计算模块，用于趋势判断。

- **核心函数**：
  - `calculate_occ()`: 计算OCC指标
  - `get_stock_occ()`: 获取指定股票的OCC值
  - `filter_bullish_stocks()`: 筛选多头趋势股票

- **支持移动平均类型**：
  - SMA: 简单移动平均
  - EMA: 指数移动平均
  - DEMA: 双指数移动平均
  - TEMA: 三指数移动平均
  - WMA: 加权移动平均
  - VWMA: 成交量加权移动平均
  - SSMA: 超级平滑移动平均
  - TMA: 三角移动平均（默认）

- **趋势判断**：
  - 多头：occ_close > occ_open
  - 空头：occ_close < occ_open

### 7. vp_slope.py (位于 tech/ 目录)

**功能**：VolumeProfile Slope指标计算模块，用于趋势强度分析。

- **核心函数**：
  - `calculate_linreg_slope()`: 计算线性回归斜率
  - `calculate_slope()`: 计算Slope指标
  - `get_stock_slope()`: 获取指定股票的斜率值
  - `filter_stocks_by_slope()`: 筛选斜率大于0的股票

- **计算参数**：
  - 长期周期：默认100
  - 短期周期：默认10

- **斜率意义**：
  - slope > 0: 上升趋势
  - slope < 0: 下降趋势
  - slope = 0: 横盘整理

### 8. extract_data.py (位于 data/ 目录)

**功能**：从新浪财经获取前复权价格数据并存储到数据库。

- **数据获取**：
  - 从新浪财经API获取股票列表（上证A股60开头）
  - 从新浪财经API获取不复权的原始K线数据
  - 从新浪财经API获取后复权因子
  - 计算前复权价格：前复权价格 = 原始价格 / 后复权因子

- **增量更新**：
  - 检测复权因子变动
  - 当复权因子变动时重新下载所有历史数据
  - 否则只下载最新数据

- **数据存储**：
  - 存储前复权价格数据到SQLite数据库
  - 记录股票基本信息和数据时间范围

- **数据库字段**：
  - stock_code: 股票代码
  - date: 日期
  - open: 前复权开盘价
  - high: 前复权最高价
  - low: 前复权最低价
  - close: 前复权收盘价
  - volume: 成交量

### 9. init_db.py (位于 data/ 目录)

**功能**：初始化数据库，清除历史数据或创建新数据库。

- **数据库检查**：
  - 检查数据库是否存在
  - 如果存在，清除其中的所有历史数据
  - 如果不存在，创建新数据库

- **表结构创建**：
  - 创建股票日线数据表（stock_daily）
  - 创建股票信息表（stock_info）
  - 创建索引以提高查询效率

### 10. read_data.py (位于 data/ 目录)

**功能**：数据库读取模块，提供数据查询功能。

- **核心函数**：
  - `get_stock_price_on_date()`: 获取指定股票在指定日期的价格和交易量
  - `get_all_stocks_price_on_date()`: 获取所有股票在指定日期的价格和交易量
  - `get_stock_price_in_range()`: 获取指定股票在日期范围内的价格和交易量
  - `calculate_heikin_ashi()`: 计算Heikin-Ashi平均K线
  - `get_all_stock_codes()`: 获取所有股票代码列表

## 依赖项

项目依赖以下Python库：

- pandas
- numpy
- requests

可以通过以下命令安装依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

1. **运行股票筛选主程序**（推荐）：
   ```bash
   # 默认：更新数据后筛选今天的股票
   python trading_list.py
   
   # 指定日期筛选
   python trading_list.py -d 2025-03-07
   
   # 使用代理更新数据
   python trading_list.py -p http://127.0.0.1:7890
   
   # 跳过数据更新，直接筛选
   python trading_list.py --skip-update
   
   # 完整参数示例
   python trading_list.py -d 2025-03-07 -b 15.0 -p http://127.0.0.1:7890
   ```

2. **运行图形界面程序**（推荐）：
   ```bash
   python list_gui.py
   ```
   
   图形界面提供：
   - 初始化数据库按钮
   - 提取数据按钮
   - 5个筛选器开关
   - 股票列表显示

3. **初始化数据库**：
   ```bash
   python data/init_db.py
   ```

4. **提取历史数据**：
   ```bash
   python data/extract_data.py
   ```
   
   可选参数：
   ```bash
   python data/extract_data.py --proxy http://127.0.0.1:7890  # 使用代理
   ```

5. **使用技术指标模块**：

   **SuperTrend指标**：
   ```python
   from tech.supertrend import get_stock_supertrend, filter_bullish_stocks
   
   # 计算单只股票
   st_df = get_stock_supertrend('600000', '2025-03-07')
   
   # 筛选多头股票
   codes = ['600000', '600004', '600006']
   bullish_df = filter_bullish_stocks('2025-03-07', stock_codes=codes)
   ```

   **Vegas通道**：
   ```python
   from tech.vegas import get_stock_vegas, filter_bullish_stocks
   
   # 计算单只股票
   vegas_df = get_stock_vegas('600000', '2025-03-07')
   
   # 筛选多头股票
   codes = ['600000', '600004', '600006']
   bullish_df = filter_bullish_stocks('2025-03-07', codes)
   ```

   **布林带**：
   ```python
   from tech.bollingerband import get_stock_bollinger_band, filter_stocks_by_bandwidth
   
   # 计算单只股票
   bb_df = get_stock_bollinger_band('600000', '2025-03-07')
   
   # 筛选开口率超过10%的股票
   codes = ['600000', '600004', '600006']
   result_df = filter_stocks_by_bandwidth('2025-03-07', codes, threshold=10.0)
   ```

   **OCC指标**：
   ```python
   from tech.occross import get_stock_occ, filter_bullish_stocks
   
   # 计算单只股票（使用默认TMA）
   occ_df = get_stock_occ('600000', '2025-03-07')
   
   # 使用EMA计算
   occ_df = get_stock_occ('600000', '2025-03-07', ma_type='EMA')
   
   # 筛选多头股票
   codes = ['600000', '600004', '600006']
   bullish_df = filter_bullish_stocks('2025-03-07', codes)
   ```

   **Slope指标**：
   ```python
   from tech.vp_slope import get_stock_slope, filter_stocks_by_slope
   
   # 计算单只股票
   slope_df = get_stock_slope('600000', '2025-03-07')
   
   # 筛选斜率大于0的股票
   codes = ['600000', '600004', '600006']
   result_df = filter_stocks_by_slope('2025-03-07', codes)
   ```

6. **读取数据库**：
   ```python
   from data.read_data import get_stock_price_on_date, get_all_stocks_price_on_date
   
   # 获取指定股票的价格
   open_price, high_price, low_price, close_price, volume = get_stock_price_on_date('600000', '2025-03-07')
   
   # 获取所有股票的价格
   df = get_all_stocks_price_on_date('2025-03-07')
   
   # 获取所有股票代码
   from data.read_data import get_all_stock_codes
   codes = get_all_stock_codes()
   ```

## 数据来源

- **股票列表**：新浪财经API（上证A股60开头股票）
- **历史K线数据**：新浪财经API（不复权原始价格）
- **复权因子**：新浪财经API（后复权因子）
- **前复权价格计算**：前复权价格 = 原始价格 / 后复权因子

## 前复权价格说明

### 什么是前复权？

前复权是指以当前价格为基准，对历史价格进行调整，使得历史价格与当前价格具有可比性。前复权价格考虑了分红、送股、配股等因素对价格的影响。

### 计算方法

本项目使用新浪财经提供的后复权因子来计算前复权价格：

```
前复权价格 = 原始价格 / 后复权因子
```

### 示例

以浦发银行（600000）为例，2025-07-16为除权日：

- 2025-07-15：
  - 原始收盘价：13.930元
  - 后复权因子：1.030325
  - 前复权收盘价：13.930 / 1.030325 = 13.520元

- 2025-07-16（除权日）：
  - 原始收盘价：13.480元
  - 后复权因子：1.0
  - 前复权收盘价：13.480 / 1.0 = 13.480元

## 技术指标说明

### SuperTrend

SuperTrend是一种趋势跟踪指标，基于ATR（平均真实波幅）计算。它通过动态调整支撑/阻力位来识别趋势方向。

### Vegas通道

Vegas通道由多条EMA组成，通过不同周期的EMA排列来判断趋势。当所有EMA从上到下依次排列时为多头趋势，反之为空头趋势。

### 布林带

布林带由中轨（移动平均线）和上下轨（中轨±N倍标准差）组成。开口率反映了股价的波动程度，开口率扩大通常预示着趋势的开始。

### Open/Close Cross (OCC)

OCC指标通过比较开盘价和收盘价的移动平均线来判断趋势。当收盘价的MA高于开盘价的MA时为多头趋势。

### VolumeProfile Slope

Slope指标通过线性回归计算价格趋势的斜率。斜率大于0表示上升趋势，小于0表示下降趋势。

## 注意事项

1. **数据完整性**：
   - 系统会自动处理API返回的数据格式异常
   - 确保网络连接正常，以便获取最新的股票数据

2. **API限制**：
   - 系统会添加适当的延迟，避免触发API频率限制
   - 新浪财经API稳定可靠，适合批量获取数据

3. **复权因子更新**：
   - 系统会自动检测复权因子变动
   - 当复权因子变动时，会重新下载所有历史数据

4. **技术指标使用**：
   - 不同指标适用于不同的市场环境
   - 建议结合多个指标进行综合分析
   - 注意指标的滞后性和假信号

## 项目扩展

- 可以添加更多技术指标
- 可以实现更复杂的评分算法
- 可以添加数据可视化功能
- 可以实现自动交易策略
- 可以添加回测功能
- 可以添加风险管理模块

## 许可证

本项目仅供学习和研究使用，不得用于商业用途。
