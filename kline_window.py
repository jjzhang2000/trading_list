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
    <div id="header">K线图</div>
    <div id="chart-container">
        <div class="info-bar" id="info-bar"></div>
    </div>
    
    <script>
        let chart = null;
        let candleSeries = null;
        let volumeSeries = null;
        let currentStockCode = null;
        let currentStockName = null;
        
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
                    return;
                }
                const data = param.seriesData.get(candleSeries);
                const volData = param.seriesData.get(volumeSeries);
                if (data) {
                    updateInfoBar({
                        time: param.time,
                        open: data.open, high: data.high,
                        low: data.low, close: data.close,
                        volume: volData ? volData.value : 0
                    });
                }
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
                
                // 更新标题
                document.getElementById('header').textContent = `${stockName} (${stockCode})`;
                
                currentStockCode = stockCode;
                currentStockName = stockName;
                
                // 如果chart未初始化，先初始化
                if (!chart) {
                    initChart();
                }
                
                // 加载数据
                const result = await window.pywebview.api.get_kline_data(stockCode, 120);
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
                    chart.timeScale().fitContent();
                }
            } catch (e) {
                console.error('显示股票失败:', e);
            }
        }
    </script>
</body>
</html>'''


class KLineAPI:
    """K线图数据API（供JavaScript调用）"""
    
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
