#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合趋势评分模块

根据5个技术指标的计算结果，综合评判多头趋势的强弱
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


def calculate_trend_score(stock_code: str, date: str) -> Optional[Dict]:
    """
    计算单只股票的综合趋势评分
    
    评分规则：
    1. SuperTrend: 多头 +1分
    2. Vegas通道: 多头排列 +2分, 震荡 +1分
    3. 布林带: 收盘价高于中轨 +1分
    4. OCC指标: 多头 +1分
    5. VP Slope: 斜率 > 0 +1分
    
    总分范围: 0-6分
    
    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        包含评分详情的字典，如果数据不足则返回None
    """
    score = 0
    details = {}
    
    st_df = supertrend.get_stock_supertrend(stock_code, date, days=50)
    if st_df is not None and not st_df.empty:
        last_row = st_df.iloc[-1]
        if last_row['trend_direction'] == 1:
            score += 1
            details['supertrend'] = '多头'
        else:
            details['supertrend'] = '空头'
    else:
        details['supertrend'] = '数据不足'
    
    vegas_df = vegas.get_stock_vegas(stock_code, date, days=50)
    if vegas_df is not None and not vegas_df.empty:
        last_row = vegas_df.iloc[-1]
        if last_row['trend_direction'] == 1:
            score += 2
            details['vegas'] = '多头排列'
        elif last_row['trend_direction'] == 0:
            score += 1
            details['vegas'] = '震荡'
        else:
            details['vegas'] = '空头排列'
    else:
        details['vegas'] = '数据不足'
    
    bb_df = bollingerband.get_stock_bollinger_band(stock_code, date, days=50)
    if bb_df is not None and not bb_df.empty:
        last_row = bb_df.iloc[-1]
        if last_row['close'] > last_row['middle_band']:
            score += 1
            details['bollingerband'] = f"高于中轨 (开口率: {last_row['bandwidth']:.2f}%)"
        else:
            details['bollingerband'] = f"低于中轨 (开口率: {last_row['bandwidth']:.2f}%)"
        details['bandwidth'] = last_row['bandwidth']
    else:
        details['bollingerband'] = '数据不足'
        details['bandwidth'] = 0
    
    occ_df = occross.get_stock_occ(stock_code, date, days=50)
    if occ_df is not None and not occ_df.empty:
        last_row = occ_df.iloc[-1]
        if last_row['trend_direction'] == 1:
            score += 1
            details['occ'] = '多头'
        else:
            details['occ'] = '空头'
    else:
        details['occ'] = '数据不足'
    
    slope_df = vp_slope.get_stock_slope(stock_code, date, days=50)
    if slope_df is not None and not slope_df.empty:
        last_row = slope_df.iloc[-1]
        if last_row['slope_long'] > 0:
            score += 1
            details['vp_slope'] = f"斜率>0 ({last_row['slope_long']:.4f})"
        else:
            details['vp_slope'] = f"斜率<=0 ({last_row['slope_long']:.4f})"
        details['slope_value'] = last_row['slope_long']
    else:
        details['vp_slope'] = '数据不足'
        details['slope_value'] = 0
    
    details['total_score'] = score
    details['stock_code'] = stock_code
    details['stock_name'] = get_stock_name(stock_code) or ''
    
    return details


def rank_stocks_by_trend(stock_codes: List[str], date: str) -> pd.DataFrame:
    """
    对股票列表按综合趋势评分排序
    
    Args:
        stock_codes: 股票代码列表
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        DataFrame，包含股票代码、名称、评分和详情，按评分降序排列
    """
    results = []
    
    logger.info(f"开始计算 {len(stock_codes)} 只股票的综合趋势评分...")
    
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")
        
        details = calculate_trend_score(code, date)
        if details is not None:
            results.append(details)
    
    df = pd.DataFrame(results)
    
    if not df.empty:
        df = df.sort_values('total_score', ascending=False).reset_index(drop=True)
        df['rank'] = range(1, len(df) + 1)
        cols = ['rank', 'stock_code', 'stock_name', 'total_score', 
                'supertrend', 'vegas', 'bollingerband', 'occ', 'vp_slope']
        df = df[cols]
    
    logger.info(f"评分完成，共 {len(df)} 只股票")
    
    return df


def get_trend_strength_label(score: int) -> str:
    """
    根据评分返回趋势强度标签
    
    Args:
        score: 综合评分 (0-6)
    
    Returns:
        趋势强度标签
    """
    if score >= 6:
        return '极强'
    elif score >= 5:
        return '很强'
    elif score >= 4:
        return '较强'
    elif score >= 3:
        return '中等'
    elif score >= 2:
        return '较弱'
    elif score >= 1:
        return '很弱'
    else:
        return '空头'


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试综合趋势评分模块")
    logger.info("=" * 70)
    
    test_codes = ['600010', '600026', '600036', '600519']
    date = '2026-03-15'
    
    df = rank_stocks_by_trend(test_codes, date)
    
    if not df.empty:
        logger.info(f"\n评分结果:")
        for _, row in df.iterrows():
            logger.info(f"  {row['rank']}. {row['stock_code']} {row['stock_name']}: "
                        f"{row['total_score']}分 ({get_trend_strength_label(row['total_score'])})")
            logger.info(f"     SuperTrend: {row['supertrend']}, Vegas: {row['vegas']}, "
                        f"布林带: {row['bollingerband']}, OCC: {row['occ']}, VP Slope: {row['vp_slope']}")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
