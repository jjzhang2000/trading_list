#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化工具
如果股票数据库存在，则清除其中的所有历史数据；如果数据库不存在，则新建这个数据库

使用方法:
    python data/init_db.py
"""

import os
import sqlite3
from pathlib import Path

# ==================== 配置 ====================
OUTPUT_DIR = r'.'
DB_PATH = os.path.join(OUTPUT_DIR, 'data', 'stock_data.db')


def init_database():
    """初始化数据库"""
    print("=" * 70)
    print("数据库初始化工具")
    print("=" * 70)
    print(f"数据库路径: {DB_PATH}")
    print("=" * 70)
    
    # 确保data目录存在
    data_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"创建目录: {data_dir}")
    
    # 检查数据库是否存在
    db_exists = os.path.exists(DB_PATH)
    
    if db_exists:
        print("数据库已存在，正在清除历史数据...")
    else:
        print("数据库不存在，正在创建新数据库...")
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 删除现有表（如果存在）
    cursor.execute('DROP TABLE IF EXISTS stock_daily')
    cursor.execute('DROP TABLE IF EXISTS stock_info')
    
    # 创建股票日线数据表（前复权价格）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,      -- 前复权开盘价
            high REAL,      -- 前复权最高价
            low REAL,       -- 前复权最低价
            close REAL,     -- 前复权收盘价
            volume INTEGER, -- 成交量
            UNIQUE(stock_code, date)
        )
    ''')
    
    # 创建股票信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_info (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            total_records INTEGER,
            start_date TEXT,
            end_date TEXT
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date ON stock_daily(stock_code, date)')
    
    conn.commit()
    conn.close()
    
    if db_exists:
        print("历史数据清除完成！")
    else:
        print("数据库创建完成！")
    
    print("=" * 70)
    print("数据库初始化完成!")
    print(f"数据库文件: {DB_PATH}")
    print("=" * 70)


def main():
    """主函数"""
    init_database()


if __name__ == '__main__':
    main()
