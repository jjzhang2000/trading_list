#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vegas通道指标计算模块
使用pandas-ta库实现Vegas通道计算和筛选功能
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


def calculate_vegas(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算Vegas通道指标
    
    Args:
        df: DataFrame，必须包含列：close
    
    Returns:
        DataFrame，包含列：ema12, ema26, ema144, ema169, ema576, ema676, trend_direction
        
    Vegas通道组成：
        - 短期通道：EMA 12, EMA 26
        - 中期通道：EMA 144, EMA 169
        - 长期通道：EMA 576, EMA 676
        
    趋势判断：
        - trend_direction = 1: 多头（EMA12 > EMA26 > EMA144 > EMA169 > EMA576 > EMA676）
        - trend_direction = -1: 空头（EMA12 < EMA26 < EMA144 < EMA169 < EMA576 < EMA676）
        - trend_direction = 0: 震荡（其他情况）
    """
    if df.empty or len(df) < 676:
        return pd.DataFrame()
    
    df = df.copy()
    
    df['ema12'] = ta.ema(df['close'], length=12)
    df['ema26'] = ta.ema(df['close'], length=26)
    df['ema144'] = ta.ema(df['close'], length=144)
    df['ema169'] = ta.ema(df['close'], length=169)
    df['ema576'] = ta.ema(df['close'], length=576)
    df['ema676'] = ta.ema(df['close'], length=676)
    
    df['trend_direction'] = 0
    
    bullish_mask = (
        (df['ema12'] > df['ema26']) &
        (df['ema26'] > df['ema144']) &
        (df['ema144'] > df['ema169']) &
        (df['ema169'] > df['ema576']) &
        (df['ema576'] > df['ema676'])
    )
    
    bearish_mask = (
        (df['ema12'] < df['ema26']) &
        (df['ema26'] < df['ema144']) &
        (df['ema144'] < df['ema169']) &
        (df['ema169'] < df['ema576']) &
        (df['ema576'] < df['ema676'])
    )
    
    df.loc[bullish_mask, 'trend_direction'] = 1
    df.loc[bearish_mask, 'trend_direction'] = -1
    
    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    if 'close' in df.columns:
        result['close'] = df['close']
    result['ema12'] = df['ema12']
    result['ema26'] = df['ema26']
    result['ema144'] = df['ema144']
    result['ema169'] = df['ema169']
    result['ema576'] = df['ema576']
    result['ema676'] = df['ema676']
    result['trend_direction'] = df['trend_direction']
    
    return result


def get_stock_vegas(stock_code: str, end_date: str, days: int = 50) -> Optional[pd.DataFrame]:
    """
    计算指定股票的Vegas通道值
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        days: 返回结果天数，默认为50天
    
    Returns:
        DataFrame，包含列：date, close, ema12, ema26, ema144, ema169, ema576, ema676, trend_direction
        如果数据不足则返回None
    
    Note:
        EMA需要足够的历史数据才能收敛到稳定值。
        EMA676需要至少676条数据才能开始输出有效值。
        因此内部始终获取足够的数据进行计算，然后返回用户需要的天数。
    """
    MIN_DATA_BUFFER = 100
    REQUIRED_DATA = 800
    
    df = get_stock_price_before_date(stock_code, end_date, limit=REQUIRED_DATA)
    
    if df.empty or len(df) < REQUIRED_DATA:
        logger.warning(f"Vegas: 股票 {stock_code} 数据不足 (需要 {REQUIRED_DATA} 条, 实际 {len(df)} 条)")
        return None
    
    vegas_df = calculate_vegas(df)
    
    if vegas_df.empty:
        logger.warning(f"Vegas: 股票 {stock_code} 计算结果为空")
        return None
    
    result = vegas_df.tail(days)
    last_row = result.iloc[-1]
    trend = "多头排列" if last_row['trend_direction'] == 1 else ("空头排列" if last_row['trend_direction'] == -1 else "震荡")
    logger.info(f"Vegas: {stock_code} 收盘价={last_row['close']:.2f} "
                f"EMA12={last_row['ema12']:.2f} EMA26={last_row['ema26']:.2f} "
                f"EMA144={last_row['ema144']:.2f} EMA169={last_row['ema169']:.2f} "
                f"EMA576={last_row['ema576']:.2f} EMA676={last_row['ema676']:.2f} "
                f"趋势={trend}")
    
    return result


def filter_bullish_stocks(date: str, stock_codes: List[str]) -> pd.DataFrame:
    """
    筛选指定日期Vegas通道为多头（trend_direction=1）的股票
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
    
    Returns:
        DataFrame，包含列：stock_code, ema12, ema26, ema144, ema169, ema576, ema676, trend_direction
        只包含trend_direction=1的股票
    """
    results = []
    
    logger.info(f"开始计算 {len(stock_codes)} 只股票的Vegas通道...")
    logger.info(f"{'代码':<8} {'收盘价':>10} {'EMA12':>10} {'EMA26':>10} {'EMA144':>10} {'EMA169':>10} {'EMA576':>10} {'EMA676':>10} {'趋势':<6}")
    logger.info("-" * 95)
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        vegas_df = get_stock_vegas(code, date, days=800)
        
        if vegas_df is not None and not vegas_df.empty:
            last_row = vegas_df.iloc[-1]
            trend = "多头" if last_row['trend_direction'] == 1 else ("空头" if last_row['trend_direction'] == -1 else "震荡")
            
            logger.info(f"{code:<8} {last_row.get('close', 0):>10.2f} {last_row['ema12']:>10.2f} {last_row['ema26']:>10.2f} "
                        f"{last_row['ema144']:>10.2f} {last_row['ema169']:>10.2f} {last_row['ema576']:>10.2f} "
                        f"{last_row['ema676']:>10.2f} {trend:<6}")
            
            if last_row['trend_direction'] == 1:
                results.append({
                    'stock_code': code,
                    'ema12': last_row['ema12'],
                    'ema26': last_row['ema26'],
                    'ema144': last_row['ema144'],
                    'ema169': last_row['ema169'],
                    'ema576': last_row['ema576'],
                    'ema676': last_row['ema676'],
                    'trend_direction': last_row['trend_direction']
                })
    
    bullish_df = pd.DataFrame(results)
    
    if not bullish_df.empty:
        bullish_df = bullish_df.sort_values('stock_code').reset_index(drop=True)
    
    return bullish_df


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试Vegas通道指标计算模块 (pandas-ta)")
    logger.info("=" * 70)
    
    logger.info("测试：计算600000的Vegas通道值")
    vegas_df = get_stock_vegas('600026', '2025-03-13')
    if vegas_df is not None and not vegas_df.empty:
        logger.info(f"  获取到 {len(vegas_df)} 条Vegas通道数据")
        logger.info("  最近5天的数据:")
        logger.info(f"\n{vegas_df.tail()}")
    else:
        logger.warning("  数据不足，无法计算Vegas通道")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
