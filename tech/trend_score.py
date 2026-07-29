#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多指标加总评分模块

总分 = supertrend + vegas + bollingerbands + openclosecross + volumeprofile
五个指标值均从 stock_indicators 表读取（-100 ~ 100 的整数），简单求和即为总分。
"""

import pandas as pd
from typing import Optional, List, Dict
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.read_data import get_stock_name, get_indicator
from utils.logger import get_logger

logger = get_logger(__name__)

INDICATOR_COLUMNS = ['supertrend', 'vegas', 'bollingerbands', 'openclosecross', 'volumeprofile']


def get_stock_score(stock_code: str, date: str) -> Optional[Dict]:
    """
    从 stock_indicators 读取5个指标值并求和

    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）

    Returns:
        字典，包含 stock_code, stock_name, 5个指标值, strength_score（总和）
        如果股票名称不存在则返回None
    """
    name = get_stock_name(stock_code)
    if not name:
        return None

    values = {}
    total = 0
    for col in INDICATOR_COLUMNS:
        v = get_indicator(stock_code, date, col)
        v = v if v is not None else 0
        values[col] = v
        total += v

    return {
        'stock_code': stock_code,
        'stock_name': name,
        'supertrend': values['supertrend'],
        'vegas': values['vegas'],
        'bollingerbands': values['bollingerbands'],
        'openclosecross': values['openclosecross'],
        'volumeprofile': values['volumeprofile'],
        'strength_score': total,
    }


def rank_stocks_by_strength(stock_codes: List[str], date: str,
                            holding_codes: List[str] = None) -> pd.DataFrame:
    """
    按5指标总和降序排列

    Args:
        stock_codes: 股票代码列表
        date: 日期（YYYY-MM-DD格式）
        holding_codes: 持仓股票代码列表（会在股票名称前加*标记）

    Returns:
        DataFrame，按 strength_score 降序排列
    """
    if holding_codes is None:
        holding_codes = []
    holding_set = set(holding_codes)

    logger.info(f"开始计算 {len(stock_codes)} 只股票的指标加总评分...")

    results = []
    for i, code in enumerate(stock_codes):
        if (i + 1) % 100 == 0:
            logger.info(f"  处理进度: {i + 1}/{len(stock_codes)}")

        score = get_stock_score(code, date)
        if score is not None:
            results.append(score)

    if not results:
        logger.info("无有效数据")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # 持仓股票名称前加*标记
    if holding_set:
        df['stock_name'] = df.apply(
            lambda row: '*' + row['stock_name'] if row['stock_code'] in holding_set else row['stock_name'],
            axis=1
        )

    df = df.sort_values('strength_score', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)

    cols = ['rank', 'stock_code', 'stock_name', 'strength_score',
            'supertrend', 'vegas', 'bollingerbands', 'openclosecross', 'volumeprofile']
    df = df[cols]

    logger.info(f"加总评分完成，共 {len(df)} 只股票")

    return df


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试多指标加总评分模块")
    logger.info("=" * 70)

    test_codes = ['600010', '600026', '600036']
    date = '2026-03-15'

    df = rank_stocks_by_strength(test_codes, date)

    if not df.empty:
        logger.info(f"\n排序结果:")
        for _, row in df.iterrows():
            logger.info(f"  {row['rank']}. {row['stock_code']} {row['stock_name']}: "
                        f"{row['strength_score']}分 "
                        f"(ST={row['supertrend']} VG={row['vegas']} "
                        f"BB={row['bollingerbands']} OC={row['openclosecross']} VP={row['volumeprofile']})")

    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
