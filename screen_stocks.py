import pandas as pd
import sqlite3
from stock_strategy import StockStrategy

def load_stock_data(stock_code, db_path='stock_data.db'):
    """
    从数据库加载股票历史数据
    """
    conn = sqlite3.connect(db_path)
    query = f"""
    SELECT date, open, high, low, close, volume 
    FROM stock_history 
    WHERE code = '{stock_code}' 
    ORDER BY date
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    # 转换日期格式，跳过无效日期
    if not df.empty:
        # 过滤无效日期
        valid_dates = []
        valid_data = []
        for i, row in df.iterrows():
            try:
                # 尝试解析日期
                pd.to_datetime(row['date'])
                valid_dates.append(row['date'])
                valid_data.append(row)
            except:
                continue
        
        if valid_data:
            df = pd.DataFrame(valid_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        else:
            return pd.DataFrame()
    
    return df

def screen_all_stocks(db_path='stock_data.db'):
    """
    筛选所有股票
    """
    # 连接数据库
    conn = sqlite3.connect(db_path)
    
    # 获取所有股票代码
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM stock_basic")
    stock_codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # 筛选结果
    results = []
    
    for stock_code in stock_codes:
        try:
            # 加载股票数据
            data = load_stock_data(stock_code, db_path)
            
            # 确保数据足够
            if len(data) < 200:  # 需要足够的数据来计算指标
                continue
            
            # 创建策略实例
            strategy = StockStrategy(data)
            
            # 筛选股票
            result = strategy.filter_stocks()
            
            # 如果有买入信号，添加到结果
            if result['last_signal']:
                # 计算各项指标的具体值
                indicators = {}
                if 'st_trend' in strategy.indicators:
                    indicators['supertrend'] = '买入' if strategy.indicators['st_trend'].iloc[-1] == 1 else '卖出'
                if 'ema_fast' in strategy.indicators and 'ema_slow' in strategy.indicators:
                    indicators['ema_cross'] = '金叉' if strategy.indicators['ema_fast'].iloc[-1] > strategy.indicators['ema_slow'].iloc[-1] else '死叉'
                if 'vegas_long' in result:
                    indicators['vegas'] = '多头' if result['vegas_long'].iloc[-1] else '空头'
                if 'bb_basis' in strategy.indicators:
                    indicators['bollinger_band'] = '上轨' if data['close'].iloc[-1] > strategy.indicators['bb_upper'].iloc[-1] else '中轨' if data['close'].iloc[-1] > strategy.indicators['bb_basis'].iloc[-1] else '下轨'
                if 'occ_close' in strategy.indicators and 'occ_open' in strategy.indicators:
                    indicators['open_close_cross'] = '收大于开' if strategy.indicators['occ_close'].iloc[-1] > strategy.indicators['occ_open'].iloc[-1] else '收小于开'
                
                results.append({
                    'stock_code': stock_code,
                    'last_price': data['close'].iloc[-1],
                    'indicators': indicators
                })
                
            print(f"处理股票: {stock_code} - {'符合条件' if result['last_signal'] else '不符合条件'}")
            
        except Exception as e:
            print(f"处理股票 {stock_code} 时出错: {e}")
            continue
    
    return results

def main():
    """
    主函数
    """
    print("开始筛选股票...")
    results = screen_all_stocks()
    
    print(f"\n筛选完成，共找到 {len(results)} 只符合条件的股票:")
    for result in results:
        print(f"\n股票代码: {result['stock_code']}")
        print(f"最新价格: {result['last_price']}")
        print("指标状态:")
        for indicator, status in result['indicators'].items():
            print(f"  - {indicator}: {status}")
    
    # 保存结果到CSV文件
    if results:
        df = pd.DataFrame(results)
        df.to_csv('screened_stocks.csv', index=False, encoding='utf-8-sig')
        print("\n结果已保存到 screened_stocks.csv 文件")

if __name__ == "__main__":
    main()
