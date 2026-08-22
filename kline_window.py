# -*- coding: utf-8 -*-
"""
K线图窗口模块
单窗口，只显示最新双击的股票K线图
"""

import subprocess
import sys
import os
import multiprocessing
from typing import List, Dict
from utils.logger import get_logger
from utils.window_state import load_window_state, save_window_state

logger = get_logger(__name__)


def get_kline_html() -> str:
    """生成K线图HTML页面（单股票版本）"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K线图</title>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        #header {
            background: #252526;
            border-bottom: 1px solid #3c3c3c;
            padding: 12px 16px;
            font-size: 16px;
            font-weight: bold;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            gap: 100px;
        }
        .vegas-toggle {
            font-size: 14px;
            font-weight: normal;
            display: flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            user-select: none;
            color: #d4d4d4;
        }
        .vegas-toggle input {
            cursor: pointer;
        }
        .header-controls {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .bollinger-bandwidth {
            font-variant-numeric: tabular-nums;
            color: #9cdcfe;
        }
        .vp-slope-display {
            font-size: 14px;
            font-weight: normal;
            color: #d4d4d4;
        }
        #vp-slope-value {
            font-variant-numeric: tabular-nums;
            color: #9cdcfe;
        }
        #chart-container {
            flex: 1;
            position: relative;
            overflow: hidden;
        }
        .info-bar {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(30, 30, 30, 0.9);
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 13px;
            z-index: 1000;
            pointer-events: none;
        }
        .info-bar span { margin-right: 15px; }
        .up { color: #6ccb5f; }
        .down { color: #f76363; }
        .neutral { color: #d4d4d4; }
    </style>
</head>
<body>
    <div id="header">
        <span id="header-title">K线图</span>
        <div class="header-controls">
            <label class="vegas-toggle">
                <input type="checkbox" id="vegas-checkbox"> Vegas
            </label>
            <label class="vegas-toggle">
                <input type="checkbox" id="bollinger-checkbox"> Bollinger Bands
                <span id="bollinger-bandwidth" class="bollinger-bandwidth"></span>
            </label>
            <span class="vp-slope-display">VP Slope <span id="vp-slope-value"></span></span>
        </div>
    </div>
    <div id="chart-container">
        <div class="info-bar" id="info-bar"></div>
    </div>
    
    <script>
        let chart = null;
        let candleSeries = null;
        let volumeSeries = null;
        let currentStockCode = null;
        let currentStockName = null;
        let ema12Series = null;
        let ema144Series = null;
        let ema576Series = null;
        let currentVegasData = null;
        let bbUpperSeries = null;
        let bbMiddleSeries = null;
        let bbLowerSeries = null;
        let currentBollingerData = null;
        let currentVpSlopeData = null;
        let uiState = { vegas: false, bollinger: false, visibleFrom: null, visibleTo: null };
        let rangeSaveTimer = null;
        
        function initChart() {
            const container = document.getElementById('chart-container');
            
            chart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {
                    background: { type: 'solid', color: '#1e1e1e' },
                    textColor: '#d4d4d4',
                },
                grid: {
                    vertLines: { color: 'rgba(192, 192, 192, 0.1)' },
                    horzLines: { color: 'rgba(192, 192, 192, 0.1)' },
                },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: 'rgba(192, 192, 192, 0.3)' },
                timeScale: {
                    borderColor: 'rgba(192, 192, 192, 0.3)',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });
            
            candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
                upColor: '#6ccb5f', downColor: '#f76363',
                borderUpColor: '#6ccb5f', borderDownColor: '#f76363',
                wickUpColor: '#6ccb5f', wickDownColor: '#f76363',
            });
            
            volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
                priceFormat: { type: 'volume' },
                priceScaleId: 'volume',
            });
            chart.priceScale('volume').applyOptions({
                scaleMargins: { top: 0.8, bottom: 0 },
            });
            
            // 监听resize
            const resizeObserver = new ResizeObserver(() => {
                chart.applyOptions({
                    width: container.clientWidth,
                    height: container.clientHeight,
                });
            });
            resizeObserver.observe(container);
            
            // 监听鼠标移动更新info bar
            chart.subscribeCrosshairMove(param => {
                if (!param.time || !param.point) {
                    updateInfoBar(null);
                    updateBollingerBandwidth(null);
                    updateVpSlopeValue(null);
                    return;
                }
                const data = param.seriesData.get(candleSeries);
                const volData = param.seriesData.get(volumeSeries);
                updateBollingerBandwidth(param.time);
                updateVpSlopeValue(param.time);
                if (data) {
                    updateInfoBar({
                        time: param.time,
                        open: data.open, high: data.high,
                        low: data.low, close: data.close,
                        volume: volData ? volData.value : 0
                    });
                }
            });
            
            // 监听可视日期范围变化，用于持久化保存
            chart.timeScale().subscribeVisibleTimeRangeChange(() => {
                scheduleRangeSave();
            });
        }
        
        function updateInfoBar(data) {
            const infoBar = document.getElementById('info-bar');
            if (!infoBar) return;
            
            if (!data) { 
                infoBar.innerHTML = ''; 
                return; 
            }
            
            const change = data.close - data.open;
            const changePct = (change / data.open * 100).toFixed(2);
            const changeClass = change > 0 ? 'up' : change < 0 ? 'down' : 'neutral';
            const sign = change > 0 ? '+' : '';
            
            infoBar.innerHTML = `
                <span>O: ${data.open.toFixed(2)}</span>
                <span>H: ${data.high.toFixed(2)}</span>
                <span>L: ${data.low.toFixed(2)}</span>
                <span>C: <span class="${changeClass}">${data.close.toFixed(2)}</span></span>
                <span class="${changeClass}">${sign}${change.toFixed(2)} (${sign}${changePct}%)</span>
                <span>Vol: ${formatVolume(data.volume)}</span>
            `;
        }
        
        function formatVolume(vol) {
            if (vol >= 1e8) return (vol / 1e8).toFixed(2) + '亿';
            if (vol >= 1e4) return (vol / 1e4).toFixed(2) + '万';
            return vol.toFixed(0);
        }
        
        function calcEMA(values, length) {
            const alpha = 2 / (length + 1);
            const result = new Array(values.length);
            result[0] = values[0];
            for (let i = 1; i < values.length; i++) {
                result[i] = alpha * values[i] + (1 - alpha) * result[i - 1];
            }
            return result;
        }
        
        function updateVegasSeries() {
            if (!chart) return;
            const checked = document.getElementById('vegas-checkbox').checked;
            
            if (checked && currentVegasData) {
                if (!ema12Series) {
                    ema12Series = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(255, 165, 0, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                    ema144Series = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(255, 0, 0, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                    ema576Series = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(0, 0, 255, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                }
                
                const dates = currentVegasData.dates;
                ema12Series.setData(dates.map((date, i) => ({ time: date, value: currentVegasData.ema12[i] })));
                ema144Series.setData(dates.map((date, i) => ({ time: date, value: currentVegasData.ema144[i] })));
                ema576Series.setData(dates.map((date, i) => ({ time: date, value: currentVegasData.ema576[i] })));
            } else {
                if (ema12Series) ema12Series.setData([]);
                if (ema144Series) ema144Series.setData([]);
                if (ema576Series) ema576Series.setData([]);
            }
        }
        
        function calcBollinger(closes, period, mult) {
            const middle = calcEMA(closes, period);
            const upper = new Array(closes.length).fill(null);
            const lower = new Array(closes.length).fill(null);
            const bandwidth = new Array(closes.length).fill(null);
            for (let i = period - 1; i < closes.length; i++) {
                let sum = 0;
                for (let j = i - period + 1; j <= i; j++) sum += closes[j];
                const mean = sum / period;
                let sq = 0;
                for (let j = i - period + 1; j <= i; j++) {
                    const d = closes[j] - mean;
                    sq += d * d;
                }
                const std = Math.sqrt(sq / period);
                upper[i] = middle[i] + mult * std;
                lower[i] = middle[i] - mult * std;
                bandwidth[i] = (upper[i] - lower[i]) / middle[i] * 100;
            }
            return { middle, upper, lower, bandwidth };
        }
        
        function updateBollingerSeries() {
            if (!chart) return;
            const checked = document.getElementById('bollinger-checkbox').checked;
            
            if (checked && currentBollingerData) {
                if (!bbUpperSeries) {
                    bbUpperSeries = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(0, 255, 0, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                    bbMiddleSeries = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(255, 255, 255, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                    bbLowerSeries = chart.addSeries(LightweightCharts.LineSeries, {
                        color: 'rgba(0, 255, 0, 0.5)',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    });
                }
                
                const dates = currentBollingerData.dates;
                const upperData = [];
                const middleData = [];
                const lowerData = [];
                for (let i = 0; i < dates.length; i++) {
                    if (currentBollingerData.upper[i] != null) {
                        upperData.push({ time: dates[i], value: currentBollingerData.upper[i] });
                    }
                    if (currentBollingerData.middle[i] != null) {
                        middleData.push({ time: dates[i], value: currentBollingerData.middle[i] });
                    }
                    if (currentBollingerData.lower[i] != null) {
                        lowerData.push({ time: dates[i], value: currentBollingerData.lower[i] });
                    }
                }
                bbUpperSeries.setData(upperData);
                bbMiddleSeries.setData(middleData);
                bbLowerSeries.setData(lowerData);
            } else {
                if (bbUpperSeries) bbUpperSeries.setData([]);
                if (bbMiddleSeries) bbMiddleSeries.setData([]);
                if (bbLowerSeries) bbLowerSeries.setData([]);
            }
        }
        
        function timeToKey(time) {
            if (typeof time === 'string') return time;
            if (time && time.year !== undefined) {
                const m = String(time.month).padStart(2, '0');
                const d = String(time.day).padStart(2, '0');
                return `${time.year}-${m}-${d}`;
            }
            return String(time);
        }
        
        function bandwidthColor(val) {
            if (val < 10) return '#f76363';
            if (val < 20) return '#e8930c';
            return '#6ccb5f';
        }
        
        function updateBollingerBandwidth(time) {
            const el = document.getElementById('bollinger-bandwidth');
            if (!el) return;
            
            if (!time || !currentBollingerData || !currentBollingerData.bandwidthMap) {
                el.textContent = '';
                el.style.color = '';
                return;
            }
            
            const bw = currentBollingerData.bandwidthMap[timeToKey(time)];
            if (bw != null) {
                el.textContent = bw.toFixed(1) + '%';
                el.style.color = bandwidthColor(bw);
            } else {
                el.textContent = '';
                el.style.color = '';
            }
        }
        
        function calcLinregSlope(values, length) {
            const n = length;
            const sumX = n * (n - 1) / 2;
            const sumX2 = n * (n - 1) * (2 * n - 1) / 6;
            const denom = n * sumX2 - sumX * sumX;
            const result = new Array(values.length).fill(null);
            for (let i = n - 1; i < values.length; i++) {
                let sumY = 0;
                let sumXY = 0;
                for (let j = 0; j < n; j++) {
                    const y = values[i - n + 1 + j];
                    sumY += y;
                    sumXY += j * y;
                }
                result[i] = (n * sumXY - sumX * sumY) / denom;
            }
            return result;
        }
        
        function slopeColor(val) {
            if (val > 0) return '#6ccb5f';
            if (val < 0) return '#f76363';
            return '#ffffff';
        }
        
        function updateVpSlopeValue(time) {
            const el = document.getElementById('vp-slope-value');
            if (!el) return;
            
            if (!time || !currentVpSlopeData) {
                el.textContent = '';
                return;
            }
            
            const key = timeToKey(time);
            const longVal = currentVpSlopeData.longMap[key];
            const shortVal = currentVpSlopeData.shortMap[key];
            const parts = [];
            if (longVal != null) {
                parts.push(`<span style="color:${slopeColor(longVal)}">${longVal.toFixed(1)}%</span>`);
            }
            if (shortVal != null) {
                parts.push(`<span style="color:${slopeColor(shortVal)}">${shortVal.toFixed(1)}%</span>`);
            }
            el.innerHTML = parts.join(' / ');
        }
        
        function saveUiState() {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.save_ui_state) {
                window.pywebview.api.save_ui_state({
                    vegas: document.getElementById('vegas-checkbox').checked,
                    bollinger: document.getElementById('bollinger-checkbox').checked,
                    visibleFrom: uiState.visibleFrom || null,
                    visibleTo: uiState.visibleTo || null,
                });
            }
        }
        
        function saveVisibleRange() {
            if (!chart) return;
            const range = chart.timeScale().getVisibleRange();
            if (!range || range.from === undefined || range.to === undefined) return;
            const from = timeToKey(range.from);
            const to = timeToKey(range.to);
            if (from && to && (uiState.visibleFrom !== from || uiState.visibleTo !== to)) {
                uiState.visibleFrom = from;
                uiState.visibleTo = to;
                saveUiState();
            }
        }
        
        function scheduleRangeSave() {
            if (rangeSaveTimer) clearTimeout(rangeSaveTimer);
            rangeSaveTimer = setTimeout(() => {
                rangeSaveTimer = null;
                saveVisibleRange();
            }, 500);
        }
        
        function waitForApi() {
            return new Promise((resolve) => {
                if (window.pywebview && window.pywebview.api) {
                    resolve();
                } else {
                    const check = () => {
                        if (window.pywebview && window.pywebview.api) {
                            resolve();
                        } else {
                            setTimeout(check, 100);
                        }
                    };
                    check();
                }
            });
        }
        
        async function showStock(stockCode, stockName) {
            try {
                await waitForApi();
                await uiStateReady;
                
                // 更新标题
                document.getElementById('header-title').textContent = `${stockCode} / ${stockName}`;
                
                currentStockCode = stockCode;
                currentStockName = stockName;
                
                // 如果chart未初始化，先初始化
                if (!chart) {
                    initChart();
                }
                
                // 加载数据（加载完整历史，缩放时由图表自行调整可见区间）
                const result = await window.pywebview.api.get_kline_data(stockCode, 2000);
                if (result && result.length > 0) {
                    const candles = result.map(d => ({
                        time: d.date, open: d.open,
                        high: d.high, low: d.low, close: d.close,
                    }));
                    const volumes = result.map(d => ({
                        time: d.date, value: d.volume,
                        color: d.close >= d.open ? 'rgba(108, 203, 95, 0.3)' : 'rgba(247, 99, 99, 0.3)',
                    }));
                    
                    candleSeries.setData(candles);
                    volumeSeries.setData(volumes);
                    
                    // 计算Vegas通道EMA数据（EMA12/144/576）
                    const closes = result.map(d => d.close);
                    currentVegasData = {
                        ema12: calcEMA(closes, 12),
                        ema144: calcEMA(closes, 144),
                        ema576: calcEMA(closes, 576),
                        dates: result.map(d => d.date),
                    };
                    updateVegasSeries();
                    
                    // 计算布林带数据（中轨EMA20，上下轨±2倍标准差）
                    currentBollingerData = calcBollinger(closes, 20, 2.0);
                    currentBollingerData.dates = result.map(d => d.date);
                    currentBollingerData.bandwidthMap = {};
                    for (let i = 0; i < currentBollingerData.dates.length; i++) {
                        currentBollingerData.bandwidthMap[currentBollingerData.dates[i]] = currentBollingerData.bandwidth[i];
                    }
                    updateBollingerSeries();
                    updateBollingerBandwidth(null);
                    
                    // 计算Volume Profile Slope数据（slope_long周期100，slope_short周期10，均转为相对收盘价的百分比）
                    const dates = result.map(d => d.date);
                    const slopeLong = calcLinregSlope(closes, 100);
                    const slopeShort = calcLinregSlope(closes, 10);
                    currentVpSlopeData = { longMap: {}, shortMap: {} };
                    for (let i = 0; i < dates.length; i++) {
                        const c = closes[i];
                        if (c && slopeLong[i] != null) {
                            currentVpSlopeData.longMap[dates[i]] = slopeLong[i] / c * 100;
                        }
                        if (c && slopeShort[i] != null) {
                            currentVpSlopeData.shortMap[dates[i]] = slopeShort[i] / c * 100;
                        }
                    }
                    updateVpSlopeValue(null);
                    
                    // 恢复上次显示的日期范围，否则默认显示最近120个交易日
                    let rangeRestored = false;
                    if (uiState.visibleFrom && uiState.visibleTo) {
                        try {
                            chart.timeScale().setVisibleRange({
                                from: uiState.visibleFrom,
                                to: uiState.visibleTo,
                            });
                            rangeRestored = true;
                        } catch (e) {
                            console.error('恢复日期范围失败:', e);
                        }
                    }
                    if (!rangeRestored) {
                        const totalBars = candles.length;
                        const visibleBars = 120;
                        if (totalBars > visibleBars) {
                            chart.timeScale().setVisibleLogicalRange({
                                from: totalBars - visibleBars,
                                to: totalBars + 0.5,
                            });
                        } else {
                            chart.timeScale().fitContent();
                        }
                    }
                }
            } catch (e) {
                console.error('显示股票失败:', e);
            }
        }
        
        const uiStateReady = (async () => {
            try {
                await waitForApi();
                const state = await window.pywebview.api.get_ui_state();
                if (state) {
                    uiState.vegas = !!state.vegas;
                    uiState.bollinger = !!state.bollinger;
                    uiState.visibleFrom = state.visibleFrom || null;
                    uiState.visibleTo = state.visibleTo || null;
                    if (state.vegas) document.getElementById('vegas-checkbox').checked = true;
                    if (state.bollinger) document.getElementById('bollinger-checkbox').checked = true;
                }
            } catch (e) {
                console.error('加载UI状态失败:', e);
            }
            updateVegasSeries();
            updateBollingerSeries();
        })();
        
        // Vegas复选框切换事件
        document.getElementById('vegas-checkbox').addEventListener('change', () => {
            updateVegasSeries();
            saveUiState();
        });
        // Bollinger Bands复选框切换事件
        document.getElementById('bollinger-checkbox').addEventListener('change', () => {
            updateBollingerSeries();
            saveUiState();
        });
    </script>
</body>
</html>'''


class KLineAPI:
    """K线图数据API（供JavaScript调用）"""
    
    def get_ui_state(self) -> Dict:
        """
        获取K线窗口UI状态（复选框选中状态与可视日期范围）
        
        Returns:
            包含 vegas、bollinger 复选框状态及 visibleFrom、visibleTo 的字典
        """
        state = load_window_state('kline_ui') or {}
        return {
            'vegas': bool(state.get('vegas', False)),
            'bollinger': bool(state.get('bollinger', False)),
            'visibleFrom': state.get('visibleFrom'),
            'visibleTo': state.get('visibleTo'),
        }
    
    def save_ui_state(self, state: Dict) -> None:
        """
        保存K线窗口UI状态
        
        Args:
            state: 包含 vegas、bollinger、visibleFrom、visibleTo 的字典
        """
        save_window_state('kline_ui', {
            'vegas': bool(state.get('vegas', False)),
            'bollinger': bool(state.get('bollinger', False)),
            'visibleFrom': state.get('visibleFrom'),
            'visibleTo': state.get('visibleTo'),
        })
    
    def get_kline_data(self, stock_code: str, days: int = 120) -> List[Dict]:
        """
        获取K线数据
        
        Args:
            stock_code: 股票代码
            days: 获取天数
        
        Returns:
            K线数据列表
        """
        from datetime import datetime, timedelta
        from data import read_data
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        df = read_data.get_stock_price_in_range(stock_code, start_date, end_date)
        
        if df.empty:
            return []
        
        result = []
        for _, row in df.iterrows():
            result.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
            })
        
        return result


class KLineWindow:
    """K线图窗口类 - 单窗口，只显示最新双击的股票"""
    
    def __init__(self):
        """初始化K线图窗口"""
        self._process = None
        self._cmd_queue = None
        
    def show(self, stock_code: str, stock_name: str):
        """
        显示K线图（只显示最新双击的股票）
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
        """
        try:
            # 如果进程不存在，启动新进程
            if self._process is None or not self._process.is_alive():
                logger.info(f"启动K线图进程: {stock_code} - {stock_name}")
                
                # 创建命令队列
                self._cmd_queue = multiprocessing.Queue()
                
                # 导入并启动子进程
                from kline_standalone import run_kline_window
                self._process = multiprocessing.Process(
                    target=run_kline_window,
                    args=(self._cmd_queue,)
                )
                self._process.daemon = True
                self._process.start()
                
                logger.info(f"K线图进程已启动，PID: {self._process.pid}")
                
                # 等待窗口初始化
                import time
                time.sleep(1)
            
            # 发送显示股票命令（只显示最新双击的股票）
            if self._cmd_queue is not None:
                self._cmd_queue.put({
                    'action': 'show_stock',
                    'stock_code': stock_code,
                    'stock_name': stock_name
                })
                logger.info(f"发送显示股票命令: {stock_code} - {stock_name}")
                
        except Exception as e:
            logger.error(f"显示K线图失败: {e}", exc_info=True)
    
    def close(self):
        """关闭K线图窗口"""
        if self._process and self._process.is_alive():
            try:
                # 发送关闭命令
                if self._cmd_queue is not None:
                    self._cmd_queue.put({'action': 'close'})
                
                # 等待进程退出
                self._process.join(timeout=2)
                
                # 如果进程仍在运行，强制终止
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=1)
            except Exception as e:
                logger.error(f"关闭K线图窗口失败: {e}", exc_info=True)
        
        # 清理队列
        if self._cmd_queue is not None:
            try:
                self._cmd_queue.close()
                self._cmd_queue.join_thread()
            except:
                pass
        
        self._process = None
        self._cmd_queue = None
        logger.info("K线图窗口已关闭")
