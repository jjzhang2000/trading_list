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

    def _request_with_retry(self, url: str, params: Optional[dict] = None,
                            timeout: int = 30, max_retries: int = 3) -> Optional['requests.Response']:
        """
        带重试的HTTP GET请求。

        新浪接口会偶发主动断开连接（RemoteDisconnected）或在并发下复用
        已失效的keep-alive连接，重试并重建会话可显著降低失败率。

        Args:
            url: 请求地址
            params: URL查询参数
            timeout: 超时秒数
            max_retries: 最大重试次数（含首次）
        Returns:
            Response；所有重试失败后抛异常
        """
        for attempt in range(max_retries):
            if attempt > 0:
                # 连接可能已被服务端关闭，重建会话并使用退避延迟
                self._init_session()
                time.sleep(0.5 * attempt)
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"请求失败，重试中({attempt + 1}/{max_retries - 1}): {e}")
        return None

    def fetch_adjust_factor_from_sina(self, stock_code: str) -> Optional[Dict]:
        """从新浪财经获取前复权因子"""
        try:
            import re
            import json
            
            url = f'http://finance.sina.com.cn/realstock/company/sh{stock_code}/qfq.js'
            
            response = self._request_with_retry(url, timeout=30)
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
    
    def fetch_from_sina(self, stock_code: str, start_date: str, end_date: str,
                        datalen: int = 1825) -> Optional[pd.DataFrame]:
        """从新浪财经获取前复权价格"""
        try:
            import pandas as pd
            
            # ETF不需要前复权处理（极少分红拆股）
            if stock_code.startswith('5'):
                factor_dict = None
            else:
                factor_dict = self.fetch_adjust_factor_from_sina(stock_code)
            
            url = 'http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
            params = {
                'symbol': f'sh{stock_code}',
                'scale': 240,
                'datalen': datalen,
            }
            
            response = self._request_with_retry(url, params=params, timeout=30)
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
    
    def fetch_adjust_factor(self, stock_code: str, start_date: str, end_date: str,
                            datalen: int = 1825) -> Tuple[Optional[pd.DataFrame], str]:
        """获取前复权价格"""
        df = self.fetch_from_sina(stock_code, start_date, end_date, datalen=datalen)
        if df is not None and not df.empty:
            return df, 'sina'
        
        return None, 'failed'

    def fetch_incremental(self, stock_code: str, info: Optional[Dict], start_date: str,
                          end_date: str, datalen: int = 50) -> Tuple[Optional[pd.DataFrame], str]:
        """
        根据数据库现有信息增量获取数据。

        - 数据库中无此股票：全量下载（5年数据）
        - 已有股票：先用少量数据（datalen条）判断复权因子是否变动
          - 因子未变：只返回 end_date 之后的新数据
          - 因子变动：全量重新下载

        Args:
            stock_code: 股票代码
            info: 数据库中的现有信息（get_stock_info 的返回值），无则为 None
            start_date: 全量下载起始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            datalen: 增量判断时请求的最近数据条数
        Returns:
            (待写入的DataFrame, 数据源)；失败返回 (None, 'failed')
        """
        if info is None:
            return self.fetch_adjust_factor(stock_code, start_date, end_date, datalen=1825)

        df_small = self.fetch_from_sina(stock_code, info['end_date'], end_date,
                                        datalen=datalen)
        if df_small is None or df_small.empty:
            return None, 'failed'
        source = 'sina'

        end_ts = pd.to_datetime(info['end_date'])
        end_data = df_small[df_small['date'] == end_ts]

        if end_data.empty:
            # 停牌等导致数据库最新日期不在最近数据中，回退全量再截取新数据
            df_full, source = self.fetch_adjust_factor(stock_code, start_date, end_date,
                                                       datalen=1825)
            if df_full is None or df_full.empty:
                return None, source
            return df_full[df_full['date'] > end_ts], source

        source_close = end_data.iloc[0]['close']
        db_close = info.get('end_date_close')
        if db_close is not None and abs(source_close - db_close) > 0.01:
            # 复权因子变动，全量重新下载
            return self.fetch_adjust_factor(stock_code, start_date, end_date, datalen=1825)

        return df_small[df_small['date'] > end_ts], source


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


def update_all_stock_data(stock_list: List[tuple], start_date: str, end_date: str,
                          proxy: Optional[str] = None, max_workers: int = 3,
                          progress_cb=None, incremental_datalen: int = 50,
                          request_delay: float = 0.2) -> Tuple[int, int, Dict]:
    """
    并发下载所有股票价格数据并写入数据库。

    网络请求（I/O密集型）使用线程池并发执行，大幅提升提取速度；
    数据库写入在主线程串行执行，避免SQLite并发写入冲突。
    每只股票通过 fetch_incremental 自动判断全量下载或增量更新，
    日常增量更新只拉取最近 incremental_datalen 条数据。
    每个worker线程每完成一只股票后停顿 request_delay 秒，
    控制整体请求频率，降低被数据源屏蔽的风险。

    Args:
        stock_list: [(stock_code, stock_name), ...]
        start_date: 全量下载起始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        proxy: HTTP代理
        max_workers: 并发下载线程数
        progress_cb: 进度回调 callback(done, total, success, fail, message)
        incremental_datalen: 增量更新时请求的最近数据条数
        request_delay: 每个线程每完成一只股票后的停顿秒数
    Returns:
        (success_count, fail_count, source_stats)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    create_database(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    # 预加载现有股票信息（只读，供各线程判断增量/全量）
    info_map: Dict[str, Dict] = {}
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT si.stock_code, si.start_date, si.end_date,
                   (SELECT close FROM stock_daily
                    WHERE stock_code = si.stock_code AND date = si.end_date)
            FROM stock_info si
        """)
        for code, start, db_end, close in cursor.fetchall():
            info_map[code] = {
                'start_date': start,
                'end_date': db_end,
                'end_date_close': close,
            }
        cursor.close()
    except Exception as e:
        logger.warning(f"预加载股票信息失败: {e}")

    total = len(stock_list)
    success_count = 0
    fail_count = 0
    source_stats: Dict[str, int] = {}
    done_count = 0

    def fetch_one(item: tuple) -> tuple:
        """单个股票的下载任务（仅网络请求，在worker线程执行）"""
        code, name = item
        info = info_map.get(code)
        fetcher = RealAdjustFactorFetcher(proxy=proxy)
        try:
            df, source = fetcher.fetch_incremental(code, info, start_date, end_date,
                                                   datalen=incremental_datalen)
            return code, name, df, source
        except Exception as e:
            logger.warning(f"股票 {code} 获取失败: {e}")
            return code, name, None, 'failed'
        finally:
            # 线程级节流：每完成一只股票停顿一小会儿，降低请求频率
            time.sleep(request_delay)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, item): item for item in stock_list}
        for future in as_completed(futures):
            code, name, df, source = future.result()
            source_stats[source] = source_stats.get(source, 0) + 1

            if df is not None and not df.empty:
                try:
                    insert_data(DB_PATH, code, df)
                    update_stock_info(conn, code, df, name)
                    success_count += 1
                except Exception as e:
                    logger.warning(f"股票 {code} 写入数据库失败: {e}")
                    fail_count += 1
            elif source == 'failed':
                fail_count += 1
            # 其余情况：无新数据，不计数

            done_count += 1
            if progress_cb:
                progress_cb(done_count, total, success_count, fail_count,
                            f"进度: {done_count}/{total} ({done_count / total * 100:.1f}%) "
                            f"- 成功: {success_count}, 失败: {fail_count}")

    conn.close()
    return success_count, fail_count, source_stats


def get_sh_etf_list():
    """获取上证ETF指数代码和名称列表（5开头）"""
    import requests
    
    logger.info("尝试从新浪财经API获取上证ETF列表...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://finance.sina.com.cn/'
    }
    
    # 方法1: 使用JSONP端点（akshare验证可用，节点为 etf_hq_fund）
    try:
        url = ('https://vip.stock.finance.sina.com.cn/quotes_service/api/jsonp.php/'
               'IO.XSRV2.CallbackList[\'hq_list\']/Market_Center.getHQNodeDataSimple')
        params = {
            'page': 1,
            'num': 5000,
            'sort': 'symbol',
            'asc': 1,
            'node': 'etf_hq_fund',
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        text = response.text
        
        # JSONP格式: IO.XSRV2.CallbackList['hq_list']([{...}, {...}])
        json_start = text.find('([')
        json_end = text.rfind('])')
        
        if json_start != -1 and json_end != -1:
            json_str = text[json_start + 1:json_end + 1]
            data = json.loads(json_str)
            
            if isinstance(data, list):
                all_etfs = []
                for item in data:
                    # code字段已经是纯代码（如510050），symbol字段带前缀（如sh510050）
                    code = item.get('code', '')
                    
                    if code.startswith('5'):
                        all_etfs.append((code, item.get('name', '')))
                
                if all_etfs:
                    seen = set()
                    unique_etfs = []
                    for code, name in all_etfs:
                        if code not in seen:
                            seen.add(code)
                            unique_etfs.append((code, name))
                    unique_etfs.sort(key=lambda x: x[0])
                    logger.info(f"成功从新浪财经获取 {len(unique_etfs)} 只上证ETF")
                    return unique_etfs
    except Exception as e:
        logger.warning(f"新浪财经ETF JSONP API失败: {e}")
    
    # 方法2: 回退到json_v2端点尝试
    try:
        url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        params = {
            'page': 1,
            'num': 5000,
            'sort': 'symbol',
            'asc': 1,
            'node': 'etf_hq_fund',
            'symbol': '',
            '_s_r_a': 'page'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        data = response.json()
        
        if isinstance(data, list):
            all_etfs = []
            for item in data:
                code = item.get('code', '')
                
                if code.startswith('5'):
                    all_etfs.append((code, item.get('name', '')))
            
            if all_etfs:
                seen = set()
                unique_etfs = []
                for code, name in all_etfs:
                    if code not in seen:
                        seen.add(code)
                        unique_etfs.append((code, name))
                unique_etfs.sort(key=lambda x: x[0])
                logger.info(f"成功从新浪财经获取 {len(unique_etfs)} 只上证ETF")
                return unique_etfs
    except Exception as e:
        logger.warning(f"新浪财经ETF JSON API失败: {e}")
    
    logger.warning("无法获取ETF列表")
    return []


def get_sh_a_stock_list():
    """获取上证A股股票和ETF指数代码和名称列表（60开头股票 + 5开头ETF）"""
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
            
            page_stocks = [(stock['code'], stock.get('name', '')) for stock in data if stock['code'].startswith(('60', '5'))]
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
            
            # 获取ETF列表并合并
            etf_list = get_sh_etf_list()
            if etf_list:
                unique_stocks.extend(etf_list)
                unique_stocks.sort(key=lambda x: x[0])
                logger.info(f"合并ETF后共 {len(unique_stocks)} 只证券（股票+ETF）")
            
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
    
    create_database(DB_PATH)
    
    logger.info("开始获取前复权价格数据...")
    
    logger.info("获取上证A股股票列表...")
    stock_codes = get_sh_a_stock_list()
    total = len(stock_codes)
    
    if total == 0:
        logger.error("没有获取到股票列表，程序退出")
        return
    
    logger.info(f"共处理 {total} 只上证A股及ETF")
    logger.info("使用并发下载（默认3线程，无需逐只等待）...")

    end_date = datetime.now()
    end_date_str = end_date.strftime('%Y-%m-%d')
    start_date = end_date - timedelta(days=YEARS * 365)
    start_date_str = start_date.strftime('%Y-%m-%d')

    def progress(done, total_cnt, success, fail, message):
        if done % 100 == 0 or done == total_cnt:
            logger.info(message)

    success_count, fail_count, source_stats = update_all_stock_data(
        stock_codes, start_date_str, end_date_str,
        proxy=args.proxy, max_workers=3, progress_cb=progress
    )

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
