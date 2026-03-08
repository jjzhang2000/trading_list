import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import time
import os
import json
from config import DATA_FETCH_CONFIG, STOCK_LIST, INDICATOR_CONFIG

def get_stock_data(ticker, period="1y"):
    """获取股票历史数据，支持缓存"""
    # 检查缓存
    cache_file = os.path.join(DATA_FETCH_CONFIG['cache_dir'], f"{ticker}_{period}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time < DATA_FETCH_CONFIG['cache_expire']:
                print(f"使用缓存数据: {ticker}")
                data = pd.DataFrame(cache_data['data'])
                data.index = pd.to_datetime(data.index)
                print(f"成功加载缓存数据，共 {len(data)} 条记录")
                return data
        except Exception as e:
            print(f"读取缓存失败: {e}")
    
    # 缓存过期或不存在，尝试从网络获取
    try:
        print(f"正在获取 {ticker} 数据...")
        # 移除.SS后缀，akshare使用纯数字代码
        stock_code = ticker.replace('.SS', '')
        
        # 计算开始日期
        end_date = datetime.now().strftime('%Y%m%d')
        if period == "1y":
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        elif period == "6mo":
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        elif period == "3mo":
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        else:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        # 使用akshare获取数据
        data = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="qfq")
        
        if data is not None and not data.empty:
            # 调整数据格式
            data['日期'] = pd.to_datetime(data['日期'])
            data.set_index('日期', inplace=True)
            data = data.rename(columns={
                '开盘': 'Open',
                '最高': 'High',
                '最低': 'Low',
                '收盘': 'Close',
                '成交量': 'Volume'
            })
            
            # 保存到缓存
            os.makedirs(DATA_FETCH_CONFIG['cache_dir'], exist_ok=True)
            cache_data = {
                'timestamp': time.time(),
                'data': data.to_dict()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"成功获取 {ticker} 数据，共 {len(data)} 条记录")
            return data
        else:
            print(f"获取 {ticker} 数据为空")
            return None
    except Exception as e:
        print(f"获取 {ticker} 数据失败: {e}")
        # 尝试返回过期缓存
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                data = pd.DataFrame(cache_data['data'])
                data.index = pd.to_datetime(data.index)
                print(f"使用过期缓存数据: {ticker}")
                return data
            except Exception as e:
                print(f"读取过期缓存失败: {e}")
        return None

def calculate_indicators(data):
    """计算技术指标"""
    try:
        if data is None or data.empty:
            return None
        
        # 计算收益率
        data['Return'] = data['Close'].pct_change()
        
        # 计算移动平均线
        data['MA5'] = data['Close'].rolling(window=5).mean()
        data['MA20'] = data['Close'].rolling(window=20).mean()
        data['MA50'] = data['Close'].rolling(window=50).mean()
        
        # 计算RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # 计算MACD
        exp1 = data['Close'].ewm(span=12, adjust=False).mean()
        exp2 = data['Close'].ewm(span=26, adjust=False).mean()
        data['MACD'] = exp1 - exp2
        data['Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        
        return data
    except Exception as e:
        print(f"计算指标失败: {e}")
        return None

def score_stock(data, ticker):
    """对股票进行评分"""
    try:
        if data is None or data.empty:
            return 0
        
        score = 0
        latest = data.iloc[-1]
        
        # 趋势得分（移动平均线）
        if not pd.isna(latest['MA5']) and not pd.isna(latest['MA20']) and not pd.isna(latest['MA50']):
            if latest['MA5'] > latest['MA20'] > latest['MA50']:
                score += 30
            elif latest['MA5'] > latest['MA20']:
                score += 20
            elif latest['MA20'] > latest['MA50']:
                score += 10
        
        # RSI得分
        if not pd.isna(latest['RSI']):
            if 30 <= latest['RSI'] <= 70:
                score += 20
            elif latest['RSI'] < 30:
                score += 15  # 超卖，可能反弹
        
        # MACD得分
        if not pd.isna(latest['MACD']) and not pd.isna(latest['Signal']):
            if latest['MACD'] > latest['Signal']:
                score += 20
        
        # 波动率得分（较低的波动率更稳定）
        if not pd.isna(data['Return'].std()):
            volatility = data['Return'].std() * np.sqrt(252)
            if volatility < 0.2:
                score += 15
            elif volatility < 0.3:
                score += 10
        
        # 最近表现得分
        if len(data) >= 30:
            recent_return = data['Return'].tail(30).mean() * 365
            if recent_return > 0:
                score += 15
        
        return score
    except Exception as e:
        print(f"评分失败: {e}")
        return 0

def rank_stocks(tickers):
    """对股票进行排名"""
    results = []
    
    for ticker in tickers:
        print(f"分析股票: {ticker}")
        # 尝试获取数据，最多重试3次
        retry_count = 0
        max_retries = 3
        data = None
        
        while retry_count < max_retries:
            try:
                data = get_stock_data(ticker)
                if data is not None and not data.empty:
                    break
                retry_count += 1
                if retry_count < max_retries:
                    print(f"重试获取 {ticker} 数据... ({retry_count}/{max_retries})")
                    time.sleep(2)  # 减少延迟时间，避免网络超时
            except Exception as e:
                print(f"获取数据时发生异常: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"重试获取 {ticker} 数据... ({retry_count}/{max_retries})")
                    time.sleep(2)
        
        if data is not None and not data.empty:
            data = calculate_indicators(data)
            if data is not None:
                score = score_stock(data, ticker)
                latest_price = data.iloc[-1]['Close']
                results.append({
                    'ticker': ticker,
                    'score': score,
                    'price': latest_price
                })
        else:
            print(f"无法获取 {ticker} 数据，跳过该股票")
        # 添加延迟，避免API速率限制
        time.sleep(1)  # 减少延迟时间
    
    # 按得分排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def main():
    """主函数"""
    print("开始分析上证A股...")
    ranked_stocks = rank_stocks(STOCK_LIST)
    
    print("\n股票排名结果:")
    print("-" * 50)
    print(f"{'排名':<5} {'股票':<10} {'得分':<10} {'当前价格':<10}")
    print("-" * 50)
    
    if ranked_stocks:
        for i, stock in enumerate(ranked_stocks, 1):
            print(f"{i:<5} {stock['ticker']:<10} {stock['score']:<10} ¥{stock['price']:.2f}")
        print("-" * 50)
        print(f"推荐买入: {ranked_stocks[0]['ticker']} (得分: {ranked_stocks[0]['score']})")
    else:
        print("未获取到任何股票数据，请检查网络连接或稍后重试")
        print("-" * 50)

if __name__ == "__main__":
    main()
