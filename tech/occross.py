#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open/Close Cross (OCC) 指标计算模块
使用pandas-ta库实现OCC指标计算和筛选功能
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data'))

from data.read_data import get_stock_price_in_range


def calculate_occ(df: pd.DataFrame, period: int = 8, ma_type: str = "ema") -> pd.DataFrame:
    """
    计算Open/Close Cross (OCC) 指标
    
    Args:
        df: DataFrame，必须包含列：open, close
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为ema
    
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
    
    ma_type_lower = ma_type.lower()
    
    if ma_type_lower == "ema":
        occ_open = ta.ema(df['open'], length=period)
        occ_close = ta.ema(df['close'], length=period)
    elif ma_type_lower == "sma":
        occ_open = ta.sma(df['open'], length=period)
        occ_close = ta.sma(df['close'], length=period)
    elif ma_type_lower == "wma":
        occ_open = ta.wma(df['open'], length=period)
        occ_close = ta.wma(df['close'], length=period)
    elif ma_type_lower == "dema":
        occ_open = ta.dema(df['open'], length=period)
        occ_close = ta.dema(df['close'], length=period)
    elif ma_type_lower == "tema":
        occ_open = ta.tema(df['open'], length=period)
        occ_close = ta.tema(df['close'], length=period)
    elif ma_type_lower == "tma":
        sma1_open = ta.sma(df['open'], length=period)
        sma1_close = ta.sma(df['close'], length=period)
        occ_open = ta.sma(sma1_open, length=period)
        occ_close = ta.sma(sma1_close, length=period)
    else:
        occ_open = ta.ema(df['open'], length=period)
        occ_close = ta.ema(df['close'], length=period)
    
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
                  period: int = 8, ma_type: str = "ema") -> Optional[pd.DataFrame]:
    """
    计算指定股票的OCC指标值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为50天
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为ema
    
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
                          period: int = 8, ma_type: str = "ema") -> pd.DataFrame:
    """
    筛选指定日期OCC为多头（trend_direction=1）的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
        period: 移动平均周期，默认为8
        ma_type: 移动平均类型，默认为ema
    
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
    print("测试OCC指标计算模块 (pandas-ta)")
    print("=" * 70)
    
    print("\n测试：计算600000的OCC指标值")
    occ_df = get_stock_occ('600000', '2025-03-07')
    if occ_df is not None and not occ_df.empty:
        print(f"  获取到 {len(occ_df)} 条OCC数据")
        print("  最近5天的数据:")
        print(occ_df.tail())
    else:
        print("  数据不足，无法计算OCC指标")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
