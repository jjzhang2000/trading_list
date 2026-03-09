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


def get_stock_price_on_date(stock_code: str, date: str, price_type: str = 'close') -> Optional[Tuple[float, int]]:
    """
    获取指定股票在指定日期的价格和交易量
    
    Args:
        stock_code: 股票代码（如：600000）
        date: 日期（YYYY-MM-DD格式）
        price_type: 价格类型，可选值：'open', 'high', 'low', 'close'，默认为'close'
    
    Returns:
        (价格, 交易量) 元组，如果数据不存在则返回None
    
    Example:
        >>> price, volume = get_stock_price_on_date('600000', '2025-03-07', 'close')
        >>> print(f"收盘价: {price}, 成交量: {volume}")
    """
    if price_type not in ['open', 'high', 'low', 'close']:
        raise ValueError(f"price_type必须是'open', 'high', 'low', 'close'之一，当前值: {price_type}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT {price_type}, volume
            FROM stock_daily
            WHERE stock_code = ? AND date = ?
        """, (stock_code, date))
        
        result = cursor.fetchone()
        
        if result:
            return (float(result[0]), int(result[1]))
        else:
            return None
    finally:
        conn.close()


def get_all_stocks_price_on_date(date: str, price_type: str = 'close') -> pd.DataFrame:
    """
    获取所有股票在指定日期的价格和交易量
    
    Args:
        date: 日期（YYYY-MM-DD格式）
        price_type: 价格类型，可选值：'open', 'high', 'low', 'close'，默认为'close'
    
    Returns:
        DataFrame，包含股票代码、价格、交易量
    
    Example:
        >>> df = get_all_stocks_price_on_date('2025-03-07', 'close')
        >>> print(df.head())
    """
    if price_type not in ['open', 'high', 'low', 'close']:
        raise ValueError(f"price_type必须是'open', 'high', 'low', 'close'之一，当前值: {price_type}")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = f"""
            SELECT stock_code, {price_type} as price, volume
            FROM stock_daily
            WHERE date = ?
            ORDER BY stock_code
        """
        
        df = pd.read_sql_query(query, conn, params=(date,))
        
        if not df.empty:
            df['price'] = df['price'].astype(float)
            df['volume'] = df['volume'].astype(int)
        
        return df
    finally:
        conn.close()


def get_stock_price_in_range(stock_code: str, start_date: str, end_date: str, price_type: str = 'close') -> pd.DataFrame:
    """
    获取指定股票在日期范围内的价格和交易量
    
    Args:
        stock_code: 股票代码（如：600000）
        start_date: 开始日期（YYYY-MM-DD格式）
        end_date: 结束日期（YYYY-MM-DD格式）
        price_type: 价格类型，可选值：'open', 'high', 'low', 'close'，默认为'close'
    
    Returns:
        DataFrame，包含日期、价格、交易量
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07', 'close')
        >>> print(df.head())
    """
    if price_type not in ['open', 'high', 'low', 'close']:
        raise ValueError(f"price_type必须是'open', 'high', 'low', 'close'之一，当前值: {price_type}")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = f"""
            SELECT date, {price_type} as price, volume
            FROM stock_daily
            WHERE stock_code = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        df = pd.read_sql_query(query, conn, params=(stock_code, start_date, end_date))
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['price'] = df['price'].astype(float)
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
    print("\n测试1：获取600000在2025-03-07的收盘价和交易量")
    result = get_stock_price_on_date('600000', '2025-03-07', 'close')
    if result:
        print(f"  收盘价: {result[0]:.2f}, 成交量: {result[1]:,}")
    else:
        print("  数据不存在")
    
    # 测试2：获取所有股票在指定日期的价格和交易量
    print("\n测试2：获取所有股票在2025-03-07的收盘价和交易量")
    df = get_all_stocks_price_on_date('2025-03-07', 'close')
    print(f"  获取到 {len(df)} 只股票的数据")
    print(df.head(10))
    
    # 测试3：获取指定股票在日期范围内的价格和交易量
    print("\n测试3：获取600000在2025-01-01到2025-03-07的收盘价和交易量")
    df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07', 'close')
    print(f"  获取到 {len(df)} 条数据")
    print(df.head(10))
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
