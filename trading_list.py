#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票筛选主程序（命令行版本）
"""

import argparse
from datetime import datetime
from typing import List, Optional

from utils.logger import get_logger
from data.read_data import get_all_stock_codes
from data import extract_data
from tech import supertrend, vegas, bollingerband, occross, vp_slope

logger = get_logger(__name__)


def update_stock_data(proxy: Optional[str] = None):
    """更新股票数据"""
    logger.info("=" * 70)
    logger.info("更新股票数据...")
    logger.info("=" * 70)
    
    adj_fetcher = extract_data.RealAdjustFactorFetcher(proxy=proxy)
    extract_data.create_database(extract_data.DB_PATH)
    
    stock_list = extract_data.get_sh_a_stock_list()
    total = len(stock_list)
    
    if total == 0:
        logger.warning("没有获取到股票列表，跳过数据更新")
        return
    
    logger.info(f"共需更新 {total} 只股票")
    
    success_count = 0
    fail_count = 0
    
    import sqlite3
    import time
    from datetime import timedelta
    
    conn = sqlite3.connect(extract_data.DB_PATH)
    end_date = datetime.now()
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    for i, (stock_code, stock_name) in enumerate(stock_list):
        stock_info = extract_data.get_stock_info(conn, stock_code)
        
        if stock_info is None:
            start_date = end_date - timedelta(days=extract_data.YEARS * 365)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code, start_date_str, end_date_str
            )
            
            if df_adj is not None and not df_adj.empty:
                success_count += 1
                extract_data.insert_data(extract_data.DB_PATH, stock_code, df_adj)
                extract_data.update_stock_info(conn, stock_code, df_adj, stock_name)
        else:
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code, stock_info['end_date'], end_date_str
            )
            
            if df_adj is not None and not df_adj.empty:
                end_date_data = df_adj[df_adj['date'] == stock_info['end_date']]
                
                if not end_date_data.empty:
                    source_close = end_date_data.iloc[0]['close']
                    db_close = stock_info['end_date_close']
                    
                    if abs(source_close - db_close) > 0.01:
                        start_date = end_date - timedelta(days=extract_data.YEARS * 365)
                        start_date_str = start_date.strftime('%Y-%m-%d')
                        
                        df_adj_full, source_full = adj_fetcher.fetch_adjust_factor(
                            stock_code, start_date_str, end_date_str
                        )
                        
                        if df_adj_full is not None and not df_adj_full.empty:
                            success_count += 1
                            extract_data.insert_data(extract_data.DB_PATH, stock_code, df_adj_full)
                            extract_data.update_stock_info(conn, stock_code, df_adj_full, stock_name)
                    else:
                        new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                        
                        if not new_data.empty:
                            success_count += 1
                            extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                            extract_data.update_stock_info(conn, stock_code, new_data, stock_name)
                else:
                    new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                    
                    if not new_data.empty:
                        success_count += 1
                        extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                        extract_data.update_stock_info(conn, stock_code, new_data, stock_name)
            else:
                fail_count += 1
        
        if (i + 1) % 100 == 0 or i == total - 1:
            logger.info(f"更新进度: {i + 1}/{total} ({(i + 1)/total*100:.1f}%) - 成功: {success_count}, 失败: {fail_count}")
        
        time.sleep(extract_data.REQUEST_DELAY)
    
    conn.close()
    logger.info(f"数据更新完成: 成功 {success_count}, 失败 {fail_count}")


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


def run_filter(date: str, bandwidth_threshold: float = 10.0, proxy: Optional[str] = None, skip_update: bool = False) -> List[str]:
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
    
    logger.info("=" * 70)
    logger.info("筛选完成!")
    logger.info("=" * 70)
    logger.info(f"最终符合条件的股票列表 ({len(codes)} 只):")
    for i, code in enumerate(codes, 1):
        logger.info(f"  {i:3d}. {code}")
    
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
    parser.add_argument('--skip-update', action='store_true',
                        help='跳过数据更新步骤')
    
    args = parser.parse_args()
    
    if args.date:
        date = args.date
    else:
        date = datetime.now().strftime('%Y-%m-%d')
    
    result = run_filter(
        date, 
        bandwidth_threshold=args.bandwidth,
        proxy=args.proxy,
        skip_update=args.skip_update
    )
    
    return result


if __name__ == '__main__':
    main()
