#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前复权价格获取工具
从新浪财经获取前复权价格数据并存储到SQLite数据库

算法逻辑:
1. 前复权价格获取流程:
   - 初始化HTTP会话，设置User-Agent避免被API限制
   - 从新浪财经获取前复权因子
   - 从新浪财经获取不复权的原始K线数据
   - 应用前复权因子计算前复权价格
   - 返回前复权价格数据和数据源标识

2. 新浪财经前复权因子获取算法:
   - 访问新浪财经前复权因子API获取复权因子数据
   - 解析JSON数据，提取日期和对应的复权因子
   - 构建前复权因子字典，用于后续计算

3. 新浪财经K线数据获取算法:
   - 访问新浪财经历史K线API获取不复权的原始数据
   - 解析返回的K线数据，提取日期、开盘价、最高价、最低价、收盘价、成交量
   - 应用前复权因子计算前复权价格
   - 前复权价格 = 原始价格 × 前复权因子

4. 数据存储算法:
   - 创建SQLite数据库，包含两个表:
     * stock_daily: 存储股票前复权价格数据
     * stock_info: 存储股票基本信息
   - 使用INSERT OR REPLACE语句确保数据更新时不会重复
   - 创建索引提高查询效率

5. 异常处理策略:
   - 捕获网络请求异常，返回None
   - 处理API返回数据格式异常
   - 对无法获取数据的股票进行计数
   - 添加请求延迟避免API限制

6. 性能优化:
   - 使用HTTP会话复用，减少连接建立开销
   - 批量插入数据减少数据库操作次数
   - 使用索引加速查询
   - 合理的错误处理避免程序崩溃

安装依赖:
    pip install pandas numpy requests

使用方法:
    python data/extract_data.py [--proxy PROXY]
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

# ==================== 配置 ====================
OUTPUT_DIR = r'.'
DB_PATH = os.path.join(OUTPUT_DIR, 'data', 'stock_data.db')
YEARS = 5
REQUEST_DELAY = 0.3  # 请求间隔(秒)，避免请求过快被封


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
        # 设置代理
        if self.proxy:
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            print(f"  使用代理: {self.proxy}")
    
    def fetch_adjust_factor_from_sina(self, stock_code: str) -> Optional[Dict]:
        """
        从新浪财经获取前复权因子
        
        Args:
            stock_code: 股票代码
            
        Returns:
            字典，键为日期，值为前复权因子
        """
        try:
            import requests
            import re
            import json
            
            # 新浪财经前复权因子API
            url = f'http://finance.sina.com.cn/realstock/company/sh{stock_code}/qfq.js'
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # 解析响应
            content = response.text
            
            # 提取JSON数据
            # 直接查找JSON部分（从第一个{到最后一个}）
            start_pos = content.find('{')
            end_pos = content.rfind('}')
            
            if start_pos == -1 or end_pos == -1:
                print("  无法解析前复权因子数据")
                return None
            
            json_str = content[start_pos:end_pos+1]
            
            try:
                data = json.loads(json_str)
            except ValueError as e:
                print(f"  前复权因子JSON解析失败: {e}")
                return None
            
            if 'data' not in data:
                print("  前复权因子数据格式错误")
                return None
            
            # 构建前复权因子字典
            # 每个因子记录表示从该日期开始，使用该因子
            factor_dict = {}
            for item in data['data']:
                date = item['d']
                factor = float(item['f'])
                factor_dict[date] = factor
            
            return factor_dict
            
        except Exception as e:
            print(f"  获取前复权因子失败: {e}")
            return None
    
    def fetch_from_sina(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        从新浪财经获取前复权价格
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            
        Returns:
            DataFrame包含日期和前复权价格数据
        """
        try:
            import requests
            import pandas as pd
            
            # 获取前复权因子
            factor_dict = self.fetch_adjust_factor_from_sina(stock_code)
            
            # 新浪财经历史K线API（不复权）
            url = 'http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
            params = {
                'symbol': f'sh{stock_code}',  # sh前缀表示上海股票
                'scale': 240,  # 日线
                'datalen': 1825,  # 5年数据
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析JSON响应
            try:
                data = response.json()
            except ValueError as e:
                print(f"  新浪财经JSON解析失败: {e}")
                return None
            
            # 检查数据是否为列表
            if not isinstance(data, list):
                print(f"  新浪财经数据格式错误，期望列表，得到: {type(data)}")
                return None
            
            # 解析K线数据
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
                    
                    # 计算前复权价格
                    if factor_dict:
                        # 找到适用的前复权因子
                        # 前复权因子按日期降序排列，找到第一个小于等于当前日期的因子
                        adjust_factor = 1.0
                        for factor_date in sorted(factor_dict.keys(), reverse=True):
                            if factor_date <= date_str:
                                adjust_factor = factor_dict[factor_date]
                                break
                        
                        # 应用前复权因子（新浪财经返回的是后复权因子，需要除）
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
                    print(f"  解析K线数据失败: {e}")
                    continue
            
            df = pd.DataFrame(records)
            if df.empty:
                return None
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except requests.exceptions.ProxyError as e:
            print(f"  新浪财经代理错误: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"  新浪财经连接错误: {e}")
            return None
        except requests.exceptions.Timeout as e:
            print(f"  新浪财经超时错误: {e}")
            return None
        except Exception as e:
            print(f"  新浪财经获取失败: {e}")
            return None
    
    def fetch_adjust_factor(self, stock_code: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], str]:
        """
        获取前复权价格
        
        Returns:
            (DataFrame, source) 前复权价格数据和来源
        """
        # 使用新浪财经
        df = self.fetch_from_sina(stock_code, start_date, end_date)
        if df is not None and not df.empty:
            return df, 'sina'
        
        # 如果失败，返回None
        return None, 'failed'


def create_database(db_path: str):
    """创建数据库"""
    # 确保data目录存在
    data_dir = os.path.dirname(db_path)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"创建目录: {data_dir}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 股票日线数据表（前复权价格）
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
    
    # 股票信息表
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
    print("数据库创建完成")


def insert_data(db_path: str, stock_code: str, df_price: pd.DataFrame):
    """插入数据"""
    if df_price.empty:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 插入前复权价格数据
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
    """更新股票信息
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        df: 股票数据DataFrame
        stock_name: 股票名称
    """
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
    """获取上证A股股票代码和名称列表（60开头）- 尝试多个数据源
    
    Returns:
        [(股票代码, 股票名称), ...] 元组列表
    """
    import requests
    
    # 尝试方法1: 使用新浪财经API
    print("  尝试从新浪财经API获取股票列表...")
    try:
        url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        # 使用分页方式获取所有股票
        all_stocks = []
        page = 1
        page_size = 80  # 每页获取80条数据
        
        while True:
            params = {
                'page': page,
                'num': page_size,
                'sort': 'symbol',
                'asc': 1,
                'node': 'sh_a',  # 上证A股
                'symbol': '',
                '_s_r_a': 'page'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or not isinstance(data, list) or len(data) == 0:
                # 没有更多数据，退出循环
                break
            
            # 筛选出60开头的股票代码和名称
            page_stocks = [(stock['code'], stock.get('name', '')) for stock in data if stock['code'].startswith('60')]
            all_stocks.extend(page_stocks)
            
            print(f"    第{page}页: 获取 {len(page_stocks)} 只股票，累计 {len(all_stocks)} 只")
            
            # 如果返回的数据少于页大小，说明已经是最后一页
            if len(data) < page_size:
                break
            
            page += 1
            
            # 添加延迟，避免请求过快
            time.sleep(0.1)
        
        if all_stocks:
            # 去重并按代码排序
            seen = set()
            unique_stocks = []
            for code, name in all_stocks:
                if code not in seen:
                    seen.add(code)
                    unique_stocks.append((code, name))
            unique_stocks.sort(key=lambda x: x[0])
            print(f"  成功从新浪财经获取 {len(unique_stocks)} 只上证A股股票")
            return unique_stocks
    except Exception as e:
        print(f"  新浪财经API失败: {e}")
    
    # 尝试方法2: 使用腾讯财经API
    print("  尝试从腾讯财经API获取股票列表...")
    try:
        url = 'http://qt.gtimg.cn/q='
        # 获取上证A股列表
        params = {
            'q': 'sh600000,sh600004,sh600006,sh600007,sh600008,sh600009,sh600010,sh600011,sh600012,sh600015'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 这个API需要先知道股票代码，所以不适用
        pass
    except Exception as e:
        print(f"  腾讯财经API失败: {e}")
    
    # 尝试方法3: 使用东方财富API (备用服务器)
    print("  尝试从东方财富备用API获取股票列表...")
    try:
        url = 'http://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1,
            'pz': 5000,
            'po': 1,
            'np': 1,
            'fltt': 2,
            'invt': 2,
            'fid': 'f3',
            'fs': 'm:1+t:2,m:1+t:23',
            'fields': 'f12,f14'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://quote.eastmoney.com/'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' in data and 'diff' in data['data']:
            stocks = data['data']['diff']
            sh_a_stocks = [stock['f12'] for stock in stocks if stock['f12'].startswith('60')]
            print(f"  成功从东方财富获取 {len(sh_a_stocks)} 只上证A股股票")
            return sh_a_stocks
    except Exception as e:
        print(f"  东方财富备用API失败: {e}")
    
    # 尝试方法4: 使用网易财经API
    print("  尝试从网易财经API获取股票列表...")
    try:
        url = 'http://api.money.126.net/data/feed/hs_a'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 网易财经返回的是JSONP格式，需要解析
        content = response.text
        if content:
            # 这个API也不太适用，跳过
            pass
    except Exception as e:
        print(f"  网易财经API失败: {e}")
    
    # 如果所有API都失败，返回空列表
    print("  所有API都失败，无法获取股票列表")
    return []

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='前复权价格获取工具')
    parser.add_argument('--proxy', type=str, default=None, help='代理服务器地址，例如: http://127.0.0.1:7890')
    args = parser.parse_args()
    
    print("=" * 70)
    print("前复权价格获取工具")
    print("=" * 70)
    print(f"数据库: {DB_PATH}")
    print(f"提取年限: {YEARS}年")
    if args.proxy:
        print(f"代理服务器: {args.proxy}")
    print("=" * 70)
    
    # 检查依赖
    try:
        import requests
        print("\n✓ 依赖检查通过")
    except ImportError as e:
        print(f"\n✗ 缺少依赖: {e}")
        print("请运行: pip install requests pandas numpy")
        return
    
    # 初始化
    adj_fetcher = RealAdjustFactorFetcher(proxy=args.proxy)
    create_database(DB_PATH)
    
    # 提取并处理数据
    print("\n开始获取前复权价格数据...")
    print("(数据来源: 新浪财经)\n")
    
    # 获取股票列表
    print("获取上证A股股票列表...")
    stock_codes = get_sh_a_stock_list()
    total = len(stock_codes)
    
    if total == 0:
        print("  没有获取到股票列表，程序退出")
        return
    
    print(f"共处理 {total} 只上证A股\n")
    
    success_count = 0
    fail_count = 0
    source_stats = {'sina': 0, 'failed': 0}
    
    conn = sqlite3.connect(DB_PATH)
    
    for i, stock_code in enumerate(stock_codes):
        print(f"\n处理股票: {stock_code}")
        
        # 获取股票在数据库中的信息
        stock_info = get_stock_info(conn, stock_code)
        
        # 计算日期范围
        end_date = datetime.now()
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        if stock_info is None:
            # 数据库中没有这只股票，下载最近5年的所有数据
            print("  数据库中无此股票，下载最近5年数据")
            start_date = end_date - timedelta(days=YEARS * 365)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            # 获取前复权价格数据
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code,
                start_date_str,
                end_date_str
            )
            
            source_stats[source] = source_stats.get(source, 0) + 1
            
            if df_adj is not None and not df_adj.empty:
                success_count += 1
                # 保存到数据库
                insert_data(DB_PATH, stock_code, df_adj)
                # 更新股票信息
                update_stock_info(conn, stock_code, df_adj)
                print(f"  成功下载 {len(df_adj)} 条记录")
            else:
                fail_count += 1
                print("  下载失败")
        else:
            # 数据库中有这只股票，检查是否需要更新
            print(f"  数据库中已有此股票，最新日期: {stock_info['end_date']}")
            
            # 从数据源下载从end_date到当前日期的数据
            df_adj, source = adj_fetcher.fetch_adjust_factor(
                stock_code,
                stock_info['end_date'],
                end_date_str
            )
            
            source_stats[source] = source_stats.get(source, 0) + 1
            
            if df_adj is not None and not df_adj.empty:
                # 找到end_date当天的数据
                end_date_data = df_adj[df_adj['date'] == stock_info['end_date']]
                
                if not end_date_data.empty:
                    # 比较end_date当天的收盘价
                    source_close = end_date_data.iloc[0]['close']
                    db_close = stock_info['end_date_close']
                    
                    print(f"  数据库收盘价: {db_close:.2f}, 数据源收盘价: {source_close:.2f}")
                    
                    if abs(source_close - db_close) > 0.01:  # 价格差异超过0.01，说明复权因子变动
                        print("  复权因子变动，重新下载所有数据")
                        # 重新下载最近5年的数据
                        start_date = end_date - timedelta(days=YEARS * 365)
                        start_date_str = start_date.strftime('%Y-%m-%d')
                        
                        df_adj_full, source_full = adj_fetcher.fetch_adjust_factor(
                            stock_code,
                            start_date_str,
                            end_date_str
                        )
                        
                        if df_adj_full is not None and not df_adj_full.empty:
                            success_count += 1
                            # 保存到数据库（会替换原有数据）
                            insert_data(DB_PATH, stock_code, df_adj_full)
                            # 更新股票信息
                            update_stock_info(conn, stock_code, df_adj_full)
                            print(f"  成功重新下载 {len(df_adj_full)} 条记录")
                        else:
                            fail_count += 1
                            print("  重新下载失败")
                    else:
                        # 复权因子未变动，只添加新数据
                        print("  复权因子未变动，只添加新数据")
                        # 过滤出end_date之后的数据
                        new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                        
                        if not new_data.empty:
                            success_count += 1
                            # 保存到数据库
                            insert_data(DB_PATH, stock_code, new_data)
                            # 更新股票信息
                            update_stock_info(conn, stock_code, new_data)
                            print(f"  成功添加 {len(new_data)} 条新记录")
                        else:
                            print("  无新数据")
                else:
                    # 数据源中没有end_date当天的数据，只添加新数据
                    print("  数据源中无end_date当天数据，只添加新数据")
                    # 过滤出end_date之后的数据
                    new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                    
                    if not new_data.empty:
                        success_count += 1
                        # 保存到数据库
                        insert_data(DB_PATH, stock_code, new_data)
                        # 更新股票信息
                        update_stock_info(conn, stock_code, new_data)
                        print(f"  成功添加 {len(new_data)} 条新记录")
                    else:
                        print("  无新数据")
            else:
                fail_count += 1
                print("  下载失败")
        
        if (i + 1) % 5 == 0 or i == total - 1:
            print(f"\n进度: {i + 1}/{total} ({(i + 1)/total*100:.1f}%) - "
                  f"成功: {success_count}, 失败: {fail_count}")
        
        # 添加延迟
        time.sleep(REQUEST_DELAY)
    
    conn.close()
    
    # 统计
    print("\n" + "=" * 70)
    print("数据统计")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM stock_daily')
    print(f"总记录数: {cursor.fetchone()[0]:,}")
    
    cursor.execute('SELECT COUNT(DISTINCT stock_code) FROM stock_daily')
    print(f"股票数量: {cursor.fetchone()[0]}")
    
    print("\n数据来源统计:")
    for source, count in source_stats.items():
        print(f"  {source}: {count}只股票")
    
    # 显示样本
    print("\n样本数据 (600000):")
    cursor.execute("""
        SELECT date, open, high, low, close, volume
        FROM stock_daily 
        WHERE stock_code = '600000'
        ORDER BY date DESC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: 开盘={row[1]:.2f}, 最高={row[2]:.2f}, 最低={row[3]:.2f}, 收盘={row[4]:.2f}, 成交量={row[5]:,}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("数据提取完成!")
    print(f"数据库文件: {DB_PATH}")
    print("=" * 70)


if __name__ == '__main__':
    main()
