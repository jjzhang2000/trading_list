# -*- coding: utf-8 -*-
"""
K线图窗口模块
使用独立进程显示K线图窗口，避免阻塞主GUI
"""

import subprocess
import sys
import os
from typing import List, Dict
from utils.logger import get_logger

logger = get_logger(__name__)


def get_kline_html() -> str:
    """生成K线图HTML页面"""
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
        }
        #chart-container {
            width: 100%;
            height: 100vh;
            position: relative;
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
    <div id="chart-container">
        <div class="info-bar" id="info-bar"></div>
    </div>
    
    <script>
        let chart = null;
        let candleSeries = null;
        let volumeSeries = null;
        
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
            
            window.addEventListener('resize', () => {
                chart.applyOptions({
                    width: container.clientWidth,
                    height: container.clientHeight,
                });
            });
            
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
            if (!data) { infoBar.innerHTML = ''; return; }
            
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
        
        async function loadKLine(code) {
            try {
                await waitForApi();
                const result = await window.pywebview.api.get_kline_data(code, 120);
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
                console.error('加载K线数据失败:', e);
            }
        }
        
        window.addEventListener('DOMContentLoaded', () => {
            initChart();
        });
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
    """K线图窗口类 - 使用独立进程"""
    
    def __init__(self):
        """初始化K线图窗口"""
        self._processes = []  # 跟踪所有启动的进程
        
    def show(self, stock_code: str, stock_name: str):
        """
        显示K线图窗口（启动独立进程）
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            kline_script = os.path.join(current_dir, 'kline_standalone.py')
            
            # 检查脚本是否存在
            if not os.path.exists(kline_script):
                logger.error(f"K线图脚本不存在: {kline_script}")
                return
            
            logger.info(f"启动K线图进程: {stock_code} - {stock_name}")
            
            # 启动子进程，输出直接显示在控制台以便调试
            process = subprocess.Popen(
                [sys.executable, kline_script, stock_code, stock_name],
                cwd=current_dir
            )
            
            self._processes.append(process)
            logger.info(f"K线图进程已启动，PID: {process.pid}")
                
        except Exception as e:
            logger.error(f"启动K线图窗口失败: {e}", exc_info=True)
    
    def close(self):
        """关闭所有K线图窗口"""
        for process in self._processes:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    try:
                        process.kill()
                    except:
                        pass
        self._processes.clear()
        logger.info("所有K线图窗口已关闭")
