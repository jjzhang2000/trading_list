import pandas as pd
import numpy as np

class StockStrategy:
    def __init__(self, data):
        """
        初始化策略类
        data: 包含股票历史数据的 DataFrame，至少包含 'open', 'high', 'low', 'close', 'volume' 列
        """
        self.data = data
        self.indicators = {}
    
    def calculate_ma(self, source, length, ma_type):
        """
        计算各种移动平均线
        source: 数据源
        length: 周期
        ma_type: 移动平均线类型
        """
        if ma_type == "SMA":
            return source.rolling(window=length).mean()
        elif ma_type == "EMA":
            return source.ewm(span=length, adjust=False).mean()
        elif ma_type == "DEMA":
            ema1 = source.ewm(span=length, adjust=False).mean()
            ema2 = ema1.ewm(span=length, adjust=False).mean()
            return 2 * ema1 - ema2
        elif ma_type == "TEMA":
            ema1 = source.ewm(span=length, adjust=False).mean()
            ema2 = ema1.ewm(span=length, adjust=False).mean()
            ema3 = ema2.ewm(span=length, adjust=False).mean()
            return 3 * (ema1 - ema2) + ema3
        elif ma_type == "RMA":
            return source.ewm(alpha=1/length, adjust=False).mean()
        elif ma_type == "WMA":
            weights = np.arange(1, length + 1)
            return source.rolling(window=length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
        elif ma_type == "VWMA":
            return (source * self.data['volume']).rolling(window=length).sum() / self.data['volume'].rolling(window=length).sum()
        elif ma_type == "TMA":
            sma1 = source.rolling(window=length).mean()
            return sma1.rolling(window=length).mean()
        else:
            return source.rolling(window=length).mean()
    
    def calculate_supertrend(self, atr_periods=10, atr_multi=3.0):
        """
        计算 SuperTrend 指标
        """
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']
        
        # 计算 ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_periods).mean()
        
        # 计算 SuperTrend
        upper_band = (high + low) / 2 + atr_multi * atr
        lower_band = (high + low) / 2 - atr_multi * atr
        
        supertrend = pd.Series(index=close.index)
        st_trend = pd.Series(index=close.index)
        
        # 初始化第一个值
        supertrend.iloc[0] = upper_band.iloc[0]
        st_trend.iloc[0] = 1
        
        for i in range(1, len(close)):
            # 上升趋势
            if st_trend.iloc[i-1] == 1:
                if close.iloc[i] > supertrend.iloc[i-1]:
                    supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
                    st_trend.iloc[i] = 1
                else:
                    supertrend.iloc[i] = lower_band.iloc[i]
                    st_trend.iloc[i] = -1
            # 下降趋势
            else:
                if close.iloc[i] < supertrend.iloc[i-1]:
                    supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
                    st_trend.iloc[i] = -1
                else:
                    supertrend.iloc[i] = upper_band.iloc[i]
                    st_trend.iloc[i] = 1
        
        self.indicators['supertrend'] = supertrend
        self.indicators['st_trend'] = st_trend
        
        # 计算买入/卖出信号
        st_buy_signal = (st_trend.shift(1) == -1) & (st_trend == 1)
        st_sell_signal = (st_trend.shift(1) == 1) & (st_trend == -1)
        
        return {
            'supertrend': supertrend,
            'st_trend': st_trend,
            'st_long': st_trend == 1,
            'st_short': st_trend == -1,
            'st_buy_signal': st_buy_signal,
            'st_sell_signal': st_sell_signal
        }
    
    def calculate_ema_cross(self, fast_period=21, slow_period=89):
        """
        计算 2 EMA Cross 指标
        """
        close = self.data['close']
        
        ema_fast = close.ewm(span=fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        
        self.indicators['ema_fast'] = ema_fast
        self.indicators['ema_slow'] = ema_slow
        
        # 计算买入/卖出信号
        ema_long = ema_fast > ema_slow
        ema_short = ema_fast < ema_slow
        ema_buy_signal = (ema_fast.shift(1) <= ema_slow.shift(1)) & (ema_fast > ema_slow)
        ema_sell_signal = (close.shift(1) >= ema_fast.shift(1)) & (close < ema_fast)
        
        return {
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'ema_long': ema_long,
            'ema_short': ema_short,
            'ema_buy_signal': ema_buy_signal,
            'ema_sell_signal': ema_sell_signal
        }
    
    def calculate_vegas(self, filter_period=12, fast_period1=144, fast_period2=169, slow_period1=576, slow_period2=676):
        """
        计算 Vegas 指标
        """
        close = self.data['close']
        
        vegas_filter = close.ewm(span=filter_period, adjust=False).mean()
        vegas_fast1 = close.ewm(span=fast_period1, adjust=False).mean()
        vegas_fast2 = close.ewm(span=fast_period2, adjust=False).mean()
        vegas_fast = pd.concat([vegas_fast1, vegas_fast2], axis=1).max(axis=1)
        vegas_slow1 = close.ewm(span=slow_period1, adjust=False).mean()
        vegas_slow2 = close.ewm(span=slow_period2, adjust=False).mean()
        vegas_slow = pd.concat([vegas_slow1, vegas_slow2], axis=1).max(axis=1)
        
        self.indicators['vegas_filter'] = vegas_filter
        self.indicators['vegas_fast'] = vegas_fast
        self.indicators['vegas_slow'] = vegas_slow
        
        # 计算买入/卖出信号
        vegas_fast_long = (vegas_filter > vegas_fast) & (vegas_fast > vegas_slow)
        vegas_fast_short = (vegas_filter < vegas_fast) | (vegas_fast < vegas_slow)
        vegas_slow_long = (vegas_slow1.shift(1) < vegas_slow1) & (vegas_slow2.shift(1) < vegas_slow2)
        vegas_slow_short = (vegas_slow1.shift(1) > vegas_slow1) & (vegas_slow2.shift(1) > vegas_slow2)
        vegas_long = vegas_fast_long & vegas_slow_long
        vegas_short = vegas_fast_short & vegas_slow_short
        
        return {
            'vegas_filter': vegas_filter,
            'vegas_fast': vegas_fast,
            'vegas_slow': vegas_slow,
            'vegas_long': vegas_long,
            'vegas_short': vegas_short
        }
    
    def calculate_bollinger_band(self, length=21, ma_type='EMA', source='close', multi=2.0):
        """
        计算 Bollinger Band 指标
        """
        if source == 'close':
            src = self.data['close']
        elif source == 'open':
            src = self.data['open']
        elif source == 'high':
            src = self.data['high']
        elif source == 'low':
            src = self.data['low']
        else:
            src = self.data['close']
        
        bb_basis = self.calculate_ma(src, length, ma_type)
        bb_dev = multi * src.rolling(window=length).std()
        bb_upper = bb_basis + bb_dev
        bb_lower = bb_basis - bb_dev
        bb_width = (bb_upper / bb_lower - 1) * 100
        
        self.indicators['bb_basis'] = bb_basis
        self.indicators['bb_upper'] = bb_upper
        self.indicators['bb_lower'] = bb_lower
        self.indicators['bb_width'] = bb_width
        
        # 计算买入/卖出信号
        bb_long = (src > bb_basis) & (bb_width > 10)
        bb_short = (src < bb_basis) | (bb_width <= 10)
        bb_buy_signal = (src.shift(1) <= bb_lower.shift(1)) & (src > bb_lower)
        bb_sell_signal = (src.shift(1) >= bb_basis.shift(1)) & (src < bb_basis)
        
        return {
            'bb_basis': bb_basis,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'bb_width': bb_width,
            'bb_long': bb_long,
            'bb_short': bb_short,
            'bb_buy_signal': bb_buy_signal,
            'bb_sell_signal': bb_sell_signal
        }
    
    def calculate_open_close_cross(self, basis_type="TMA", basis_len=8):
        """
        计算 Open/Close Cross 指标
        """
        open_price = self.data['open']
        close_price = self.data['close']
        
        occ_open = self.calculate_ma(open_price, basis_len, basis_type)
        occ_close = self.calculate_ma(close_price, basis_len, basis_type)
        
        self.indicators['occ_open'] = occ_open
        self.indicators['occ_close'] = occ_close
        
        # 计算买入/卖出信号
        occ_long = occ_close > occ_open
        occ_short = occ_close < occ_open
        occ_buy = (occ_close.shift(1) <= occ_open.shift(1)) & (occ_close > occ_open)
        occ_sell = (occ_close.shift(1) >= occ_open.shift(1)) & (occ_close < occ_open)
        
        return {
            'occ_open': occ_open,
            'occ_close': occ_close,
            'occ_long': occ_long,
            'occ_short': occ_short,
            'occ_buy': occ_buy,
            'occ_sell': occ_sell
        }
    
    def calculate_slope(self, long_period=100, short_period=10):
        """
        计算 VolumeProfile Slope 指标
        """
        close = self.data['close']
        
        def linreg(source, length):
            x = np.arange(1, length + 1)
            sum_x = np.sum(x)
            sum_y = np.sum(source)
            sum_x_sqr = np.sum(x**2)
            sum_xy = np.sum(source * x)
            
            slope = (length * sum_xy - sum_x * sum_y) / (length * sum_x_sqr - sum_x**2)
            return slope
        
        slope_l = close.rolling(window=long_period).apply(linreg, args=(long_period,), raw=True)
        slope_s = close.rolling(window=short_period).apply(linreg, args=(short_period,), raw=True)
        
        self.indicators['slope_l'] = slope_l
        self.indicators['slope_s'] = slope_s
        
        return {
            'slope_l': slope_l,
            'slope_s': slope_s
        }
    
    def filter_stocks(self, strategies=None):
        """
        根据策略筛选股票
        strategies: 要使用的策略列表
        """
        if strategies is None:
            strategies = ['supertrend', 'ema_cross', 'vegas', 'bollinger_band', 'open_close_cross']
        
        # 计算所有指标
        if 'supertrend' in strategies:
            self.calculate_supertrend()
        if 'ema_cross' in strategies:
            self.calculate_ema_cross()
        if 'vegas' in strategies:
            self.calculate_vegas()
        if 'bollinger_band' in strategies:
            self.calculate_bollinger_band()
        if 'open_close_cross' in strategies:
            self.calculate_open_close_cross()
        if 'slope' in strategies:
            self.calculate_slope()
        
        # 生成买入信号
        buy_signals = {}
        
        if 'supertrend' in strategies:
            buy_signals['supertrend'] = self.indicators['st_trend'] == 1
        if 'ema_cross' in strategies:
            buy_signals['ema_cross'] = self.indicators['ema_fast'] > self.indicators['ema_slow']
        if 'vegas' in strategies:
            buy_signals['vegas'] = self.indicators.get('vegas_long', pd.Series(False, index=self.data.index))
        if 'bollinger_band' in strategies:
            buy_signals['bollinger_band'] = (self.data['close'] > self.indicators['bb_basis']) & (self.indicators['bb_width'] > 10)
        if 'open_close_cross' in strategies:
            buy_signals['open_close_cross'] = self.indicators['occ_close'] > self.indicators['occ_open']
        
        # 综合信号
        if buy_signals:
            combined_signal = pd.concat(buy_signals.values(), axis=1).all(axis=1)
        else:
            combined_signal = pd.Series(False, index=self.data.index)
        
        return {
            'buy_signals': buy_signals,
            'combined_signal': combined_signal,
            'last_signal': combined_signal.iloc[-1] if not combined_signal.empty else False
        }
