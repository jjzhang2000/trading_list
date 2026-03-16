#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票筛选主程序（命令行版本）
"""

import argparse
import os
from datetime import datetime
from typing import List, Optional

from utils.logger import get_logger, get_log_dir
from data.read_data import get_all_stock_codes, get_stock_name
from data import extract_data
from tech import supertrend, vegas, bollingerband, occross, vp_slope, trend_score

logger = get_logger(__name__)

SHAREHOLDING_FILE = os.path.join(os.path.dirname(__file__), 'shareholding.txt')


def load_shareholding() -> List[str]:
    """读取持仓股票列表"""
    if not os.path.exists(SHAREHOLDING_FILE):
        return []
    
    codes = []
    with open(SHAREHOLDING_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            code = line.strip()
            if code and code.isdigit():
                codes.append(code)
    
    return codes


def update_stock_data(proxy: Optional[str] = None):
    """更新股票数据"""
    from data.batch_fetch import update_daily_data_batch
    
    logger.info("=" * 70)
    logger.info("更新股票数据...")
    logger.info("=" * 70)
    
    update_daily_data_batch(proxy=proxy)


def filter_by_supertrend(date: str, stock_codes: List[str]) -> List[str]:
    """SuperTrend筛选"""
    logger.info(f"[1/5] SuperTrend筛选 - 输入: {len(stock_codes)} 只股票")
    df = supertrend.filter_bullish_stocks(date, stock_codes=stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    logger.info(f"      SuperTrend筛选 - 输出: {len(result)} 只股票 (多头趋势)")
    return result


def filter_by_vegas(date: str, stock_codes: List[str]) -> List[str]:
    """Vegas通道筛选"""
    logger.info(f"[2/5] Vegas通道筛选 - 输入: {len(stock_codes)} 只股票")
    df = vegas.filter_bullish_stocks(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    logger.info(f"      Vegas通道筛选 - 输出: {len(result)} 只股票 (多头排列)")
    return result


def filter_by_bollingerband(date: str, stock_codes: List[str], threshold: float = 10.0) -> List[str]:
    """布林带筛选"""
    logger.info(f"[3/5] 布林带筛选 - 输入: {len(stock_codes)} 只股票 (开口率阈值: {threshold}%)")
    df = bollingerband.filter_stocks_by_bandwidth(date, stock_codes, threshold=threshold)
    result = df['stock_code'].tolist() if not df.empty else []
    logger.info(f"      布林带筛选 - 输出: {len(result)} 只股票 (开口率>{threshold}%)")
    return result


def filter_by_occross(date: str, stock_codes: List[str]) -> List[str]:
    """OCC指标筛选"""
    logger.info(f"[4/5] OCC指标筛选 - 输入: {len(stock_codes)} 只股票")
    df = occross.filter_bullish_stocks(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    logger.info(f"      OCC指标筛选 - 输出: {len(result)} 只股票 (多头趋势)")
    return result


def filter_by_vp_slope(date: str, stock_codes: List[str]) -> List[str]:
    """VP Slope筛选"""
    logger.info(f"[5/5] VP Slope筛选 - 输入: {len(stock_codes)} 只股票")
    df = vp_slope.filter_stocks_by_slope(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    logger.info(f"      VP Slope筛选 - 输出: {len(result)} 只股票 (斜率>0)")
    return result


def save_to_csv(df, date: str) -> str:
    """保存结果到CSV文件"""
    log_dir = get_log_dir()
    filename = f"listing-{date}.csv"
    filepath = os.path.join(log_dir, filename)
    
    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
    except PermissionError:
        from datetime import datetime
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f"listing-{date}_{timestamp}.csv"
        filepath = os.path.join(log_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    logger.info(f"结果已保存到: {filepath}")
    
    return filepath


def run_filter(date: str, bandwidth_threshold: float = 10.0, proxy: Optional[str] = None, skip_update: bool = True) -> List[str]:
    """执行完整的股票筛选流程"""
    logger.info("=" * 70)
    logger.info(f"股票筛选主程序 - 筛选日期: {date}")
    logger.info("=" * 70)
    
    if not skip_update:
        update_stock_data(proxy=proxy)
    
    logger.info("获取所有股票代码...")
    all_codes = get_all_stock_codes()
    logger.info(f"共有 {len(all_codes)} 只股票")
    
    codes = all_codes
    
    logger.info("过滤ST股票...")
    st_count = 0
    filtered_codes = []
    for code in codes:
        name = get_stock_name(code) or ''
        if 'ST' in name.upper():
            st_count += 1
        else:
            filtered_codes.append(code)
    logger.info(f"过滤掉 {st_count} 只ST股票，剩余 {len(filtered_codes)} 只")
    codes = filtered_codes
    
    codes = filter_by_supertrend(date, codes)
    if not codes:
        logger.info("筛选结果为空，程序结束")
        return []
    
    codes = filter_by_vegas(date, codes)
    if not codes:
        logger.info("筛选结果为空，程序结束")
        return []
    
    codes = filter_by_bollingerband(date, codes, threshold=bandwidth_threshold)
    if not codes:
        logger.info("筛选结果为空，程序结束")
        return []
    
    codes = filter_by_occross(date, codes)
    if not codes:
        logger.info("筛选结果为空，程序结束")
        return []
    
    codes = filter_by_vp_slope(date, codes)
    if not codes:
        logger.info("筛选结果为空，程序结束")
        return []
    
    shareholding = load_shareholding()
    logger.info(f"读取持仓股票: {len(shareholding)} 只")
    
    all_result_codes = list(set(codes + shareholding))
    
    logger.info("=" * 70)
    logger.info("计算趋势强度评分...")
    logger.info("=" * 70)
    
    strength_df = trend_score.rank_stocks_by_strength(all_result_codes, date)
    
    if not strength_df.empty:
        strength_df['is_shareholding'] = strength_df['stock_code'].isin(shareholding)
        
        strength_df['stock_name'] = strength_df.apply(
            lambda row: f"*{row['stock_name']}" if row['is_shareholding'] and row['stock_name'] else row['stock_name'],
            axis=1
        )
        
        logger.info(f"最终结果 ({len(all_result_codes)} 只，按趋势强度降序排列):")
        for _, row in strength_df.iterrows():
            mark = "★" if row['is_shareholding'] else " "
            display_name = row['stock_name'].lstrip('*') if row['stock_name'].startswith('*') else row['stock_name']
            logger.info(f"  {row['rank']:3d}. {mark} {row['stock_code']} {display_name}: "
                        f"{row['strength_score']:.2f}分 ({trend_score.get_strength_label(row['strength_score'])})")
        
        save_to_csv(strength_df, date)
    
    return codes


def main():
    """主函数：解析命令行参数并执行筛选"""
    parser = argparse.ArgumentParser(description='股票筛选主程序')
    parser.add_argument('-d', '--date', type=str, default=None,
                        help='筛选日期 (YYYY-MM-DD格式，默认为今天)')
    parser.add_argument('-b', '--bandwidth', type=float, default=10.0,
                        help='布林带开口率阈值 (默认: 10.0)')
    parser.add_argument('-p', '--proxy', type=str, default=None,
                        help='代理服务器地址，例如: http://127.0.0.1:7890')
    parser.add_argument('--update', action='store_true',
                        help='更新股票数据 (默认跳过更新)')
    
    args = parser.parse_args()
    
    if args.date:
        date = args.date
    else:
        date = datetime.now().strftime('%Y-%m-%d')
    
    result = run_filter(
        date, 
        bandwidth_threshold=args.bandwidth,
        proxy=args.proxy,
        skip_update=not args.update
    )
    
    return result


if __name__ == '__main__':
    main()
