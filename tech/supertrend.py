#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperTrend指标计算模块
使用pandas-ta库实现SuperTrend指标计算和筛选功能
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.read_data import get_stock_price_before_date, get_all_stock_codes
from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    计算SuperTrend指标
    
    Args:
        df: DataFrame，必须包含列：high, low, close
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：supertrend, trend_direction
        
    使用pandas-ta的supertrend函数计算，返回：
        - supertrend: SuperTrend线值
        - trend_direction: 1表示多头，-1表示空头
    """
    if df.empty or len(df) < period:
        return pd.DataFrame()
    
    df = df.copy()
    
    st_df = ta.supertrend(df['high'], df['low'], df['close'], 
                          length=period, multiplier=multiplier)
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    if 'close' in df.columns:
        result['close'] = df['close']
    
    supert_col = [col for col in st_df.columns if col.startswith('SUPERT_') and not col.startswith('SUPERTd') and not col.startswith('SUPERTl') and not col.startswith('SUPERTs')][0]
    supertd_col = [col for col in st_df.columns if col.startswith('SUPERTd_')][0]
    
    result['supertrend'] = st_df[supert_col]
    result['trend_direction'] = st_df[supertd_col]
    
    return result


def get_stock_supertrend(stock_code: str, end_date: str, days: int = 50, 
                         period: int = 10, multiplier: float = 3.0) -> Optional[pd.DataFrame]:
    """
    计算指定股票的SuperTrend值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为50天
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0
    
    Returns:
        DataFrame，包含列：date, supertrend, trend_direction
        如果数据不足则返回None
    """
    MIN_DATA_BUFFER = 10
    min_required = days + period + MIN_DATA_BUFFER
    
    df = get_stock_price_before_date(stock_code, end_date, limit=min_required)
    
    if df.empty or len(df) < period + MIN_DATA_BUFFER:
        logger.warning(f"SuperTrend: 股票 {stock_code} 数据不足 (需要 {period + MIN_DATA_BUFFER} 条, 实际 {len(df)} 条)")
        return None
    
    st_df = calculate_supertrend(df, period, multiplier)
    
    if st_df.empty:
        logger.warning(f"SuperTrend: 股票 {stock_code} 计算结果为空")
        return None
    
    result = st_df.tail(days)
    last_row = result.iloc[-1]
    trend = "多头" if last_row['trend_direction'] == 1 else "空头"
    logger.info(f"SuperTrend: {stock_code} supertrend={last_row['supertrend']:.2f} 趋势={trend}")
    
    return result


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
    """
    if stock_codes is None:
        stock_codes = get_all_stock_codes()
    
    results = []
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
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
    logger.info("=" * 70)
    logger.info("测试SuperTrend指标计算模块 (pandas-ta)")
    logger.info("=" * 70)
    
    logger.info("测试：计算600000的SuperTrend值")
    st_df = get_stock_supertrend('600000', '2025-03-07')
    if st_df is not None and not st_df.empty:
        logger.info(f"  获取到 {len(st_df)} 条SuperTrend数据")
        logger.info("  最近5天的数据:")
        logger.info(f"\n{st_df.tail()}")
    else:
        logger.warning("  数据不足，无法计算SuperTrend")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
