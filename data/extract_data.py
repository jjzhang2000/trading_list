#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前复权价格获取工具
从新浪财经获取前复权价格数据并存储到SQLite数据库
"""

import os
import sys
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.logger import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = r'.'
DB_PATH = os.path.join(OUTPUT_DIR, 'data', 'stock_data.db')
YEARS = 5
REQUEST_DELAY = 0.3


class RealAdjustFactorFetcher:
    """前复权价格获取器（从东方财富）"""
    
    def __init__(self, proxy=None):
        self.session = None
        self.proxy = proxy
        self._init_session()
        
    def _init_session(self):
        """初始化HTTP会话"""
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        if self.proxy:
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            logger.info(f"使用代理: {self.proxy}")
    
    def fetch_adjust_factor_from_sina(self, stock_code: str) -> Optional[Dict]:
        """从新浪财经获取前复权因子"""
        try:
            import requests
            import re
            import json
            
            url = f'http://finance.sina.com.cn/realstock/company/sh{stock_code}/qfq.js'
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            content = response.text
            
            start_pos = content.find('{')
            end_pos = content.rfind('}')
            
            if start_pos == -1 or end_pos == -1:
                logger.warning("无法解析前复权因子数据")
                return None
            
            json_str = content[start_pos:end_pos+1]
            
            try:
                data = json.loads(json_str)
            except ValueError as e:
                logger.warning(f"前复权因子JSON解析失败: {e}")
                return None
            
            if 'data' not in data:
                logger.warning("前复权因子数据格式错误")
                return None
            
            factor_dict = {}
            for item in data['data']:
                date = item['d']
                factor = float(item['f'])
                factor_dict[date] = factor
            
            return factor_dict
            
        except Exception as e:
            logger.warning(f"获取前复权因子失败: {e}")
            return None
    
    def fetch_from_sina(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从新浪财经获取前复权价格"""
        try:
            import requests
            import pandas as pd
            
            factor_dict = self.fetch_adjust_factor_from_sina(stock_code)
            
            url = 'http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
            params = {
                'symbol': f'sh{stock_code}',
                'scale': 240,
                'datalen': 1825,
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError as e:
                logger.warning(f"新浪财经JSON解析失败: {e}")
                return None
            
            if not isinstance(data, list):
                logger.warning(f"新浪财经数据格式错误，期望列表，得到: {type(data)}")
                return None
            
            records = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                try:
                    date_str = item.get('day', '')
                    open_price = float(item.get('open', 0))
                    close_price = float(item.get('close', 0))
                    low_price = float(item.get('low', 0))
                    high_price = float(item.get('high', 0))
                    volume = float(item.get('volume', 0))
                    
                    if factor_dict:
                        adjust_factor = 1.0
                        for factor_date in sorted(factor_dict.keys(), reverse=True):
                            if factor_date <= date_str:
                                adjust_factor = factor_dict[factor_date]
                                break
                        
                        open_price /= adjust_factor
                        close_price /= adjust_factor
                        low_price /= adjust_factor
                        high_price /= adjust_factor
                    
                    records.append({
                        'date': date_str,
                        'open': open_price,
                        'close': close_price,
                        'low': low_price,
                        'high': high_price,
                        'volume': volume
                    })
                except (ValueError, KeyError) as e:
                    logger.debug(f"解析K线数据失败: {e}")
                    continue
            
            df = pd.DataFrame(records)
            if df.empty:
                return None
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.warning(f"新浪财经获取失败: {e}")
            return None
    
    def fetch_adjust_factor(self, stock_code: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], str]:
        """获取前复权价格"""
        df = self.fetch_from_sina(stock_code, start_date, end_date)
        if df is not None and not df.empty:
            return df, 'sina'
        
        return None, 'failed'


def create_database(db_path: str):
    """创建数据库"""
    data_dir = os.path.dirname(db_path)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"创建目录: {data_dir}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(stock_code, date)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_info (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            total_records INTEGER,
            start_date TEXT,
            end_date TEXT
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date ON stock_daily(stock_code, date)')
    
    conn.commit()
    conn.close()
    logger.info("数据库创建完成")


def insert_data(db_path: str, stock_code: str, df_price: pd.DataFrame):
    """插入数据"""
    if df_price.empty:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    price_records = []
    for _, row in df_price.iterrows():
        price_records.append((
            stock_code,
            row['date'].strftime('%Y-%m-%d') if isinstance(row['date'], datetime) else row['date'],
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            int(row['volume'])
        ))
    
    cursor.executemany('''
        INSERT OR REPLACE INTO stock_daily 
        (stock_code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', price_records)
    
    conn.commit()
    conn.close()


def get_stock_info(conn, stock_code):
    """获取股票在数据库中的信息"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT start_date, end_date, 
               (SELECT close FROM stock_daily 
                WHERE stock_code = ? AND date = end_date)
        FROM stock_info 
        WHERE stock_code = ?
    """, (stock_code, stock_code))
    result = cursor.fetchone()
    if result:
        return {
            'start_date': result[0],
            'end_date': result[1],
            'end_date_close': result[2]
        }
    return None


def update_stock_info(conn, stock_code, df, stock_name=''):
    """更新股票信息"""
    if df.empty:
        return
    
    cursor = conn.cursor()
    new_start_date = df['date'].min().strftime('%Y-%m-%d')
    new_end_date = df['date'].max().strftime('%Y-%m-%d')
    new_records = len(df)
    
    cursor.execute("SELECT start_date, total_records FROM stock_info WHERE stock_code = ?", (stock_code,))
    existing = cursor.fetchone()
    
    if existing:
        start_date = existing[0] if existing[0] else new_start_date
        total_records = (existing[1] or 0) + new_records
    else:
        start_date = new_start_date
        total_records = new_records
    
    cursor.execute("""
        INSERT OR REPLACE INTO stock_info 
        (stock_code, stock_name, total_records, start_date, end_date)
        VALUES (?, ?, ?, ?, ?)
    """, (stock_code, stock_name, total_records, start_date, new_end_date))
    conn.commit()


def get_sh_a_stock_list():
    """获取上证A股股票代码和名称列表（60开头）"""
    import requests
    
    logger.info("尝试从新浪财经API获取股票列表...")
    try:
        url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        all_stocks = []
        page = 1
        page_size = 80
        
        while True:
            params = {
                'page': page,
                'num': page_size,
                'sort': 'symbol',
                'asc': 1,
                'node': 'sh_a',
                'symbol': '',
                '_s_r_a': 'page'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            
            page_stocks = [(stock['code'], stock.get('name', '')) for stock in data if stock['code'].startswith('60')]
            all_stocks.extend(page_stocks)
            
            logger.debug(f"第{page}页: 获取 {len(page_stocks)} 只股票，累计 {len(all_stocks)} 只")
            
            if len(data) < page_size:
                break
            
            page += 1
            time.sleep(0.1)
        
        if all_stocks:
            seen = set()
            unique_stocks = []
            for code, name in all_stocks:
                if code not in seen:
                    seen.add(code)
                    unique_stocks.append((code, name))
            unique_stocks.sort(key=lambda x: x[0])
            logger.info(f"成功从新浪财经获取 {len(unique_stocks)} 只上证A股股票")
            return unique_stocks
    except Exception as e:
        logger.warning(f"新浪财经API失败: {e}")
    
    logger.error("所有API都失败，无法获取股票列表")
    return []


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='前复权价格获取工具')
    parser.add_argument('--proxy', type=str, default=None, help='代理服务器地址')
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("前复权价格获取工具")
    logger.info("=" * 70)
    logger.info(f"数据库: {DB_PATH}")
    logger.info(f"提取年限: {YEARS}年")
    if args.proxy:
        logger.info(f"代理服务器: {args.proxy}")
    logger.info("=" * 70)
    
    try:
        import requests
        logger.info("依赖检查通过")
    except ImportError as e:
        logger.error(f"缺少依赖: {e}")
        logger.info("请运行: pip install requests pandas numpy")
        return
    
    adj_fetcher = RealAdjustFactorFetcher(proxy=args.proxy)
    create_database(DB_PATH)
    
    logger.info("开始获取前复权价格数据...")
    
    logger.info("获取上证A股股票列表...")
    stock_codes = get_sh_a_stock_list()
    total = len(stock_codes)
    
    if total == 0:
        logger.error("没有获取到股票列表，程序退出")
        return
    
    logger.info(f"共处理 {total} 只上证A股")
    
    success_count = 0
    fail_count = 0
    source_stats = {'sina': 0, 'failed': 0}
    
    conn = sqlite3.connect(DB_PATH)
    
    for i, stock_code in enumerate(stock_codes):
        logger.debug(f"处理股票: {stock_code}")
        
        stock_info = get_stock_info(conn, stock_code)
        
        end_date = datetime.now()
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        if stock_info is None:
            logger.debug("数据库中无此股票，下载最近5年数据")
            start_date = end_date - timedelta(days=YEARS * 365)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code,
                start_date_str,
                end_date_str
            )
            
            source_stats[source] = source_stats.get(source, 0) + 1
            
            if df_adj is not None and not df_adj.empty:
                success_count += 1
                insert_data(DB_PATH, stock_code, df_adj)
                update_stock_info(conn, stock_code, df_adj)
                logger.debug(f"成功下载 {len(df_adj)} 条记录")
            else:
                fail_count += 1
                logger.debug("下载失败")
        else:
            logger.debug(f"数据库中已有此股票，最新日期: {stock_info['end_date']}")
            
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code,
                stock_info['end_date'],
                end_date_str
            )
            
            source_stats[source] = source_stats.get(source, 0) + 1
            
            if df_adj is not None and not df_adj.empty:
                end_date_data = df_adj[df_adj['date'] == stock_info['end_date']]
                
                if not end_date_data.empty:
                    source_close = end_date_data.iloc[0]['close']
                    db_close = stock_info['end_date_close']
                    
                    logger.debug(f"数据库收盘价: {db_close:.2f}, 数据源收盘价: {source_close:.2f}")
                    
                    if abs(source_close - db_close) > 0.01:
                        logger.debug("复权因子变动，重新下载所有数据")
                        start_date = end_date - timedelta(days=YEARS * 365)
                        start_date_str = start_date.strftime('%Y-%m-%d')
                        
                        df_adj_full, source_full = adj_fetcher.fetch_adjust_factor(
                            stock_code,
                            start_date_str,
                            end_date_str
                        )
                        
                        if df_adj_full is not None and not df_adj_full.empty:
                            success_count += 1
                            insert_data(DB_PATH, stock_code, df_adj_full)
                            update_stock_info(conn, stock_code, df_adj_full)
                            logger.debug(f"成功重新下载 {len(df_adj_full)} 条记录")
                        else:
                            fail_count += 1
                            logger.debug("重新下载失败")
                    else:
                        logger.debug("复权因子未变动，只添加新数据")
                        new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                        
                        if not new_data.empty:
                            success_count += 1
                            insert_data(DB_PATH, stock_code, new_data)
                            update_stock_info(conn, stock_code, new_data)
                            logger.debug(f"成功添加 {len(new_data)} 条新记录")
                        else:
                            logger.debug("无新数据")
                else:
                    logger.debug("数据源中无end_date当天数据，只添加新数据")
                    new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                    
                    if not new_data.empty:
                        success_count += 1
                        insert_data(DB_PATH, stock_code, new_data)
                        update_stock_info(conn, stock_code, new_data)
                        logger.debug(f"成功添加 {len(new_data)} 条新记录")
                    else:
                        logger.debug("无新数据")
            else:
                fail_count += 1
                logger.debug("下载失败")
        
        if (i + 1) % 100 == 0 or i == total - 1:
            logger.info(f"进度: {i + 1}/{total} ({(i + 1)/total*100:.1f}%) - 成功: {success_count}, 失败: {fail_count}")
        
        time.sleep(REQUEST_DELAY)
    
    conn.close()
    
    logger.info("=" * 70)
    logger.info("数据统计")
    logger.info("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM stock_daily')
    logger.info(f"总记录数: {cursor.fetchone()[0]:,}")
    
    cursor.execute('SELECT COUNT(DISTINCT stock_code) FROM stock_daily')
    logger.info(f"股票数量: {cursor.fetchone()[0]}")
    
    logger.info("数据来源统计:")
    for source, count in source_stats.items():
        logger.info(f"  {source}: {count}只股票")
    
    conn.close()
    
    logger.info("=" * 70)
    logger.info("数据提取完成!")
    logger.info(f"数据库文件: {DB_PATH}")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
