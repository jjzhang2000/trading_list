#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合趋势强度评分模块

对已筛选出的多头股票，衡量多头趋势的强弱程度
"""

import pandas as pd
from typing import Optional, List, Dict
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tech import supertrend, vegas, bollingerband, occross, vp_slope
from data.read_data import get_stock_name
from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_trend_strength(stock_code: str, date: str) -> Optional[Dict]:
    """
    计算单只股票的多头趋势强度
    
    强度指标：
    1. SuperTrend: 收盘价高于supertrend线的幅度 (%)
    2. Vegas通道: 收盘价高于EMA144的幅度 (%) - 代表中期趋势强度
    3. 布林带: 开口率 (%) - 开口越大波动越大趋势越强
    4. OCC: occ_close高于occ_open的幅度 (%)
    5. VP Slope: 长期斜率值 - 斜率越大趋势越强
    
    综合强度 = 各指标标准化后的加权平均
    
    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        包含强度详情的字典，如果数据不足则返回None
    """
    metrics = {}
    
    st_df = supertrend.get_stock_supertrend(stock_code, date, days=50)
    if st_df is not None and not st_df.empty:
        last_row = st_df.iloc[-1]
        close = last_row.get('close', 0)
        st_value = last_row['supertrend']
        if st_value > 0 and close > 0:
            metrics['st_above_pct'] = (close - st_value) / st_value * 100
        else:
            metrics['st_above_pct'] = 0
        metrics['st_trend'] = '多头' if last_row['trend_direction'] == 1 else '空头'
    else:
        metrics['st_above_pct'] = 0
        metrics['st_trend'] = '数据不足'
    
    vegas_df = vegas.get_stock_vegas(stock_code, date, days=50)
    if vegas_df is not None and not vegas_df.empty:
        last_row = vegas_df.iloc[-1]
        close = last_row['close']
        ema144 = last_row['ema144']
        if ema144 > 0 and close > 0:
            metrics['vegas_above_pct'] = (close - ema144) / ema144 * 100
        else:
            metrics['vegas_above_pct'] = 0
        metrics['vegas_trend'] = '多头排列' if last_row['trend_direction'] == 1 else ('震荡' if last_row['trend_direction'] == 0 else '空头排列')
    else:
        metrics['vegas_above_pct'] = 0
        metrics['vegas_trend'] = '数据不足'
    
    bb_df = bollingerband.get_stock_bollinger_band(stock_code, date, days=50)
    if bb_df is not None and not bb_df.empty:
        last_row = bb_df.iloc[-1]
        metrics['bandwidth'] = last_row['bandwidth']
        metrics['bb_above_middle'] = last_row['close'] > last_row['middle_band']
    else:
        metrics['bandwidth'] = 0
        metrics['bb_above_middle'] = False
    
    occ_df = occross.get_stock_occ(stock_code, date, days=50)
    if occ_df is not None and not occ_df.empty:
        last_row = occ_df.iloc[-1]
        occ_open = last_row['occ_open']
        occ_close = last_row['occ_close']
        if occ_open > 0:
            metrics['occ_above_pct'] = (occ_close - occ_open) / occ_open * 100
        else:
            metrics['occ_above_pct'] = 0
        metrics['occ_trend'] = '多头' if last_row['trend_direction'] == 1 else '空头'
    else:
        metrics['occ_above_pct'] = 0
        metrics['occ_trend'] = '数据不足'
    
    slope_df = vp_slope.get_stock_slope(stock_code, date, days=50)
    if slope_df is not None and not slope_df.empty:
        last_row = slope_df.iloc[-1]
        metrics['slope_long'] = last_row['slope_long']
        metrics['slope_short'] = last_row['slope_short']
    else:
        metrics['slope_long'] = 0
        metrics['slope_short'] = 0
    
    st_score = min(metrics['st_above_pct'] / 10, 10) if metrics['st_above_pct'] > 0 else 0
    vegas_score = min(metrics['vegas_above_pct'] / 20, 10) if metrics['vegas_above_pct'] > 0 else 0
    bb_score = min(metrics['bandwidth'] / 10, 10) if metrics['bandwidth'] > 0 else 0
    occ_score = min(metrics['occ_above_pct'] / 5 * 10, 10) if metrics['occ_above_pct'] > 0 else 0
    slope_score = min(metrics['slope_long'] * 100, 10) if metrics['slope_long'] > 0 else 0
    
    metrics['st_score'] = round(st_score, 2)
    metrics['vegas_score'] = round(vegas_score, 2)
    metrics['bb_score'] = round(bb_score, 2)
    metrics['occ_score'] = round(occ_score, 2)
    metrics['slope_score'] = round(slope_score, 2)
    
    weights = {
        'st': 1.0,
        'vegas': 2.0,
        'bb': 1.0,
        'occ': 1.0,
        'slope': 1.0
    }
    
    total_weight = sum(weights.values())
    weighted_score = (
        st_score * weights['st'] +
        vegas_score * weights['vegas'] +
        bb_score * weights['bb'] +
        occ_score * weights['occ'] +
        slope_score * weights['slope']
    ) / total_weight
    
    metrics['strength_score'] = round(weighted_score, 2)
    metrics['stock_code'] = stock_code
    metrics['stock_name'] = get_stock_name(stock_code) or ''
    
    return metrics


def rank_stocks_by_strength(stock_codes: List[str], date: str) -> pd.DataFrame:
    """
    对股票列表按多头趋势强度排序
    
    Args:
        stock_codes: 股票代码列表
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        DataFrame，按强度评分降序排列
    """
    results = []
    
    logger.info(f"开始计算 {len(stock_codes)} 只股票的趋势强度...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        metrics = calculate_trend_strength(code, date)
        if metrics is not None:
            results.append(metrics)
    
    df = pd.DataFrame(results)
    
    if not df.empty:
        df = df.sort_values('strength_score', ascending=False).reset_index(drop=True)
        df['rank'] = range(1, len(df) + 1)
        
        cols = ['rank', 'stock_code', 'stock_name', 'strength_score',
                'st_score', 'vegas_score', 'bb_score', 'occ_score', 'slope_score',
                'st_above_pct', 'vegas_above_pct', 'bandwidth', 
                'occ_above_pct', 'slope_long']
        df = df[[c for c in cols if c in df.columns]]
    
    logger.info(f"强度评分完成，共 {len(df)} 只股票")
    
    return df


def get_strength_label(score: float) -> str:
    """
    根据强度评分返回标签
    
    Args:
        score: 强度评分 (0-10)
    
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
    logger.info("测试趋势强度评分模块")
    logger.info("=" * 70)
    
    test_codes = ['600010', '600026', '600036']
    date = '2026-03-15'
    
    df = rank_stocks_by_strength(test_codes, date)
    
    if not df.empty:
        logger.info(f"\n强度评分结果:")
        for _, row in df.iterrows():
            logger.info(f"  {row['rank']}. {row['stock_code']} {row['stock_name']}: "
                        f"{row['strength_score']:.2f}分 ({get_strength_label(row['strength_score'])})")
            logger.info(f"     SuperTrend高于: {row['st_above_pct']:.2f}%, "
                        f"Vegas高于EMA144: {row['vegas_above_pct']:.2f}%, "
                        f"布林带开口率: {row['bandwidth']:.2f}%")
            logger.info(f"     OCC高于: {row['occ_above_pct']:.2f}%, "
                        f"VP Slope: {row['slope_long']:.4f}")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
