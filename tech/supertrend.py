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

from data.read_data import get_stock_price_before_date, get_all_stock_codes, get_indicator, save_indicator
from utils.logger import get_logger

logger = get_logger(__name__)

ST_COLUMN = 'supertrend'


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


def _get_st_signal(stock_code: str, date: str,
                   period: int = 10, multiplier: float = 3.0) -> Optional[float]:
    """
    获取 st_above_pct 指标值，优先从数据库缓存读取

    逻辑：
    1. 先从 stock_indicators 表查询当天该股票的 st_above_pct
    2. 如果存在则直接返回
    3. 如果不存在则计算 SuperTrend，算出 st_above_pct，存入数据库后返回
    4. 值会被 clamp 到 [-100, 100]

    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）
        period: ATR计算周期
        multiplier: ATR乘数

    Returns:
        st_above_pct 值（>0为多头，<0为空头），数据不足时返回None
    """
    # 优先从缓存读取
    cached = get_indicator(stock_code, date, ST_COLUMN)
    if cached is not None:
        logger.debug(f"SuperTrend: {stock_code} 使用缓存值 {cached}")
        return float(cached)

    # 缓存未命中，重新计算
    MIN_DATA_BUFFER = 10
    min_required = period + MIN_DATA_BUFFER + 50

    df = get_stock_price_before_date(stock_code, date, limit=max(min_required + period, 200))

    if df.empty or len(df) < period + MIN_DATA_BUFFER:
        logger.warning(f"SuperTrend: 股票 {stock_code} 数据不足 (需要 {period + MIN_DATA_BUFFER} 条, 实际 {len(df)} 条)")
        return None

    st_df = calculate_supertrend(df, period, multiplier)

    if st_df.empty:
        logger.warning(f"SuperTrend: 股票 {stock_code} 计算结果为空")
        return None

    last_row = st_df.iloc[-1]
    st_line = last_row['supertrend']
    close = last_row['close']

    if st_line <= 0:
        logger.warning(f"SuperTrend: 股票 {stock_code} supertrend线值异常 ({st_line:.2f})")
        return None

    st_pct = (close - st_line) / st_line * 100
    save_indicator(stock_code, date, ST_COLUMN, round(st_pct))

    trend = "多头" if st_pct > 0 else "空头"
    logger.info(f"SuperTrend: {stock_code} st_line={st_line:.2f} st_above_pct={st_pct:.2f}% 趋势={trend} (已缓存)")

    return st_pct


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

    # 将 st_above_pct 缓存到数据库
    st_line = last_row['supertrend']
    if st_line > 0:
        st_pct = (last_row['close'] - st_line) / st_line * 100
        save_indicator(stock_code, end_date, ST_COLUMN, round(st_pct))

    return result


def filter_bullish_stocks(date: str, stock_codes: Optional[List[str]] = None, 
                          period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    筛选指定日期 st_above_pct > 0（多头）的股票

    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表，如果为None则使用所有股票
        period: ATR计算周期，默认为10
        multiplier: ATR乘数，默认为3.0

    Returns:
        DataFrame，包含列：stock_code, st_above_pct
        只包含 st_above_pct > 0 的股票
    """
    if stock_codes is None:
        stock_codes = get_all_stock_codes()
    
    results = []
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        st_pct = _get_st_signal(code, date, period, multiplier)
        
        if st_pct is not None and st_pct > 0:
            results.append({
                'stock_code': code,
                'st_above_pct': round(st_pct, 2),
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
