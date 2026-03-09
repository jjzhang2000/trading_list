#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vegas通道指标计算模块
提供Vegas通道计算和筛选功能
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data'))

from data.read_data import get_stock_price_in_range


def calculate_vegas(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算Vegas通道指标
    
    Args:
        df: DataFrame，必须包含列：close
    
    Returns:
        DataFrame，包含列：ema5, ema8, ema12, ema26, ema144, ema169, trend_direction
        
    Vegas通道组成：
        - 超短期通道：EMA 5, EMA 8
        - 短期通道：EMA 12, EMA 26
        - 长期通道：EMA 144, EMA 169
        
    趋势判断：
        - trend_direction = 1: 多头（EMA5 > EMA8 > EMA12 > EMA26 > EMA144 > EMA169）
        - trend_direction = -1: 空头（EMA5 < EMA8 < EMA12 < EMA26 < EMA144 < EMA169）
        - trend_direction = 0: 震荡（其他情况）
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> vegas_df = calculate_vegas(df)
        >>> print(vegas_df.tail())
    """
    if df.empty or len(df) < 169:
        return pd.DataFrame()
    
    df = df.copy()
    
    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['ema144'] = df['close'].ewm(span=144, adjust=False).mean()
    df['ema169'] = df['close'].ewm(span=169, adjust=False).mean()
    
    df['trend_direction'] = 0
    
    bullish_mask = (
        (df['ema5'] > df['ema8']) &
        (df['ema8'] > df['ema12']) &
        (df['ema12'] > df['ema26']) &
        (df['ema26'] > df['ema144']) &
        (df['ema144'] > df['ema169'])
    )
    
    bearish_mask = (
        (df['ema5'] < df['ema8']) &
        (df['ema8'] < df['ema12']) &
        (df['ema12'] < df['ema26']) &
        (df['ema26'] < df['ema144']) &
        (df['ema144'] < df['ema169'])
    )
    
    df.loc[bullish_mask, 'trend_direction'] = 1
    df.loc[bearish_mask, 'trend_direction'] = -1
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    result['ema5'] = df['ema5']
    result['ema8'] = df['ema8']
    result['ema12'] = df['ema12']
    result['ema26'] = df['ema26']
    result['ema144'] = df['ema144']
    result['ema169'] = df['ema169']
    result['trend_direction'] = df['trend_direction']
    
    return result


def get_stock_vegas(stock_code: str, end_date: str, days: int = 200) -> Optional[pd.DataFrame]:
    """
    计算指定股票的Vegas通道值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为200天（需要足够的数据来计算EMA169）
    
    Returns:
        DataFrame，包含列：date, ema5, ema8, ema12, ema26, ema144, ema169, trend_direction
        如果数据不足则返回None
    
    Example:
        >>> vegas_df = get_stock_vegas('600000', '2025-03-07')
        >>> print(vegas_df.tail())
    """
    from datetime import datetime, timedelta
    
    end = datetime.strptime(end_date, '%Y-%m-%d')
    start = end - timedelta(days=days + 200)
    start_date = start.strftime('%Y-%m-%d')
    
    df = get_stock_price_in_range(stock_code, start_date, end_date)
    
    if df.empty or len(df) < 169:
        return None
    
    vegas_df = calculate_vegas(df)
    
    if vegas_df.empty:
        return None
    
    return vegas_df


def filter_bullish_stocks(date: str, stock_codes: List[str]) -> pd.DataFrame:
    """
    筛选指定日期Vegas通道为多头（trend_direction=1）的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
    
    Returns:
        DataFrame，包含列：stock_code, ema5, ema8, ema12, ema26, ema144, ema169, trend_direction
        只包含trend_direction=1的股票
    
    Example:
        >>> codes = ['600000', '600004', '600006']
        >>> bullish_df = filter_bullish_stocks('2025-03-07', codes)
        >>> print(bullish_df)
    """
    results = []
    
    print(f"开始计算 {len(stock_codes)} 只股票的Vegas通道...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            print(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        vegas_df = get_stock_vegas(code, date, days=200)
        
        if vegas_df is not None and not vegas_df.empty:
            last_row = vegas_df.iloc[-1]
            if last_row['trend_direction'] == 1:
                results.append({
                    'stock_code': code,
                    'ema5': last_row['ema5'],
                    'ema8': last_row['ema8'],
                    'ema12': last_row['ema12'],
                    'ema26': last_row['ema26'],
                    'ema144': last_row['ema144'],
                    'ema169': last_row['ema169'],
                    'trend_direction': last_row['trend_direction']
                })
    
    bullish_df = pd.DataFrame(results)
    
    if not bullish_df.empty:
        bullish_df = bullish_df.sort_values('stock_code').reset_index(drop=True)
    
    return bullish_df


def main():
    """测试函数"""
    print("=" * 70)
    print("测试Vegas通道指标计算模块")
    print("=" * 70)
    
    # 测试1：计算指定股票的Vegas通道值
    print("\n测试1：计算600000的Vegas通道值")
    vegas_df = get_stock_vegas('600000', '2025-03-07')
    if vegas_df is not None and not vegas_df.empty:
        print(f"  获取到 {len(vegas_df)} 条Vegas通道数据")
        print("  最近5天的数据:")
        print(vegas_df.tail())
    else:
        print("  数据不足，无法计算Vegas通道")
    
    # 测试2：筛选多头股票
    print("\n测试2：筛选2025-03-07趋势为多头的股票")
    codes = ['600000', '600004', '600006', '600007', '600008', 
             '600009', '600010', '600011', '600012', '600015']
    bullish_df = filter_bullish_stocks('2025-03-07', codes)
    print(f"  找到 {len(bullish_df)} 只多头股票")
    print(bullish_df)
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
