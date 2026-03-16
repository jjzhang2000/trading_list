#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量数据获取模块
使用新浪财经API批量获取股票数据，提高数据获取效率
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time
import requests
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stock_data.db')


class BatchDataFetcher:
    """批量数据获取器"""
    
    def __init__(self, proxy: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        })
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
            logger.info(f"使用代理: {proxy}")
    
    def fetch_realtime_batch(self, stock_codes: List[str], batch_size: int = 100) -> Dict[str, Dict]:
        """
        批量获取实时行情数据
        
        新浪接口支持一次请求多只股票，格式：
        http://hq.sinajs.cn/list=sh600000,sh600001,sh600002
        
        Args:
            stock_codes: 股票代码列表
            batch_size: 每批请求数量，默认100
        
        Returns:
            字典: {stock_code: {name, open, close, high, low, volume, ...}}
        """
        results = {}
        total = len(stock_codes)
        
        for i in range(0, total, batch_size):
            batch = stock_codes[i:i + batch_size]
            codes_str = ','.join([f'sh{code}' for code in batch])
            
            url = f'http://hq.sinajs.cn/list={codes_str}'
            
            try:
                response = self.session.get(url, timeout=10)
                response.encoding = 'gbk'
                text = response.text
                
                for line in text.split(';'):
                    if not line.strip():
                        continue
                    
                    if 'hq_str_sh' not in line:
                        continue
                    
                    try:
                        code_part = line.split('=')[0].replace('var hq_str_sh', '')
                        data_part = line.split('"')[1]
                        
                        if not data_part:
                            continue
                        
                        fields = data_part.split(',')
                        if len(fields) < 32:
                            continue
                        
                        stock_code = code_part
                        results[stock_code] = {
                            'name': fields[0],
                            'open': float(fields[1]) if fields[1] else 0,
                            'pre_close': float(fields[2]) if fields[2] else 0,
                            'close': float(fields[3]) if fields[3] else 0,
                            'high': float(fields[4]) if fields[4] else 0,
                            'low': float(fields[5]) if fields[5] else 0,
                            'volume': int(float(fields[8])) if fields[8] else 0,
                            'amount': float(fields[9]) if fields[9] else 0,
                            'date': fields[30],
                            'time': fields[31]
                        }
                    except (ValueError, IndexError) as e:
                        continue
                
                if (i + batch_size) < total:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.warning(f"批量获取实时行情失败: {e}")
        
        logger.info(f"批量获取实时行情完成: {len(results)}/{total}")
        return results
    
    def fetch_daily_kline_batch(self, stock_codes: List[str], 
                                  start_date: str, end_date: str,
                                  batch_size: int = 50) -> Dict[str, pd.DataFrame]:
        """
        批量获取日K线数据
        
        注意：新浪K线接口不支持批量，需要逐个获取
        但可以并发请求提高效率
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            batch_size: 并发请求数量
        
        Returns:
            字典: {stock_code: DataFrame}
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        total = len(stock_codes)
        
        def fetch_single(code: str) -> Tuple[str, Optional[pd.DataFrame]]:
            try:
                url = 'http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
                params = {
                    'symbol': f'sh{code}',
                    'scale': 240,
                    'datalen': 800
                }
                
                response = self.session.get(url, params=params, timeout=15)
                data = response.json()
                
                if not isinstance(data, list):
                    return code, None
                
                records = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    try:
                        date_str = item.get('day', '')
                        if start_date <= date_str <= end_date:
                            records.append({
                                'date': date_str,
                                'open': float(item.get('open', 0)),
                                'close': float(item.get('close', 0)),
                                'high': float(item.get('high', 0)),
                                'low': float(item.get('low', 0)),
                                'volume': float(item.get('volume', 0))
                            })
                    except (ValueError, KeyError):
                        continue
                
                if records:
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    return code, df
                return code, None
                
            except Exception as e:
                return code, None
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_single, code): code for code in stock_codes}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                code, df = future.result()
                if df is not None:
                    results[code] = df
                
                if completed % 50 == 0:
                    logger.info(f"  K线数据获取进度: {completed}/{total}")
        
        logger.info(f"批量获取K线数据完成: {len(results)}/{total}")
        return results


def update_daily_data_batch(stock_codes: List[str] = None, proxy: str = None):
    """
    批量更新每日数据
    
    使用实时行情接口批量获取当日数据，效率更高
    
    Args:
        stock_codes: 股票代码列表，为None则获取所有上证A股
        proxy: 代理服务器
    """
    if stock_codes is None:
        from data.extract_data import get_sh_a_stock_list
        stock_list = get_sh_a_stock_list()
        stock_codes = [code for code, _ in stock_list]
    
    fetcher = BatchDataFetcher(proxy=proxy)
    
    logger.info(f"开始批量更新 {len(stock_codes)} 只股票的当日数据...")
    
    realtime_data = fetcher.fetch_realtime_batch(stock_codes)
    
    if not realtime_data:
        logger.warning("未获取到任何实时数据")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    updated_count = 0
    
    for code, data in realtime_data.items():
        if data['close'] <= 0:
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO stock_daily 
                (stock_code, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (code, today, data['open'], data['high'], 
                  data['low'], data['close'], data['volume']))
            
            cursor.execute('''
                INSERT OR REPLACE INTO stock_info 
                (stock_code, stock_name, end_date)
                VALUES (?, ?, ?)
            ''', (code, data['name'], today))
            
            updated_count += 1
            
        except Exception as e:
            logger.debug(f"更新 {code} 失败: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"批量更新完成: 更新 {updated_count} 只股票的当日数据")


def main():
    """测试函数"""
    logger.info("=" * 70)
    logger.info("测试批量数据获取模块")
    logger.info("=" * 70)
    
    test_codes = ['600000', '600036', '600519']
    
    fetcher = BatchDataFetcher()
    
    logger.info("测试批量获取实时行情...")
    realtime = fetcher.fetch_realtime_batch(test_codes)
    for code, data in realtime.items():
        logger.info(f"  {code} {data['name']}: 收盘价={data['close']:.2f}")
    
    logger.info("=" * 70)
    logger.info("测试完成")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
