#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库读取模块
提供读取股票数据的函数
"""

import sqlite3
import pandas as pd
from typing import Optional, List
from datetime import datetime


DB_PATH = r'.\data\stock_data.db'


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


def get_stock_price_before_date(stock_code: str, end_date: str, limit: int) -> pd.DataFrame:
    """
    获取指定股票在结束日期之前的N条数据
    
    Args:
        stock_code: 股票代码（如：600000）
        end_date: 结束日期（YYYY-MM-DD格式）
        limit: 获取的数据条数
    
    Returns:
        DataFrame，包含日期、开盘价、最高价、最低价、收盘价、交易量
    
    Example:
        >>> df = get_stock_price_before_date('600000', '2025-03-07', 100)
        >>> print(df.head())
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = """
            SELECT date, open, high, low, close, volume
            FROM stock_daily
            WHERE stock_code = ? AND date <= ?
            ORDER BY date DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=(stock_code, end_date, limit))
        
        if not df.empty:
            df = df.iloc[::-1].reset_index(drop=True)
            df['date'] = pd.to_datetime(df['date'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(int)
        
        return df
    finally:
        conn.close()


def get_stock_name(stock_code: str) -> Optional[str]:
    """
    获取股票名称
    
    Args:
        stock_code: 股票代码（如：600000）
    
    Returns:
        股票名称，如果不存在则返回None
    
    Example:
        >>> name = get_stock_name('600000')
        >>> print(name)
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_name FROM stock_info WHERE stock_code = ?", (stock_code,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()


def get_all_stock_codes() -> List[str]:
    """
    获取所有股票代码
    
    Returns:
        股票代码列表
    
    Example:
        >>> codes = get_all_stock_codes()
        >>> print(f"共有 {len(codes)} 只股票")
        >>> print(codes[:10])
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT stock_code
            FROM stock_daily
            ORDER BY stock_code
        """)
        
        codes = [row[0] for row in cursor.fetchall()]
        return codes
    finally:
        conn.close()


def get_indicator(stock_code: str, date: str, column: str) -> Optional[int]:
    """
    从 stock_indicators 表获取指定股票的某个指标值

    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）
        column: 指标列名（如 'supertrend'）

    Returns:
        指标值（int，-100到100），不存在返回None
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {column} FROM stock_indicators WHERE stock_code = ? AND date = ?",
            (stock_code, date)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else None
    finally:
        conn.close()


def get_latest_trading_dates(stock_code: str, limit: int = 2) -> List[str]:
    """
    获取指定股票最近的N个交易日日期（按日期降序）

    Args:
        stock_code: 股票代码（如：600000）
        limit: 获取的最近交易日数量，默认为2

    Returns:
        日期字符串列表（YYYY-MM-DD格式），按日期降序排列
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT date FROM stock_daily WHERE stock_code = ? "
            "ORDER BY date DESC LIMIT ?",
            (stock_code, limit)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def save_indicator(stock_code: str, date: str, column: str, value: int):
    """
    保存单个指标值到 stock_indicators 表（upsert，不影响同行的其他列）

    Args:
        stock_code: 股票代码
        date: 日期（YYYY-MM-DD格式）
        column: 指标列名
        value: int值，会被 clamp 到 [-100, 100]
    """
    value = max(-100, min(100, int(value)))
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO stock_indicators (stock_code, date, {column}) VALUES (?, ?, ?) "
            f"ON CONFLICT(stock_code, date) DO UPDATE SET {column} = excluded.{column}",
            (stock_code, date, value)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_stock_codes_with_names() -> List[tuple]:
    """
    获取所有股票代码和名称
    
    Returns:
        (股票代码, 股票名称) 元组列表，按股票代码升序排序
    
    Example:
        >>> stocks = get_all_stock_codes_with_names()
        >>> print(f"共有 {len(stocks)} 只股票")
        >>> for code, name in stocks[:10]:
        >>>     print(f"{code} - {name}")
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT sd.stock_code, COALESCE(si.stock_name, '') as stock_name
            FROM stock_daily sd
            LEFT JOIN stock_info si ON sd.stock_code = si.stock_code
            ORDER BY sd.stock_code
        """)
        
        stocks = [(row[0], row[1]) for row in cursor.fetchall()]
        return stocks
    finally:
        conn.close()


def main():
    """测试函数"""
    print("=" * 70)
    print("测试数据库读取模块")
    print("=" * 70)

    # 测试：获取指定股票在日期范围内的价格和交易量
    print("\n测试：获取600000在2025-01-01到2025-03-07的价格和交易量")
    df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
    print(f"  获取到 {len(df)} 条数据")
    print(df.head(10))

    # 测试：获取所有股票代码
    print("\n测试：获取所有股票代码")
    codes = get_all_stock_codes()
    print(f"  共有 {len(codes)} 只股票")
    print(f"  前10只股票: {codes[:10]}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
