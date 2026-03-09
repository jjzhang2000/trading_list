#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperTrend指标计算模块
提供SuperTrend指标计算和筛选功能
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data'))

from data.read_data import get_stock_price_in_range, get_all_stock_codes


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    计算SuperTrend指标
    
    Args:
        df: DataFrame，必须包含列：open, high, low, close
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：supertrend, trend_direction
        
    计算公式：
        1. ATR = Average True Range
        2. 基础上轨 = (最高价 + 最低价) / 2 + multiplier * ATR
        3. 基础下轨 = (最高价 + 最低价) / 2 - multiplier * ATR
        4. 最终上轨和下轨的确定：
           - 如果收盘价突破上轨，使用下轨
           - 如果收盘价突破下轨，使用上轨
        5. SuperTrend值：
           - 多头时为下轨（正值）
           - 空头时为上轨（负值）
        6. trend_direction: 1表示多头，-1表示空头
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> st_df = calculate_supertrend(df)
        >>> print(st_df.tail())
    """
    if df.empty or len(df) < period:
        return pd.DataFrame()
    
    df = df.copy()
    
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    
    df['atr'] = df['tr'].rolling(window=period).mean()
    
    df['hl2'] = (df['high'] + df['low']) / 2
    df['upper_band'] = df['hl2'] + (multiplier * df['atr'])
    df['lower_band'] = df['hl2'] - (multiplier * df['atr'])
    
    df['final_upper'] = 0.0
    df['final_lower'] = 0.0
    df['supertrend'] = 0.0
    df['trend_direction'] = 0
    
    df.loc[df.index[0], 'final_upper'] = df.loc[df.index[0], 'upper_band']
    df.loc[df.index[0], 'final_lower'] = df.loc[df.index[0], 'lower_band']
    df.loc[df.index[0], 'supertrend'] = df.loc[df.index[0], 'final_lower']
    df.loc[df.index[0], 'trend_direction'] = 1
    
    for i in range(1, len(df)):
        curr_idx = df.index[i]
        prev_idx = df.index[i-1]
        
        if df.loc[curr_idx, 'close'] > df.loc[prev_idx, 'final_upper']:
            df.loc[curr_idx, 'final_upper'] = df.loc[curr_idx, 'upper_band']
        else:
            df.loc[curr_idx, 'final_upper'] = min(df.loc[curr_idx, 'upper_band'], 
                                                   df.loc[prev_idx, 'final_upper'])
        
        if df.loc[curr_idx, 'close'] < df.loc[prev_idx, 'final_lower']:
            df.loc[curr_idx, 'final_lower'] = df.loc[curr_idx, 'lower_band']
        else:
            df.loc[curr_idx, 'final_lower'] = max(df.loc[curr_idx, 'lower_band'], 
                                                   df.loc[prev_idx, 'final_lower'])
        
        if df.loc[prev_idx, 'supertrend'] == df.loc[prev_idx, 'final_upper']:
            if df.loc[curr_idx, 'close'] < df.loc[curr_idx, 'final_upper']:
                df.loc[curr_idx, 'supertrend'] = df.loc[curr_idx, 'final_upper']
                df.loc[curr_idx, 'trend_direction'] = -1
            else:
                df.loc[curr_idx, 'supertrend'] = df.loc[curr_idx, 'final_lower']
                df.loc[curr_idx, 'trend_direction'] = 1
        else:
            if df.loc[curr_idx, 'close'] > df.loc[curr_idx, 'final_lower']:
                df.loc[curr_idx, 'supertrend'] = df.loc[curr_idx, 'final_lower']
                df.loc[curr_idx, 'trend_direction'] = 1
            else:
                df.loc[curr_idx, 'supertrend'] = df.loc[curr_idx, 'final_upper']
                df.loc[curr_idx, 'trend_direction'] = -1
    
    result = pd.DataFrame()
    result['date'] = df['date'] if 'date' in df.columns else df.index
    result['supertrend'] = df['supertrend']
    result['trend_direction'] = df['trend_direction']
    
    return result


def get_stock_supertrend(stock_code: str, end_date: str, days: int = 50, 
                         period: int = 10, multiplier: float = 3.0) -> Optional[pd.DataFrame]:
    """
    计算指定股票的SuperTrend值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为50天（需要足够的数据来计算ATR）
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：date, supertrend, trend_direction
        如果数据不足则返回None
    
    Example:
        >>> st_df = get_stock_supertrend('600000', '2025-03-07')
        >>> print(st_df.tail())
    """
    from datetime import datetime, timedelta
    
    end = datetime.strptime(end_date, '%Y-%m-%d')
    start = end - timedelta(days=days + period * 2)
    start_date = start.strftime('%Y-%m-%d')
    
    df = get_stock_price_in_range(stock_code, start_date, end_date)
    
    if df.empty or len(df) < period + 10:
        return None
    
    st_df = calculate_supertrend(df, period, multiplier)
    
    if st_df.empty:
        return None
    
    return st_df


def get_all_stocks_supertrend(date: str, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    计算指定日期所有股票的SuperTrend值
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：stock_code, supertrend, trend_direction
    
    Example:
        >>> st_df = get_all_stocks_supertrend('2025-03-07')
        >>> print(st_df.head())
    """
    codes = get_all_stock_codes()
    results = []
    
    print(f"开始计算 {len(codes)} 只股票的SuperTrend值...")
    
    for i, code in enumerate(codes):
        if (i + 1) % 100 == 0:
            print(f"  处理进度: {i + 1}/{len(codes)}")
        
        st_df = get_stock_supertrend(code, date, days=50, period=period, multiplier=multiplier)
        
        if st_df is not None and not st_df.empty:
            last_row = st_df.iloc[-1]
            results.append({
                'stock_code': code,
                'supertrend': last_row['supertrend'],
                'trend_direction': last_row['trend_direction']
            })
    
    result_df = pd.DataFrame(results)
    
    return result_df


def filter_bullish_stocks(date: str, stock_codes: Optional[List[str]] = None, 
                          period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    筛选指定日期趋势为多头（trend_direction=1）的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表，如果为None则使用所有股票
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：stock_code, supertrend, trend_direction
        只包含trend_direction=1的股票
    
    Example:
        >>> bullish_df = filter_bullish_stocks('2025-03-07')
        >>> print(bullish_df.head())
        
        >>> codes = ['600000', '600004', '600006']
        >>> bullish_df = filter_bullish_stocks('2025-03-07', stock_codes=codes)
        >>> print(bullish_df)
    """
    if stock_codes is None:
        stock_codes = get_all_stock_codes()
    
    results = []
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            print(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        st_df = get_stock_supertrend(code, date, days=50, period=period, multiplier=multiplier)
        
        if st_df is not None and not st_df.empty:
            last_row = st_df.iloc[-1]
            if last_row['trend_direction'] == 1:
                results.append({
                    'stock_code': code,
                    'supertrend': last_row['supertrend'],
                    'trend_direction': last_row['trend_direction']
                })
    
    bullish_df = pd.DataFrame(results)
    
    if not bullish_df.empty:
        bullish_df = bullish_df.sort_values('stock_code').reset_index(drop=True)
    
    return bullish_df


def main():
    """测试函数"""
    print("=" * 70)
    print("测试SuperTrend指标计算模块")
    print("=" * 70)
    
    # 测试1：计算指定股票的SuperTrend值
    print("\n测试1：计算600000的SuperTrend值")
    st_df = get_stock_supertrend('600000', '2025-03-07')
    if st_df is not None and not st_df.empty:
        print(f"  获取到 {len(st_df)} 条SuperTrend数据")
        print("  最近5天的数据:")
        print(st_df.tail())
    else:
        print("  数据不足，无法计算SuperTrend")
    
    # 测试2：计算指定日期所有股票的SuperTrend值（只测试前10只股票）
    print("\n测试2：计算2025-03-07所有股票的SuperTrend值（只测试前10只股票）")
    codes = get_all_stock_codes()[:10]
    results = []
    for code in codes:
        st_df = get_stock_supertrend(code, '2025-03-07')
        if st_df is not None and not st_df.empty:
            last_row = st_df.iloc[-1]
            results.append({
                'stock_code': code,
                'supertrend': last_row['supertrend'],
                'trend_direction': last_row['trend_direction']
            })
    
    result_df = pd.DataFrame(results)
    print(f"  获取到 {len(result_df)} 只股票的SuperTrend数据")
    print(result_df)
    
    # 测试3：筛选多头股票（使用股票列表参数）
    print("\n测试3：筛选2025-03-07趋势为多头的股票（使用股票列表参数）")
    codes = ['600000', '600004', '600006', '600007', '600008', 
             '600009', '600010', '600011', '600012', '600015']
    bullish_df = filter_bullish_stocks('2025-03-07', stock_codes=codes)
    print(f"  找到 {len(bullish_df)} 只多头股票")
    print(bullish_df)
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
