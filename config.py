# 配置文件

# 数据获取配置
DATA_FETCH_CONFIG = {
    'retry_count': 3,  # 数据获取重试次数
    'retry_delay': 2,  # 重试延迟时间（秒）
    'request_delay': 1,  # 请求间隔时间（秒）
    'cache_dir': 'data_cache',  # 数据缓存目录
    'cache_expire': 86400,  # 缓存过期时间（秒）
}

# 股票列表
STOCK_LIST = [
    '600000.SS',  # 浦发银行
    '600519.SS',  # 贵州茅台
    '601318.SS',  # 中国平安
    '601857.SS',  # 中国石油
    '600036.SS',  # 招商银行
    '601288.SS',  # 农业银行
    '601398.SS',  # 工商银行
    '600276.SS',  # 恒瑞医药
    '601668.SS',  # 中国建筑
    '601888.SS',  # 中国中免
]

# 技术指标配置
INDICATOR_CONFIG = {
    'ma_windows': [5, 20, 50],  # 移动平均线窗口
    'rsi_window': 14,  # RSI计算窗口
    'macd_fast': 12,  # MACD快速周期
    'macd_slow': 26,  # MACD慢速周期
    'macd_signal': 9,  # MACD信号周期
}
