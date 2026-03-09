#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库读取模块
提供读取股票数据的函数
"""

import sqlite3
import pandas as pd
from typing import Optional, Tuple, List
from datetime import datetime


DB_PATH = r'.\data\stock_data.db'


def get_stock_price_on_date(stock_code: str, date: str) -> Optional[Tuple[float, float, float, float, int]]:
    """
    获取指定股票在指定日期的价格和交易量
    
    Args:
        stock_code: 股票代码（如：600000）
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        (开盘价, 最高价, 最低价, 收盘价, 交易量) 元组，如果数据不存在则返回None
    
    Example:
        >>> open_price, high_price, low_price, close_price, volume = get_stock_price_on_date('600000', '2025-03-07')
        >>> print(f"开盘价: {open_price}, 最高价: {high_price}, 最低价: {low_price}, 收盘价: {close_price}, 成交量: {volume}")
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT open, high, low, close, volume
            FROM stock_daily
            WHERE stock_code = ? AND date = ?
        """, (stock_code, date))
        
        result = cursor.fetchone()
        
        if result:
            return (float(result[0]), float(result[1]), float(result[2]), float(result[3]), int(result[4]))
        else:
            return None
    finally:
        conn.close()


def get_all_stocks_price_on_date(date: str) -> pd.DataFrame:
    """
    获取所有股票在指定日期的价格和交易量
    
    Args:
        date: 日期（YYYY-MM-DD格式）
    
    Returns:
        DataFrame，包含股票代码、开盘价、最高价、最低价、收盘价、交易量
    
    Example:
        >>> df = get_all_stocks_price_on_date('2025-03-07')
        >>> print(df.head())
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = """
            SELECT stock_code, open, high, low, close, volume
            FROM stock_daily
            WHERE date = ?
            ORDER BY stock_code
        """
        
        df = pd.read_sql_query(query, conn, params=(date,))
        
        if not df.empty:
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(int)
        
        return df
    finally:
        conn.close()


def get_stock_price_in_range(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取指定股票在日期范围内的价格和交易量
    
    Args:
        stock_code: 股票代码（如：600000）
        start_date: 开始日期（YYYY-MM-DD格式）
        end_date: 结束日期（YYYY-MM-DD格式）
    
    Returns:
        DataFrame，包含日期、开盘价、最高价、最低价、收盘价、交易量
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> print(df.head())
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = """
            SELECT date, open, high, low, close, volume
            FROM stock_daily
            WHERE stock_code = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        df = pd.read_sql_query(query, conn, params=(stock_code, start_date, end_date))
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(int)
        
        return df
    finally:
        conn.close()


def main():
    """测试函数"""
    print("=" * 70)
    print("测试数据库读取模块")
    print("=" * 70)
    
    # 测试1：获取指定股票在指定日期的价格和交易量
    print("\n测试1：获取600000在2025-03-07的价格和交易量")
    result = get_stock_price_on_date('600000', '2025-03-07')
    if result:
        print(f"  开盘价: {result[0]:.2f}, 最高价: {result[1]:.2f}, 最低价: {result[2]:.2f}, 收盘价: {result[3]:.2f}, 成交量: {result[4]:,}")
    else:
        print("  数据不存在")
    
    # 测试2：获取所有股票在指定日期的价格和交易量
    print("\n测试2：获取所有股票在2025-03-07的价格和交易量")
    df = get_all_stocks_price_on_date('2025-03-07')
    print(f"  获取到 {len(df)} 只股票的数据")
    print(df.head(10))
    
    # 测试3：获取指定股票在日期范围内的价格和交易量
    print("\n测试3：获取600000在2025-01-01到2025-03-07的价格和交易量")
    df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
    print(f"  获取到 {len(df)} 条数据")
    print(df.head(10))
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
