#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带指标计算模块
使用pandas-ta库实现布林带计算和筛选功能
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data'))

from data.read_data import get_stock_price_before_date


def calculate_bollinger_band(df: pd.DataFrame, period: int = 21, std_dev: float = 2.0) -> pd.DataFrame:
    """
    计算布林带指标
    
    Args:
        df: DataFrame，必须包含列：close
        period: 移动平均周期，默认为21
        std_dev: 标准差倍数，默认为2.0
    
    Returns:
        DataFrame，包含列：middle_band, upper_band, lower_band, bandwidth
        
    使用pandas-ta的bbands函数计算：
        - 中轨 = 移动平均线（MA）
        - 上轨 = 中轨 + N × 标准差
        - 下轨 = 中轨 - N × 标准差
        - 开口率 = (上轨 - 下轨) / 中轨 × 100%
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> bb_df = calculate_bollinger_band(df)
        >>> print(bb_df.tail())
    """
    if df.empty or len(df) < period:
        return pd.DataFrame()
    
    df = df.copy()
    
    bb_df = ta.bbands(df['close'], length=period, std=std_dev)
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    
    bbm_col = [col for col in bb_df.columns if col.startswith('BBM_')][0]
    bbu_col = [col for col in bb_df.columns if col.startswith('BBU_')][0]
    bbl_col = [col for col in bb_df.columns if col.startswith('BBL_')][0]
    bbb_col = [col for col in bb_df.columns if col.startswith('BBB_')][0]
    
    result['middle_band'] = bb_df[bbm_col]
    result['upper_band'] = bb_df[bbu_col]
    result['lower_band'] = bb_df[bbl_col]
    result['bandwidth'] = bb_df[bbb_col]
    
    return result


def get_stock_bollinger_band(stock_code: str, end_date: str, days: int = 50, 
                             period: int = 21, std_dev: float = 2.0) -> Optional[pd.DataFrame]:
    """
    计算指定股票的布林带值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为50天
        period: 移动平均周期，默认为21
        std_dev: 标准差倍数，默认为2.0
    
    Returns:
        DataFrame，包含列：date, middle_band, upper_band, lower_band, bandwidth
        如果数据不足则返回None
    
    Example:
        >>> bb_df = get_stock_bollinger_band('600000', '2025-03-07')
        >>> print(bb_df.tail())
    """
    MIN_DATA_BUFFER = 10
    min_required = days + period + MIN_DATA_BUFFER
    
    df = get_stock_price_before_date(stock_code, end_date, limit=min_required)
    
    if df.empty or len(df) < period + MIN_DATA_BUFFER:
        return None
    
    bb_df = calculate_bollinger_band(df, period, std_dev)
    
    if bb_df.empty:
        return None
    
    return bb_df.tail(days)


def filter_stocks_by_bandwidth(date: str, stock_codes: List[str], threshold: float,
                               period: int = 21, std_dev: float = 2.0) -> pd.DataFrame:
    """
    筛选指定日期布林带开口率超过阈值的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
        threshold: 开口率阈值（百分比）
        period: 移动平均周期，默认为21
        std_dev: 标准差倍数，默认为2.0
    
    Returns:
        DataFrame，包含列：stock_code, middle_band, upper_band, lower_band, bandwidth
        只包含bandwidth > threshold的股票，按bandwidth降序排列
    
    Example:
        >>> codes = ['600000', '600004', '600006']
        >>> result_df = filter_stocks_by_bandwidth('2025-03-07', codes, threshold=10.0)
        >>> print(result_df)
    """
    results = []
    
    print(f"开始计算 {len(stock_codes)} 只股票的布林带...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            print(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        bb_df = get_stock_bollinger_band(code, date, days=50, period=period, std_dev=std_dev)
        
        if bb_df is not None and not bb_df.empty:
            last_row = bb_df.iloc[-1]
            if pd.notna(last_row['bandwidth']) and last_row['bandwidth'] > threshold:
                results.append({
                    'stock_code': code,
                    'middle_band': last_row['middle_band'],
                    'upper_band': last_row['upper_band'],
                    'lower_band': last_row['lower_band'],
                    'bandwidth': last_row['bandwidth']
                })
    
    result_df = pd.DataFrame(results)
    
    if not result_df.empty:
        result_df = result_df.sort_values('bandwidth', ascending=False).reset_index(drop=True)
    
    return result_df


def main():
    """测试函数"""
    print("=" * 70)
    print("测试布林带指标计算模块 (pandas-ta)")
    print("=" * 70)
    
    print("\n测试：计算600000的布林带值")
    bb_df = get_stock_bollinger_band('600000', '2025-03-07')
    if bb_df is not None and not bb_df.empty:
        print(f"  获取到 {len(bb_df)} 条布林带数据")
        print("  最近5天的数据:")
        print(bb_df.tail())
    else:
        print("  数据不足，无法计算布林带")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
