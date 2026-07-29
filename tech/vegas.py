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

from data.read_data import get_stock_price_before_date, save_indicator
from utils.logger import get_logger

logger = get_logger(__name__)

VEGAS_COLUMN = 'vegas'


def calculate_vegas(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算Vegas通道指标

    Args:
        df: DataFrame，必须包含列：close

    Returns:
        DataFrame，包含列：ema12, ema144, ema576, trend_direction

    Vegas通道组成：
        - 短期：EMA 12
        - 中期：EMA 144
        - 长期：EMA 576

    趋势判断：
        - trend_direction = 1: 多头（close > EMA12 > EMA144 > EMA576）
        - trend_direction = -1: 空头（close < EMA12 < EMA144 < EMA576）
        - trend_direction = 0: 震荡（其他情况）
    """
    if df.empty or len(df) < 576:
        return pd.DataFrame()

    df = df.copy()

    df['ema12'] = ta.ema(df['close'], length=12)
    df['ema144'] = ta.ema(df['close'], length=144)
    df['ema576'] = ta.ema(df['close'], length=576)

    df['trend_direction'] = 0

    bullish_mask = (
        (df['close'] > df['ema12']) &
        (df['ema12'] > df['ema144']) &
        (df['ema144'] > df['ema576'])
    )

    bearish_mask = (
        (df['close'] < df['ema12']) &
        (df['ema12'] < df['ema144']) &
        (df['ema144'] < df['ema576'])
    )

    df.loc[bullish_mask, 'trend_direction'] = 1
    df.loc[bearish_mask, 'trend_direction'] = -1

    result = pd.DataFrame()
    if 'date' in df.columns:
        result['date'] = df['date']
    if 'close' in df.columns:
        result['close'] = df['close']
    result['ema12'] = df['ema12']
    result['ema144'] = df['ema144']
    result['ema576'] = df['ema576']
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
        DataFrame，包含列：date, close, ema12, ema144, ema576, trend_direction
        如果数据不足则返回None

    Note:
        EMA576需要足够的历史数据才能收敛到稳定值。
    """
    MIN_DATA_REQUIRED = 800

    df = get_stock_price_before_date(stock_code, end_date, limit=2000)

    if df.empty or len(df) < MIN_DATA_REQUIRED:
        logger.warning(f"Vegas: 股票 {stock_code} 数据不足 (需要 {MIN_DATA_REQUIRED} 条, 实际 {len(df)} 条)")
        return None

    vegas_df = calculate_vegas(df)

    if vegas_df.empty:
        logger.warning(f"Vegas: 股票 {stock_code} 计算结果为空")
        return None

    result = vegas_df.tail(days)
    last_row = result.iloc[-1]
    trend = "多头排列" if last_row['trend_direction'] == 1 else ("空头排列" if last_row['trend_direction'] == -1 else "震荡")
    logger.info(f"Vegas: {stock_code} 收盘价={last_row.get('close', 0):.2f} "
                f"EMA12={last_row['ema12']:.2f} EMA144={last_row['ema144']:.2f} "
                f"EMA576={last_row['ema576']:.2f} 趋势={trend}")

    return result


def filter_bullish_stocks(date: str, stock_codes: List[str], min_bullish_days: int = 10) -> pd.DataFrame:
    """
    筛选指定日期Vegas通道为多头且连续多头天数>=min_bullish_days的股票

    Args:
        date: 日期（YYYY-MM-DD格式）
        stock_codes: 股票代码列表
        min_bullish_days: 要求连续多头排列的最少交易日天数，默认10天

    Returns:
        DataFrame，包含列：stock_code, ema12, ema144, ema576, trend_direction
    """
    results = []

    logger.info(f"开始计算 {len(stock_codes)} 只股票的Vegas通道（要求连续多头>= {min_bullish_days} 天）...")
    logger.info(f"{'代码':<8} {'收盘价':>10} {'EMA12':>10} {'EMA144':>10} {'EMA576':>10} {'趋势':<6} {'连续多头':>8}")
    logger.info("-" * 75)

    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")

        vegas_df = get_stock_vegas(code, date, days=800)

        if vegas_df is not None and not vegas_df.empty:
            last_row = vegas_df.iloc[-1]
            trend = "多头" if last_row['trend_direction'] == 1 else ("空头" if last_row['trend_direction'] == -1 else "震荡")

            bullish_streak = 0
            for j in range(len(vegas_df) - 1, -1, -1):
                if vegas_df.iloc[j]['trend_direction'] == 1:
                    bullish_streak += 1
                else:
                    break

            logger.info(f"{code:<8} {last_row.get('close', 0):>10.2f} {last_row['ema12']:>10.2f} "
                        f"{last_row['ema144']:>10.2f} {last_row['ema576']:>10.2f} {trend:<6} {bullish_streak:>8}")

            # 缓存 vegas_above_pct 到数据库
            close_price = last_row.get('close', 0)
            ema144 = last_row['ema144']
            if close_price > 0 and ema144 > 0:
                vegas_pct = (close_price - ema144) / ema144 * 100
                save_indicator(code, date, VEGAS_COLUMN, round(vegas_pct))

            if last_row['trend_direction'] == 1 and bullish_streak >= min_bullish_days:
                results.append({
                    'stock_code': code,
                    'ema12': last_row['ema12'],
                    'ema144': last_row['ema144'],
                    'ema576': last_row['ema576'],
                    'trend_direction': last_row['trend_direction']
                })

    bullish_df = pd.DataFrame(results)

    if not bullish_df.empty:
        bullish_df = bullish_df.sort_values('stock_code').reset_index(drop=True)

    return bullish_df


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试Vegas通道指标计算模块")
    logger.info("=" * 70)

    logger.info("测试：计算600026的Vegas通道值")
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
