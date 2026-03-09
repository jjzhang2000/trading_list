#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open/Close Cross (OCC) 指标计算模块
提供OCC指标计算和筛选功能
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data'))

from data.read_data import get_stock_price_in_range


def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return data.rolling(window=period).mean()


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return data.ewm(span=period, adjust=False).mean()


def calculate_dema(data: pd.Series, period: int) -> pd.Series:
    """双指数移动平均"""
    ema1 = calculate_ema(data, period)
    ema2 = calculate_ema(ema1, period)
    return 2 * ema1 - ema2


def calculate_tema(data: pd.Series, period: int) -> pd.Series:
    """三指数移动平均"""
    ema1 = calculate_ema(data, period)
    ema2 = calculate_ema(ema1, period)
    ema3 = calculate_ema(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3


def calculate_wma(data: pd.Series, period: int) -> pd.Series:
    """加权移动平均"""
    weights = np.arange(1, period + 1)
    return data.rolling(window=period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def calculate_vwma(data: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    """成交量加权移动平均"""
    return (data * volume).rolling(window=period).sum() / volume.rolling(window=period).sum()


def calculate_ssma(data: pd.Series, period: int) -> pd.Series:
    """超级平滑移动平均"""
    ssma = data.copy()
    for i in range(1, len(data)):
        if i < period:
            ssma.iloc[i] = data.iloc[:i+1].mean()
        else:
            ssma.iloc[i] = (ssma.iloc[i-1] * (period - 1) + data.iloc[i]) / period
    return ssma


def calculate_tma(data: pd.Series, period: int) -> pd.Series:
    """三角移动平均"""
    sma1 = calculate_sma(data, period)
    return calculate_sma(sma1, period)


def calculate_ma(data: pd.Series, period: int, ma_type: str = "TMA", volume: pd.Series = None) -> pd.Series:
    """
    计算移动平均线
    
    Args:
        data: 数据序列
        period: 周期
        ma_type: 移动平均类型，可选：SMA, EMA, DEMA, TEMA, WMA, VWMA, SSMA, TMA
        volume: 成交量序列（仅VWMA需要）
    
    Returns:
        移动平均序列
    """
    ma_type = ma_type.upper()
    
    if ma_type == "SMA":
        return calculate_sma(data, period)
    elif ma_type == "EMA":
        return calculate_ema(data, period)
    elif ma_type == "DEMA":
        return calculate_dema(data, period)
    elif ma_type == "TEMA":
        return calculate_tema(data, period)
    elif ma_type == "WMA":
        return calculate_wma(data, period)
    elif ma_type == "VWMA":
        if volume is None:
            raise ValueError("VWMA需要提供volume参数")
        return calculate_vwma(data, volume, period)
    elif ma_type == "SSMA":
        return calculate_ssma(data, period)
    elif ma_type == "TMA":
        return calculate_tma(data, period)
    else:
        raise ValueError(f"不支持的MA类型: {ma_type}")


def calculate_occ(df: pd.DataFrame, period: int = 8, ma_type: str = "TMA") -> pd.DataFrame:
    """
    计算Open/Close Cross (OCC) 指标
    
    Args:
        df: DataFrame，必须包含列：open, close, volume（如果使用VWMA）
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为TMA
    
    Returns:
        DataFrame，包含列：occ_open, occ_close, trend_direction
        
    计算逻辑：
        occ_open = ma(open, period, ma_type)
        occ_close = ma(close, period, ma_type)
        trend_direction = 1 (多头) 如果 occ_close > occ_open
                        = -1 (空头) 如果 occ_close < occ_open
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> occ_df = calculate_occ(df)
        >>> print(occ_df.tail())
    """
    if df.empty or len(df) < period:
        return pd.DataFrame()
    
    df = df.copy()
    
    if ma_type == "VWMA":
        occ_open = calculate_ma(df['open'], period, ma_type, df['volume'])
        occ_close = calculate_ma(df['close'], period, ma_type, df['volume'])
    else:
        occ_open = calculate_ma(df['open'], period, ma_type)
        occ_close = calculate_ma(df['close'], period, ma_type)
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    result['occ_open'] = occ_open
    result['occ_close'] = occ_close
    
    result['trend_direction'] = 0
    result.loc[result['occ_close'] > result['occ_open'], 'trend_direction'] = 1
    result.loc[result['occ_close'] < result['occ_open'], 'trend_direction'] = -1
    
    return result


def get_stock_occ(stock_code: str, end_date: str, days: int = 50, 
                  period: int = 8, ma_type: str = "TMA") -> Optional[pd.DataFrame]:
    """
    计算指定股票的OCC指标值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为50天
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为TMA
    
    Returns:
        DataFrame，包含列：date, occ_open, occ_close, trend_direction
        如果数据不足则返回None
    
    Example:
        >>> occ_df = get_stock_occ('600000', '2025-03-07')
        >>> print(occ_df.tail())
    """
    from datetime import datetime, timedelta
    
    end = datetime.strptime(end_date, '%Y-%m-%d')
    start = end - timedelta(days=days + period)
    start_date = start.strftime('%Y-%m-%d')
    
    df = get_stock_price_in_range(stock_code, start_date, end_date)
    
    if df.empty or len(df) < period:
        return None
    
    occ_df = calculate_occ(df, period, ma_type)
    
    if occ_df.empty:
        return None
    
    return occ_df


def filter_bullish_stocks(date: str, stock_codes: List[str], 
                          period: int = 8, ma_type: str = "TMA") -> pd.DataFrame:
    """
    筛选指定日期OCC为多头（trend_direction=1）的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为TMA
    
    Returns:
        DataFrame，包含列：stock_code, occ_open, occ_close, trend_direction
        只包含trend_direction=1的股票
    
    Example:
        >>> codes = ['600000', '600004', '600006']
        >>> bullish_df = filter_bullish_stocks('2025-03-07', codes)
        >>> print(bullish_df)
    """
    results = []
    
    print(f"开始计算 {len(stock_codes)} 只股票的OCC指标...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            print(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        occ_df = get_stock_occ(code, date, days=50, period=period, ma_type=ma_type)
        
        if occ_df is not None and not occ_df.empty:
            last_row = occ_df.iloc[-1]
            if last_row['trend_direction'] == 1:
                results.append({
                    'stock_code': code,
                    'occ_open': last_row['occ_open'],
                    'occ_close': last_row['occ_close'],
                    'trend_direction': last_row['trend_direction']
                })
    
    bullish_df = pd.DataFrame(results)
    
    if not bullish_df.empty:
        bullish_df = bullish_df.sort_values('stock_code').reset_index(drop=True)
    
    return bullish_df


def main():
    """测试函数"""
    print("=" * 70)
    print("测试OCC指标计算模块")
    print("=" * 70)
    
    # 测试1：计算指定股票的OCC指标值
    print("\n测试1：计算600000的OCC指标值")
    occ_df = get_stock_occ('600000', '2025-03-07')
    if occ_df is not None and not occ_df.empty:
        print(f"  获取到 {len(occ_df)} 条OCC数据")
        print("  最近5天的数据:")
        print(occ_df.tail())
    else:
        print("  数据不足，无法计算OCC指标")
    
    # 测试2：筛选多头股票
    print("\n测试2：筛选2025-03-07趋势为多头的股票")
    codes = ['600000', '600004', '600006', '600007', '600008', 
             '600009', '600010', '600011', '600012', '600015']
    bullish_df = filter_bullish_stocks('2025-03-07', codes)
    print(f"  找到 {len(bullish_df)} 只多头股票")
    print(bullish_df)
    
    # 测试3：使用不同的MA类型
    print("\n测试3：使用EMA计算OCC指标")
    occ_df_ema = get_stock_occ('600000', '2025-03-07', ma_type='EMA')
    if occ_df_ema is not None and not occ_df_ema.empty:
        print("  最近5天的数据（EMA）:")
        print(occ_df_ema.tail())
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
