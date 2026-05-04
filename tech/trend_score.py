#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ST-Slope(60日) 多因子排序模块 — Cross-Sectional Ranking

因子1: ST偏离度(st_above_pct) — 收盘价高于SuperTrend线的百分比
因子2: 60日对数价格线性回归斜率 — 惩罚过度延伸
合成公式: composite = zscore(st_above_pct) - zscore(slope_60d)
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.read_data import get_stock_price_before_date, get_stock_name
from utils.logger import get_logger

logger = get_logger(__name__)

ST_PERIOD = 10
ST_MULTIPLIER = 3.0
SLOPE_WINDOW = 60
DATA_DAYS = 120


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def supertrend_line(high: pd.Series, low: pd.Series, close: pd.Series,
                    period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """返回pd.Series: SuperTrend线值（上升趋势返回下轨，下降趋势返回上轨）"""
    atr = compute_atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(close)
    final_upper = pd.Series(np.nan, index=close.index)
    final_lower = pd.Series(np.nan, index=close.index)
    trend = pd.Series(0, index=close.index)

    first = period
    if first >= n:
        return pd.Series(np.nan, index=close.index)
    final_upper.iloc[first] = basic_upper.iloc[first]
    final_lower.iloc[first] = basic_lower.iloc[first]
    trend.iloc[first] = 1

    for i in range(first + 1, n):
        prev_upper = final_upper.iloc[i - 1]
        if pd.notna(prev_upper) and (basic_upper.iloc[i] < prev_upper
                                      or close.iloc[i - 1] > prev_upper):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = prev_upper

        prev_lower = final_lower.iloc[i - 1]
        if pd.notna(prev_lower) and (basic_lower.iloc[i] > prev_lower
                                      or close.iloc[i - 1] < prev_lower):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = prev_lower

        if trend.iloc[i - 1] == 1:
            trend.iloc[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        else:
            trend.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1

    st_line = pd.Series(np.nan, index=close.index)
    for i in range(first, n):
        if trend.iloc[i] == 1:
            st_line.iloc[i] = final_lower.iloc[i]
        else:
            st_line.iloc[i] = final_upper.iloc[i]

    return st_line


def rolling_slope(series: pd.Series, window: int) -> pd.Series:
    """对数价格的滚动线性回归斜率"""
    log_s = np.log(series)
    x = np.arange(window)

    def _slope(y):
        y = y.values if hasattr(y, 'values') else np.array(y)
        mask = ~np.isnan(y)
        if mask.sum() < window // 2:
            return np.nan
        return np.polyfit(x[mask], y[mask], 1)[0]

    return log_s.rolling(window).apply(_slope, raw=False)


def calculate_trend_strength(stock_code: str, date: str) -> Optional[Dict]:
    """
    计算单只股票的ST偏离度和60日斜率因子

    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）

    Returns:
        包含因子值的字典，如果数据不足则返回None
    """
    df = get_stock_price_before_date(stock_code, date, DATA_DAYS)
    if df.empty or len(df) < max(ST_PERIOD, SLOPE_WINDOW) + 5:
        return None

    try:
        df = df.copy()
        st_line = supertrend_line(
            df['high'], df['low'], df['close'],
            ST_PERIOD, ST_MULTIPLIER
        )
        slope = rolling_slope(df['close'], SLOPE_WINDOW)

        last_close = df['close'].iloc[-1]
        last_st = st_line.iloc[-1]
        last_slope = slope.iloc[-1]

        if pd.isna(last_st) or last_st <= 0 or np.isnan(last_slope):
            return None

        st_above_pct = (last_close - last_st) / last_st * 100

        return {
            'stock_code': stock_code,
            'stock_name': get_stock_name(stock_code) or '',
            'st_above_pct': round(st_above_pct, 4),
            'slope_60d': float(last_slope),
        }
    except Exception as e:
        logger.warning(f"计算 {stock_code} 因子失败: {e}")
        return None


def rank_stocks_by_strength(stock_codes: List[str], date: str) -> pd.DataFrame:
    """
    对股票列表按ST-Slope截面Z-score排序

    合成公式: composite = zscore(st_above_pct) - zscore(slope_60d)
    ST偏离度高加分，高斜率（过度延伸）扣分

    Args:
        stock_codes: 股票代码列表
        date: 日期（YYYY-MM-DD格式）

    Returns:
        DataFrame，按合成得分降序排列
    """
    logger.info(f"开始计算 {len(stock_codes)} 只股票的ST-Slope因子...")

    results = []
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")

        metrics = calculate_trend_strength(code, date)
        if metrics is not None:
            results.append(metrics)

    if not results:
        logger.info("无有效因子数据")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    st_s = df['st_above_pct']
    sl_s = df['slope_60d']

    st_std = st_s.std()
    sl_std = sl_s.std()

    if st_std == 0 or sl_std == 0:
        logger.warning("因子标准差为0，无法Z-score标准化")
        df['composite'] = 0.0
    else:
        df['st_zscore'] = (st_s - st_s.mean()) / st_std
        df['slope_zscore'] = (sl_s - sl_s.mean()) / sl_std
        df['composite'] = df['st_zscore'] - df['slope_zscore']

    score_min = df['composite'].min()
    score_max = df['composite'].max()
    if score_max > score_min:
        df['strength_score'] = round((df['composite'] - score_min) / (score_max - score_min) * 10, 2)
    else:
        df['strength_score'] = 5.0

    df = df.sort_values('composite', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)

    cols = ['rank', 'stock_code', 'stock_name', 'strength_score',
            'st_above_pct', 'slope_60d', 'st_zscore', 'slope_zscore', 'composite']
    df = df[[c for c in cols if c in df.columns]]

    logger.info(f"ST-Slope截面排序完成，共 {len(df)} 只股票")

    return df


def get_strength_label(score: float) -> str:
    """
    根据强度评分返回标签

    Args:
        score: 强度评分 (0-10，由composite归一化而来)

    Returns:
        强度标签
    """
    if score >= 8:
        return '极强'
    elif score >= 6:
        return '很强'
    elif score >= 4:
        return '较强'
    elif score >= 2:
        return '一般'
    else:
        return '较弱'


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试ST-Slope截面排序模块")
    logger.info("=" * 70)

    test_codes = ['600010', '600026', '600036']
    date = '2026-03-15'

    df = rank_stocks_by_strength(test_codes, date)

    if not df.empty:
        logger.info(f"\n截面排序结果:")
        for _, row in df.iterrows():
            logger.info(f"  {row['rank']}. {row['stock_code']} {row['stock_name']}: "
                        f"{row['strength_score']:.2f}分 ({get_strength_label(row['strength_score'])})")
            logger.info(f"     ST偏离度: {row['st_above_pct']:.2f}%, "
                        f"60日斜率: {row['slope_60d']:.6f}, "
                        f"Z-score: ST={row['st_zscore']:.3f} Slope={row['slope_zscore']:.3f}")

    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
