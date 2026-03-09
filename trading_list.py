#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票筛选主程序（命令行版本）

功能说明：
    读取所有股票代码，依次经过多个技术指标筛选，输出符合条件的股票列表。

筛选流程：
    1. 更新股票数据（可选跳过）
       - 从新浪财经获取上证A股股票列表
       - 增量更新每只股票的前复权价格数据
       - 自动检测复权因子变动并重新下载

    2. 技术指标筛选（依次执行）
       - SuperTrend筛选：保留多头趋势股票
       - Vegas通道筛选：保留EMA多头排列股票
       - 布林带筛选：保留开口率超过阈值的股票
       - OCC指标筛选：保留多头趋势股票
       - VP Slope筛选：保留斜率大于0的股票

使用方法：
    # 默认：更新数据后筛选今天的股票
    python trading_list.py
    
    # 指定日期筛选
    python trading_list.py -d 2025-03-07
    
    # 使用代理更新数据
    python trading_list.py -p http://127.0.0.1:7890
    
    # 跳过数据更新，直接筛选
    python trading_list.py --skip-update

命令行参数：
    -d, --date        筛选日期（YYYY-MM-DD格式，默认为今天）
    -b, --bandwidth   布林带开口率阈值（默认10.0）
    -p, --proxy       代理服务器地址
    --skip-update     跳过数据更新步骤
"""

import argparse
from datetime import datetime
from typing import List, Optional

from data.read_data import get_all_stock_codes
from data import extract_data
from tech import supertrend, vegas, bollingerband, occross, vp_slope


def update_stock_data(proxy: Optional[str] = None):
    """
    更新股票数据
    
    从新浪财经获取上证A股股票列表，并增量更新每只股票的前复权价格数据。
    支持复权因子变动检测，当检测到变动时自动重新下载所有历史数据。
    
    Args:
        proxy: 代理服务器地址，例如 'http://127.0.0.1:7890'
    
    算法逻辑：
        1. 初始化HTTP会话和数据库
        2. 获取上证A股股票列表（60开头）
        3. 对每只股票：
           a. 如果数据库中没有该股票，下载最近5年的所有数据
           b. 如果数据库中已有该股票：
              - 获取最新数据
              - 比较end_date当天的收盘价，判断复权因子是否变动
              - 如果变动，重新下载所有历史数据
              - 如果未变动，只添加新数据
        4. 添加请求延迟避免API限制
    """
    print("\n" + "=" * 70)
    print("更新股票数据...")
    print("=" * 70)
    
    adj_fetcher = extract_data.RealAdjustFactorFetcher(proxy=proxy)
    extract_data.create_database(extract_data.DB_PATH)
    
    stock_list = extract_data.get_sh_a_stock_list()
    total = len(stock_list)
    
    if total == 0:
        print("没有获取到股票列表，跳过数据更新")
        return
    
    print(f"共需更新 {total} 只股票\n")
    
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
            print(f"  更新进度: {i + 1}/{total} ({(i + 1)/total*100:.1f}%) - 成功: {success_count}, 失败: {fail_count}")
        
        time.sleep(extract_data.REQUEST_DELAY)
    
    conn.close()
    print(f"\n数据更新完成: 成功 {success_count}, 失败 {fail_count}")


def filter_by_supertrend(date: str, stock_codes: List[str]) -> List[str]:
    """
    SuperTrend筛选
    
    筛选出处于多头趋势（trend_direction=1）的股票。
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        stock_codes: 待筛选的股票代码列表
    
    Returns:
        筛选后的股票代码列表
    
    算法说明：
        SuperTrend是一种趋势跟踪指标，基于ATR（平均真实波幅）计算。
        当价格在SuperTrend线之上时为多头趋势，反之为空头趋势。
    """
    print(f"\n[1/5] SuperTrend筛选 - 输入: {len(stock_codes)} 只股票")
    df = supertrend.filter_bullish_stocks(date, stock_codes=stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    print(f"       SuperTrend筛选 - 输出: {len(result)} 只股票 (多头趋势)")
    return result


def filter_by_vegas(date: str, stock_codes: List[str]) -> List[str]:
    """
    Vegas通道筛选
    
    筛选出EMA呈多头排列（EMA5 > EMA8 > EMA12 > EMA26 > EMA144 > EMA169）的股票。
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        stock_codes: 待筛选的股票代码列表
    
    Returns:
        筛选后的股票代码列表
    
    算法说明：
        Vegas通道由多条EMA组成，通过不同周期的EMA排列来判断趋势。
        当所有EMA从上到下依次排列时为多头趋势，反之为空头趋势。
    """
    print(f"\n[2/5] Vegas通道筛选 - 输入: {len(stock_codes)} 只股票")
    df = vegas.filter_bullish_stocks(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    print(f"       Vegas通道筛选 - 输出: {len(result)} 只股票 (多头排列)")
    return result


def filter_by_bollingerband(date: str, stock_codes: List[str], threshold: float = 10.0) -> List[str]:
    """
    布林带筛选
    
    筛选出布林带开口率超过阈值的股票。
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        stock_codes: 待筛选的股票代码列表
        threshold: 开口率阈值（百分比），默认10.0
    
    Returns:
        筛选后的股票代码列表
    
    算法说明：
        布林带由中轨（移动平均线）和上下轨（中轨±N倍标准差）组成。
        开口率 = (上轨 - 下轨) / 中轨 × 100%
        开口率扩大通常预示着趋势的开始。
    """
    print(f"\n[3/5] 布林带筛选 - 输入: {len(stock_codes)} 只股票 (开口率阈值: {threshold}%)")
    df = bollingerband.filter_stocks_by_bandwidth(date, stock_codes, threshold=threshold)
    result = df['stock_code'].tolist() if not df.empty else []
    print(f"       布林带筛选 - 输出: {len(result)} 只股票 (开口率>{threshold}%)")
    return result


def filter_by_occross(date: str, stock_codes: List[str]) -> List[str]:
    """
    OCC指标筛选
    
    筛选出OCC指标呈多头趋势（occ_close > occ_open）的股票。
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        stock_codes: 待筛选的股票代码列表
    
    Returns:
        筛选后的股票代码列表
    
    算法说明：
        OCC指标通过比较开盘价和收盘价的移动平均线来判断趋势。
        当收盘价的MA高于开盘价的MA时为多头趋势。
    """
    print(f"\n[4/5] OCC指标筛选 - 输入: {len(stock_codes)} 只股票")
    df = occross.filter_bullish_stocks(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    print(f"       OCC指标筛选 - 输出: {len(result)} 只股票 (多头趋势)")
    return result


def filter_by_vp_slope(date: str, stock_codes: List[str]) -> List[str]:
    """
    VP Slope筛选
    
    筛选出长期斜率大于0的股票。
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        stock_codes: 待筛选的股票代码列表
    
    Returns:
        筛选后的股票代码列表
    
    算法说明：
        Slope指标通过线性回归计算价格趋势的斜率。
        斜率大于0表示上升趋势，小于0表示下降趋势。
    """
    print(f"\n[5/5] VP Slope筛选 - 输入: {len(stock_codes)} 只股票")
    df = vp_slope.filter_stocks_by_slope(date, stock_codes)
    result = df['stock_code'].tolist() if not df.empty else []
    print(f"       VP Slope筛选 - 输出: {len(result)} 只股票 (斜率>0)")
    return result


def run_filter(date: str, bandwidth_threshold: float = 10.0, proxy: Optional[str] = None, skip_update: bool = False) -> List[str]:
    """
    执行完整的股票筛选流程
    
    Args:
        date: 筛选日期（YYYY-MM-DD格式）
        bandwidth_threshold: 布林带开口率阈值，默认10.0
        proxy: 代理服务器地址
        skip_update: 是否跳过数据更新步骤
    
    Returns:
        筛选后的股票代码列表
    
    流程说明：
        1. 更新股票数据（可选跳过）
        2. 获取所有股票代码
        3. 依次执行5个筛选器
        4. 输出最终结果
    """
    print("=" * 70)
    print(f"股票筛选主程序 - 筛选日期: {date}")
    print("=" * 70)
    
    if not skip_update:
        update_stock_data(proxy=proxy)
    
    print("\n获取所有股票代码...")
    all_codes = get_all_stock_codes()
    print(f"共有 {len(all_codes)} 只股票")
    
    codes = all_codes
    
    codes = filter_by_supertrend(date, codes)
    if not codes:
        print("\n筛选结果为空，程序结束")
        return []
    
    codes = filter_by_vegas(date, codes)
    if not codes:
        print("\n筛选结果为空，程序结束")
        return []
    
    codes = filter_by_bollingerband(date, codes, threshold=bandwidth_threshold)
    if not codes:
        print("\n筛选结果为空，程序结束")
        return []
    
    codes = filter_by_occross(date, codes)
    if not codes:
        print("\n筛选结果为空，程序结束")
        return []
    
    codes = filter_by_vp_slope(date, codes)
    if not codes:
        print("\n筛选结果为空，程序结束")
        return []
    
    print("\n" + "=" * 70)
    print("筛选完成!")
    print("=" * 70)
    print(f"\n最终符合条件的股票列表 ({len(codes)} 只):")
    print("-" * 70)
    for i, code in enumerate(codes, 1):
        print(f"  {i:3d}. {code}")
    print("-" * 70)
    
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
