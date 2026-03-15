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


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算Heikin-Ashi（平均K线）价格序列
    
    Args:
        df: DataFrame，必须包含列：open, high, low, close
    
    Returns:
        DataFrame，包含列：ha_open, ha_high, ha_low, ha_close
    
    计算公式：
        HA收盘价 = (开盘价 + 最高价 + 最低价 + 收盘价) / 4
        HA开盘价 = (前一日HA开盘价 + 前一日HA收盘价) / 2
        HA最高价 = max(最高价, HA开盘价, HA收盘价)
        HA最低价 = min(最低价, HA开盘价, HA收盘价)
    
    Example:
        >>> df = get_stock_price_in_range('600000', '2025-01-01', '2025-03-07')
        >>> ha_df = calculate_heikin_ashi(df)
        >>> print(ha_df.head())
    """
    if df.empty:
        return pd.DataFrame()
    
    ha_df = pd.DataFrame()
    
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    ha_df['ha_open'] = 0.0
    ha_df.loc[df.index[0], 'ha_open'] = (df.loc[df.index[0], 'open'] + df.loc[df.index[0], 'close']) / 2
    
    for i in range(1, len(df)):
        ha_df.loc[df.index[i], 'ha_open'] = (ha_df.loc[df.index[i-1], 'ha_open'] + ha_df.loc[df.index[i-1], 'ha_close']) / 2
    
    ha_df['ha_high'] = ha_df[['ha_open', 'ha_close']].max(axis=1)
    ha_df['ha_high'] = ha_df[['ha_high']].max(axis=1)
    ha_df.loc[:, 'ha_high'] = pd.concat([df['high'], ha_df['ha_open'], ha_df['ha_close']], axis=1).max(axis=1)
    
    ha_df['ha_low'] = ha_df[['ha_open', 'ha_close']].min(axis=1)
    ha_df.loc[:, 'ha_low'] = pd.concat([df['low'], ha_df['ha_open'], ha_df['ha_close']], axis=1).min(axis=1)
    
    if 'date' in df.columns:
        ha_df['date'] = df['date']
    
    return ha_df


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
    
    # 测试4：计算Heikin-Ashi平均K线
    print("\n测试4：计算600000的Heikin-Ashi平均K线")
    ha_df = calculate_heikin_ashi(df)
    print(f"  获取到 {len(ha_df)} 条Heikin-Ashi数据")
    print(ha_df.head(10))
    
    # 测试5：获取所有股票代码
    print("\n测试5：获取所有股票代码")
    codes = get_all_stock_codes()
    print(f"  共有 {len(codes)} 只股票")
    print(f"  前10只股票: {codes[:10]}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
