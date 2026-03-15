#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VolumeProfile Slope 指标计算模块
使用pandas-ta库实现线性回归斜率计算和筛选功能
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.read_data import get_stock_price_before_date
from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_slope(df: pd.DataFrame, period_long: int = 100, period_short: int = 10) -> pd.DataFrame:
    """
    计算VolumeProfile Slope指标
    
    Args:
        df: DataFrame，必须包含列：close
        period_long: 长期周期，默认为100
        period_short: 短期周期，默认为10
    
    Returns:
        DataFrame，包含列：slope_long, slope_short
        
    使用pandas-ta的linreg函数计算线性回归，然后提取斜率：
        slope = linear_regression(close, period).slope
    """
    if df.empty or len(df) < period_long:
        return pd.DataFrame()
    
    df = df.copy()
    
    linreg_long = ta.linreg(df['close'], length=period_long, angle=False, intercept=False, 
                            r=False, slope=True)
    linreg_short = ta.linreg(df['close'], length=period_short, angle=False, intercept=False, 
                             r=False, slope=True)
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    result['slope_long'] = linreg_long
    result['slope_short'] = linreg_short
    
    return result


def get_stock_slope(stock_code: str, end_date: str, days: int = 150, 
                    period_long: int = 100, period_short: int = 10) -> Optional[pd.DataFrame]:
    """
    计算指定股票的斜率值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 计算天数，默认为150天
        period_long: 长期周期，默认为100
        period_short: 短期周期，默认为10
    
    Returns:
        DataFrame，包含列：date, slope_long, slope_short
        如果数据不足则返回None
    """
    MIN_DATA_BUFFER = 10
    min_required = days + period_long + MIN_DATA_BUFFER
    
    df = get_stock_price_before_date(stock_code, end_date, limit=min_required)
    
    if df.empty or len(df) < period_long + MIN_DATA_BUFFER:
        return None
    
    slope_df = calculate_slope(df, period_long, period_short)
    
    if slope_df.empty:
        return None
    
    return slope_df.tail(days)


def filter_stocks_by_slope(date: str, stock_codes: List[str], 
                           period_long: int = 100, period_short: int = 10) -> pd.DataFrame:
    """
    筛选指定日期斜率值大于0的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
        period_long: 长期周期，默认为100
        period_short: 短期周期，默认为10
    
    Returns:
        DataFrame，包含列：stock_code, slope_long, slope_short
        只包含slope_long > 0的股票
    """
    results = []
    
    logger.info(f"开始计算 {len(stock_codes)} 只股票的斜率...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        slope_df = get_stock_slope(code, date, days=150, 
                                   period_long=period_long, period_short=period_short)
        
        if slope_df is not None and not slope_df.empty:
            last_row = slope_df.iloc[-1]
            if pd.notna(last_row['slope_long']) and last_row['slope_long'] > 0:
                results.append({
                    'stock_code': code,
                    'slope_long': last_row['slope_long'],
                    'slope_short': last_row['slope_short']
                })
    
    result_df = pd.DataFrame(results)
    
    if not result_df.empty:
        result_df = result_df.sort_values('slope_long', ascending=False).reset_index(drop=True)
    
    return result_df


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试VolumeProfile Slope指标计算模块 (pandas-ta)")
    logger.info("=" * 70)
    
    logger.info("测试：计算600000的斜率值")
    slope_df = get_stock_slope('600000', '2025-03-07')
    if slope_df is not None and not slope_df.empty:
        logger.info(f"  获取到 {len(slope_df)} 条斜率数据")
        logger.info("  最近5天的数据:")
        logger.info(f"\n{slope_df.tail()}")
    else:
        logger.warning("  数据不足，无法计算斜率")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
