#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票筛选GUI程序（图形界面版本）

功能说明：
    提供图形界面进行数据库初始化、数据提取和股票筛选。

界面布局：
    ┌─────────────────────────────────────────────────────────────────┐
    │ 数据操作                                                         │
    │ ┌──────────────┐ ┌──────────────┐ ┌───────────────────────────┐│
    │ │ 初始化数据库 │ │  提取数据    │ │ 运行结果:                 ││
    │ └──────────────┘ └──────────────┘ │ [日志信息...]             ││
    │                                   │                           ││
    │                                   └───────────────────────────┘│
    ├─────────────────────────────────────────────────────────────────┤
    │ 筛选器设置                                                       │
    │ ☑ SuperTrend  ☑ Vegas通道  ☑ 布林带  ☑ OCC  ☑ VP Slope  [开始筛选]│
    ├─────────────────────────────────────────────────────────────────┤
    │ ┌─────────────────────┐ ┌─────────────────────┐                │
    │ │ 全部股票            │ │ 筛选结果            │                │
    │ │ ┌─────────────────┐ │ │ ┌─────────────────┐ │                │
    │ │ │ 600000          │ │ │ │ 600036          │ │                │
    │ │ │ 600004          │ │ │ │ 600519          │ │                │
    │ │ │ ...             │ │ │ │ ...             │ │                │
    │ │ └─────────────────┘ │ │ └─────────────────┘ │                │
    │ │ 共 1800 只股票      │ │ 共 25 只股票        │                │
    │ └─────────────────────┘ └─────────────────────┘                │
    └─────────────────────────────────────────────────────────────────┘

使用方法：
    python list_gui.py

操作流程：
    1. 点击"初始化数据库"清空或创建数据库
    2. 点击"提取数据"从新浪财经获取股票数据
    3. 选择需要启用的筛选器（默认全部启用）
    4. 点击"开始筛选"执行筛选

技术说明：
    - 使用tkinter构建GUI界面
    - 使用threading实现后台任务，避免界面卡顿
    - 使用root.after()实现线程安全的UI更新
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from datetime import datetime
from typing import List, Optional
import atexit
import os

from data import init_db, extract_data, read_data
from tech import supertrend, vegas, bollingerband, occross, vp_slope, trend_score
from utils.logger import get_logger, get_log_dir

logger = get_logger(__name__)

SHAREHOLDING_FILE = os.path.join(os.path.dirname(__file__), 'shareholding.txt')


def load_shareholding() -> List[str]:
    """读取持仓股票列表"""
    if not os.path.exists(SHAREHOLDING_FILE):
        return []
    
    codes = []
    with open(SHAREHOLDING_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            code = line.strip()
            if code and code.isdigit():
                codes.append(code)
    
    return codes


class StoppableThread(threading.Thread):
    """可停止的线程类，避免Python 3.13的daemon线程清理问题"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
    
    def stop(self):
        self._stop_event.set()
    
    def is_stopped(self):
        return self._stop_event.is_set()


class StockFilterGUI:
    """
    股票筛选GUI主类
    
    Attributes:
        root: Tkinter根窗口
        stock_list: 当前加载的所有股票列表 [(代码, 名称), ...]
        filtered_list: 筛选后的股票列表 [(代码, 名称), ...]
        is_running: 标记是否有后台任务正在运行
        filter_vars: 筛选器开关变量的字典
        worker_thread: 当前运行的工作线程
    """
    
    def __init__(self, root):
        """
        初始化GUI
        
        Args:
            root: Tkinter根窗口
        """
        self.root = root
        self.root.title("股票筛选系统")
        self.root.geometry("1000x700")
        
        self.stock_list: List[tuple] = []
        self.filtered_list: List[tuple] = []
        self.is_running = False
        self.worker_thread: Optional[StoppableThread] = None
        
        self.setup_ui()
        
        atexit.register(self.cleanup)
    
    def setup_ui(self):
        """
        设置UI界面
        
        将界面分为四个部分：
        - 上部：数据操作区
        - 中部：筛选器设置区
        - 下部：股票列表区
        - 底部：股票查询区
        """
        self.setup_top_frame()
        self.setup_middle_frame()
        self.setup_bottom_frame()
        self.setup_query_frame()
    
    def cleanup(self):
        """清理资源，在程序退出时调用"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.stop()
            self.worker_thread.join(timeout=1.0)
        
        import logging
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()
    
    def setup_top_frame(self):
        """
        设置上部数据操作区
        
        包含：
        - 初始化数据库按钮
        - 提取数据按钮
        - 运行结果文本框
        """
        top_frame = ttk.LabelFrame(self.root, text="数据操作", padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.LEFT)
        
        self.btn_init = ttk.Button(btn_frame, text="初始化数据库", width=15, command=self.on_init_db)
        self.btn_init.pack(side=tk.LEFT, padx=5)
        
        self.btn_extract = ttk.Button(btn_frame, text="提取数据", width=15, command=self.on_extract_data)
        self.btn_extract.pack(side=tk.LEFT, padx=5)
        
        result_frame = ttk.Frame(top_frame)
        result_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        ttk.Label(result_frame, text="运行结果:").pack(anchor=tk.W)
        self.result_text = scrolledtext.ScrolledText(result_frame, height=6, state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)
    
    def setup_middle_frame(self):
        """
        设置中部筛选器设置区
        
        包含：
        - 5个筛选器复选框（SuperTrend、Vegas、布林带、OCC、VP Slope）
        - 开始筛选按钮
        """
        middle_frame = ttk.LabelFrame(self.root, text="筛选器设置", padding=10)
        middle_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.filter_vars = {}
        filters = [
            ('supertrend', 'SuperTrend (多头趋势)'),
            ('vegas', 'Vegas通道 (EMA多头排列)'),
            ('bollingerband', '布林带 (开口率>10%)'),
            ('occross', 'OCC指标 (多头趋势)'),
            ('vp_slope', 'VP Slope (斜率>0)')
        ]
        
        for name, label in filters:
            var = tk.BooleanVar(value=True)
            self.filter_vars[name] = var
            cb = ttk.Checkbutton(middle_frame, text=label, variable=var)
            cb.pack(side=tk.LEFT, padx=15)
        
        self.btn_filter = ttk.Button(middle_frame, text="开始筛选", width=12, command=self.on_filter)
        self.btn_filter.pack(side=tk.RIGHT, padx=10)
    
    def setup_bottom_frame(self):
        """
        设置下部股票列表区
        
        包含：
        - 左侧列表：显示所有股票
        - 右侧列表：显示筛选结果
        """
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        left_frame = ttk.LabelFrame(bottom_frame, text="全部股票", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.stock_listbox = tk.Listbox(left_frame, selectmode=tk.EXTENDED)
        self.stock_listbox.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_left = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.stock_listbox.yview)
        scrollbar_left.pack(side=tk.RIGHT, fill=tk.Y)
        self.stock_listbox.config(yscrollcommand=scrollbar_left.set)
        
        self.stock_count_label = ttk.Label(left_frame, text="共 0 只股票")
        self.stock_count_label.pack(anchor=tk.W)
        
        right_frame = ttk.LabelFrame(bottom_frame, text="筛选结果", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.result_listbox = tk.Listbox(right_frame, selectmode=tk.EXTENDED)
        self.result_listbox.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_right = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.result_listbox.yview)
        scrollbar_right.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_listbox.config(yscrollcommand=scrollbar_right.set)
        
        self.result_count_label = ttk.Label(right_frame, text="共 0 只股票")
        self.result_count_label.pack(anchor=tk.W)
    
    def setup_query_frame(self):
        """
        设置底部股票查询区
        
        包含：
        - 股票代码输入框
        - 检测按钮
        - 5个指标结果显示区
        """
        query_frame = ttk.LabelFrame(self.root, text="股票查询", padding=10)
        query_frame.pack(fill=tk.X, padx=10, pady=5)
        
        input_frame = ttk.Frame(query_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(input_frame, text="股票代码:").pack(side=tk.LEFT)
        self.query_code_entry = ttk.Entry(input_frame, width=10)
        self.query_code_entry.pack(side=tk.LEFT, padx=5)
        
        self.btn_query = ttk.Button(input_frame, text="检测", width=8, command=self.on_query_stock)
        self.btn_query.pack(side=tk.LEFT, padx=5)
        
        self.query_stock_name_label = ttk.Label(input_frame, text="")
        self.query_stock_name_label.pack(side=tk.LEFT, padx=10)
        
        result_frame = ttk.Frame(query_frame)
        result_frame.pack(fill=tk.X)
        
        self.indicator_labels = {}
        indicators = [
            ('supertrend', 'SuperTrend', '多头' if True else '空头'),
            ('vegas', 'Vegas通道', '多头排列' if True else '空头排列'),
            ('bollingerband', '布林带', '开口率: 0%'),
            ('occross', 'OCC指标', '多头' if True else '空头'),
            ('vp_slope', 'VP Slope', '斜率: 0')
        ]
        
        for name, label, default_value in indicators:
            frame = ttk.Frame(result_frame)
            frame.pack(side=tk.LEFT, padx=15)
            ttk.Label(frame, text=f"{label}:", font=('', 9, 'bold')).pack(side=tk.LEFT)
            value_label = ttk.Label(frame, text="--", width=15)
            value_label.pack(side=tk.LEFT)
            self.indicator_labels[name] = value_label
    
    def on_query_stock(self):
        """
        检测按钮回调
        
        查询指定股票的5个技术指标结果
        """
        stock_code = self.query_code_entry.get().strip()
        if not stock_code:
            messagebox.showwarning("警告", "请输入股票代码！")
            return
        
        logger.info(f"开始查询股票: {stock_code}")
        
        for label in self.indicator_labels.values():
            label.config(text="--")
        self.query_stock_name_label.config(text="")
        
        if self.is_running:
            return
        
        self.is_running = True
        self.btn_query.config(state=tk.DISABLED)
        
        def run():
            try:
                date = datetime.now().strftime('%Y-%m-%d')
                
                stock_name = ""
                if self.stock_list:
                    for code, name in self.stock_list:
                        if code == stock_code:
                            stock_name = name
                            break
                
                if not stock_name:
                    stock_name = read_data.get_stock_name(stock_code) or ""
                
                logger.info(f"股票名称: {stock_name or '未知'}")
                self.root.after(0, lambda n=stock_name: self.query_stock_name_label.config(text=n))
                
                st_df = supertrend.get_stock_supertrend(stock_code, date, days=50)
                if st_df is not None and not st_df.empty:
                    last_row = st_df.iloc[-1]
                    trend = "多头" if last_row['trend_direction'] == 1 else "空头"
                    logger.info(f"SuperTrend: {trend}")
                    self.root.after(0, lambda t=trend: self.indicator_labels['supertrend'].config(text=t))
                else:
                    logger.warning("SuperTrend: 数据不足")
                    self.root.after(0, lambda: self.indicator_labels['supertrend'].config(text="数据不足"))
                
                vegas_df = vegas.get_stock_vegas(stock_code, date, days=50)
                if vegas_df is not None and not vegas_df.empty:
                    last_row = vegas_df.iloc[-1]
                    trend = "多头排列" if last_row['trend_direction'] == 1 else "空头排列"
                    logger.info(f"Vegas通道: {trend}")
                    self.root.after(0, lambda t=trend: self.indicator_labels['vegas'].config(text=t))
                else:
                    logger.warning("Vegas通道: 数据不足")
                    self.root.after(0, lambda: self.indicator_labels['vegas'].config(text="数据不足"))
                
                bb_df = bollingerband.get_stock_bollinger_band(stock_code, date, days=50)
                if bb_df is not None and not bb_df.empty:
                    last_row = bb_df.iloc[-1]
                    bandwidth = last_row['bandwidth']
                    logger.info(f"布林带开口率: {bandwidth:.2f}%")
                    self.root.after(0, lambda b=bandwidth: self.indicator_labels['bollingerband'].config(text=f"开口率: {b:.2f}%"))
                else:
                    logger.warning("布林带: 数据不足")
                    self.root.after(0, lambda: self.indicator_labels['bollingerband'].config(text="数据不足"))
                
                occ_df = occross.get_stock_occ(stock_code, date, days=50)
                if occ_df is not None and not occ_df.empty:
                    last_row = occ_df.iloc[-1]
                    trend = "多头" if last_row['trend_direction'] == 1 else "空头"
                    logger.info(f"OCC指标: {trend}")
                    self.root.after(0, lambda t=trend: self.indicator_labels['occross'].config(text=t))
                else:
                    logger.warning("OCC指标: 数据不足")
                    self.root.after(0, lambda: self.indicator_labels['occross'].config(text="数据不足"))
                
                slope_df = vp_slope.get_stock_slope(stock_code, date, days=50)
                if slope_df is not None and not slope_df.empty:
                    last_row = slope_df.iloc[-1]
                    slope_long = last_row['slope_long']
                    logger.info(f"VP Slope: {slope_long:.4f}")
                    self.root.after(0, lambda s=slope_long: self.indicator_labels['vp_slope'].config(text=f"斜率: {s:.4f}"))
                else:
                    logger.warning("VP Slope: 数据不足")
                    self.root.after(0, lambda: self.indicator_labels['vp_slope'].config(text="数据不足"))
                
                logger.info(f"股票 {stock_code} 查询完成")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"查询失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"查询失败: {msg}"))
            finally:
                self.root.after(0, lambda: self.btn_query.config(state=tk.NORMAL))
                self.is_running = False
        
        threading.Thread(target=run, daemon=True).start()
    
    def log_result(self, message: str):
        """
        在运行结果文本框中记录日志，同时写入日志文件
        
        Args:
            message: 要记录的消息
        """
        logger.info(message)
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)
    
    def set_buttons_state(self, enabled: bool):
        """
        设置所有操作按钮的启用/禁用状态
        
        Args:
            enabled: True启用，False禁用
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_init.config(state=state)
        self.btn_extract.config(state=state)
        self.btn_filter.config(state=state)
    
    def on_init_db(self):
        """
        初始化数据库按钮回调
        
        在后台线程中执行数据库初始化，完成后显示结果。
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.set_buttons_state(False)
        self.log_result("开始初始化数据库...")
        
        def run():
            try:
                init_db.init_database()
                self.root.after(0, lambda: self.log_result("数据库初始化成功！"))
                self.root.after(0, lambda: messagebox.showinfo("成功", "数据库初始化成功！"))
            except Exception as e:
                error_msg = str(e)
                logger.error(f"初始化失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"初始化失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"初始化失败: {msg}"))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def on_extract_data(self):
        """
        提取数据按钮回调
        
        在后台线程中执行数据提取，完成后更新股票列表。
        
        算法逻辑：
            1. 初始化HTTP会话和数据库
            2. 获取上证A股股票列表（60开头）
            3. 对每只股票进行增量更新：
               - 如果数据库中没有该股票，下载最近5年的所有数据
               - 如果数据库中已有该股票，检测复权因子变动并更新
            4. 更新左侧股票列表
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.set_buttons_state(False)
        self.log_result("开始提取数据...")
        
        def run():
            try:
                adj_fetcher = extract_data.RealAdjustFactorFetcher(proxy=None)
                extract_data.create_database(extract_data.DB_PATH)
                
                stock_list = extract_data.get_sh_a_stock_list()
                total = len(stock_list)
                
                if total == 0:
                    self.root.after(0, lambda: self.log_result("获取股票列表失败"))
                    return
                
                self.root.after(0, lambda: self.log_result(f"获取到 {total} 只股票"))
                
                import sqlite3
                import time
                from datetime import timedelta
                
                conn = sqlite3.connect(extract_data.DB_PATH)
                end_date = datetime.now()
                end_date_str = end_date.strftime('%Y-%m-%d')
                
                success_count = 0
                total_records = 0
                
                for i, (stock_code, stock_name) in enumerate(stock_list):
                    stock_info = extract_data.get_stock_info(conn, stock_code)
                    
                    if stock_info is None:
                        start_date = end_date - timedelta(days=extract_data.YEARS * 365)
                        start_date_str = start_date.strftime('%Y-%m-%d')
                        
                        df_adj, source = adj_fetcher.fetch_adjust_factor(
                            stock_code, start_date_str, end_date_str
                        )
                        
                        if df_adj is not None and not df_adj.empty:
                            success_count += 1
                            total_records += len(df_adj)
                            extract_data.insert_data(extract_data.DB_PATH, stock_code, df_adj)
                            extract_data.update_stock_info(conn, stock_code, df_adj, stock_name)
                    else:
                        df_adj, source = adj_fetcher.fetch_adjust_factor(
                            stock_code, stock_info['end_date'], end_date_str
                        )
                        
                        if df_adj is not None and not df_adj.empty:
                            end_date_data = df_adj[df_adj['date'] == stock_info['end_date']]
                            
                            if not end_date_data.empty:
                                source_close = end_date_data.iloc[0]['close']
                                db_close = stock_info['end_date_close']
                                
                                if abs(source_close - db_close) > 0.01:
                                    start_date = end_date - timedelta(days=extract_data.YEARS * 365)
                                    start_date_str = start_date.strftime('%Y-%m-%d')
                                    
                                    df_adj_full, source_full = adj_fetcher.fetch_adjust_factor(
                                        stock_code, start_date_str, end_date_str
                                    )
                                    
                                    if df_adj_full is not None and not df_adj_full.empty:
                                        success_count += 1
                                        total_records += len(df_adj_full)
                                        extract_data.insert_data(extract_data.DB_PATH, stock_code, df_adj_full)
                                        extract_data.update_stock_info(conn, stock_code, df_adj_full, stock_name)
                                else:
                                    new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                                    
                                    if not new_data.empty:
                                        success_count += 1
                                        total_records += len(new_data)
                                        extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                                        extract_data.update_stock_info(conn, stock_code, new_data, stock_name)
                            else:
                                new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                                
                                if not new_data.empty:
                                    success_count += 1
                                    total_records += len(new_data)
                                    extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                                    extract_data.update_stock_info(conn, stock_code, new_data, stock_name)
                    
                    if (i + 1) % 50 == 0:
                        progress = (i + 1) / total * 100
                        self.root.after(0, lambda p=progress, s=success_count, r=total_records: 
                                       self.log_result(f"进度: {p:.1f}% - 成功: {s} 只股票, {r} 条记录"))
                    
                    time.sleep(extract_data.REQUEST_DELAY)
                
                conn.close()
                
                self.stock_list = read_data.get_all_stock_codes_with_names()
                self.root.after(0, self.update_stock_list)
                self.root.after(0, lambda: self.log_result(f"提取完成！成功 {success_count} 只股票, 共 {total_records} 条记录"))
                self.root.after(0, lambda: messagebox.showinfo("成功", f"提取完成！\n成功: {success_count} 只股票\n共: {total_records} 条记录"))
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"提取失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"提取失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"提取失败: {msg}"))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def update_stock_list(self):
        """更新左侧股票列表显示"""
        self.stock_listbox.delete(0, tk.END)
        for code, name in self.stock_list:
            display_text = f"{code} - {name}" if name else code
            self.stock_listbox.insert(tk.END, display_text)
        self.stock_count_label.config(text=f"共 {len(self.stock_list)} 只股票")
    
    def update_result_list(self):
        """更新右侧筛选结果列表显示"""
        self.result_listbox.delete(0, tk.END)
        for item in self.filtered_list:
            if len(item) == 4:
                code, name, score, is_shareholding = item
                mark = "★" if is_shareholding else " "
                display_text = f"{score:.2f}  {mark} {code}  {name}" if name else f"{score:.2f}  {mark} {code}"
            elif len(item) == 3:
                code, name, score = item
                display_text = f"{score:.2f}  {code}  {name}" if name else f"{score:.2f}  {code}"
            else:
                code, name = item
                display_text = f"{code} - {name}" if name else code
            self.result_listbox.insert(tk.END, display_text)
        self.result_count_label.config(text=f"共 {len(self.filtered_list)} 只股票")
    
    def on_filter(self):
        """
        开始筛选按钮回调
        
        根据选中的筛选器依次执行筛选，更新右侧结果列表。
        
        筛选流程：
            1. 加载数据（如未加载则从数据库读取）
            2. 获取启用的筛选器列表
            3. 在后台线程中依次执行筛选
            4. 更新右侧结果列表
        """
        if self.is_running:
            return
        
        if not self.stock_list:
            self.stock_list = read_data.get_all_stock_codes_with_names()
            if not self.stock_list:
                messagebox.showwarning("警告", "数据库中没有股票数据，请先提取数据！")
                return
            self.update_stock_list()
        
        active_filters = [name for name, var in self.filter_vars.items() if var.get()]
        if not active_filters:
            messagebox.showwarning("警告", "请至少选择一个筛选器！")
            return
        
        self.is_running = True
        self.set_buttons_state(False)
        self.log_result(f"开始筛选，启用筛选器: {', '.join(active_filters)}")
        
        def run():
            try:
                date = datetime.now().strftime('%Y-%m-%d')
                codes = [code for code, name in self.stock_list]
                code_to_name = {code: name for code, name in self.stock_list}
                
                self.root.after(0, lambda: self.log_result(f"过滤ST股票..."))
                st_count = 0
                filtered_codes = []
                for code in codes:
                    name = code_to_name.get(code, '')
                    if 'ST' in name.upper():
                        st_count += 1
                    else:
                        filtered_codes.append(code)
                codes = filtered_codes
                self.root.after(0, lambda s=st_count, c=len(codes): self.log_result(f"过滤掉 {s} 只ST股票，剩余 {c} 只"))
                
                if 'supertrend' in active_filters:
                    self.root.after(0, lambda: self.log_result(f"SuperTrend筛选 - 输入: {len(codes)} 只股票"))
                    df = supertrend.filter_bullish_stocks(date, stock_codes=codes)
                    codes = df['stock_code'].tolist() if not df.empty else []
                    self.root.after(0, lambda c=len(codes): self.log_result(f"SuperTrend筛选 - 输出: {c} 只股票"))
                    if not codes:
                        self.root.after(0, lambda: self.log_result("筛选结果为空"))
                        return
                
                if 'vegas' in active_filters and codes:
                    self.root.after(0, lambda: self.log_result(f"Vegas通道筛选 - 输入: {len(codes)} 只股票"))
                    df = vegas.filter_bullish_stocks(date, codes)
                    codes = df['stock_code'].tolist() if not df.empty else []
                    self.root.after(0, lambda c=len(codes): self.log_result(f"Vegas通道筛选 - 输出: {c} 只股票"))
                    if not codes:
                        self.root.after(0, lambda: self.log_result("筛选结果为空"))
                        return
                
                if 'bollingerband' in active_filters and codes:
                    self.root.after(0, lambda: self.log_result(f"布林带筛选 - 输入: {len(codes)} 只股票"))
                    df = bollingerband.filter_stocks_by_bandwidth(date, codes, threshold=10.0)
                    codes = df['stock_code'].tolist() if not df.empty else []
                    self.root.after(0, lambda c=len(codes): self.log_result(f"布林带筛选 - 输出: {c} 只股票"))
                    if not codes:
                        self.root.after(0, lambda: self.log_result("筛选结果为空"))
                        return
                
                if 'occross' in active_filters and codes:
                    self.root.after(0, lambda: self.log_result(f"OCC指标筛选 - 输入: {len(codes)} 只股票"))
                    df = occross.filter_bullish_stocks(date, codes)
                    codes = df['stock_code'].tolist() if not df.empty else []
                    self.root.after(0, lambda c=len(codes): self.log_result(f"OCC指标筛选 - 输出: {c} 只股票"))
                    if not codes:
                        self.root.after(0, lambda: self.log_result("筛选结果为空"))
                        return
                
                if 'vp_slope' in active_filters and codes:
                    self.root.after(0, lambda: self.log_result(f"VP Slope筛选 - 输入: {len(codes)} 只股票"))
                    df = vp_slope.filter_stocks_by_slope(date, codes)
                    codes = df['stock_code'].tolist() if not df.empty else []
                    self.root.after(0, lambda c=len(codes): self.log_result(f"VP Slope筛选 - 输出: {c} 只股票"))
                
                shareholding = load_shareholding()
                self.root.after(0, lambda s=len(shareholding): self.log_result(f"读取持仓股票: {s} 只"))
                
                all_result_codes = list(set(codes + shareholding))
                
                if all_result_codes:
                    self.root.after(0, lambda: self.log_result(f"计算趋势强度评分..."))
                    strength_df = trend_score.rank_stocks_by_strength(all_result_codes, date)
                    
                    if not strength_df.empty:
                        strength_df['is_shareholding'] = strength_df['stock_code'].isin(shareholding)
                        
                        strength_df['stock_name'] = strength_df.apply(
                            lambda row: f"*{row['stock_name']}" if row['is_shareholding'] and row['stock_name'] else row['stock_name'],
                            axis=1
                        )
                        
                        self.filtered_list = [
                            (row['stock_code'], row['stock_name'], row['strength_score'], row['is_shareholding'])
                            for _, row in strength_df.iterrows()
                        ]
                        self.root.after(0, self.update_result_list)
                        
                        csv_path = os.path.join(get_log_dir(), f"listing-{date}.csv")
                        strength_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                        self.root.after(0, lambda p=csv_path: self.log_result(f"结果已保存到: {p}"))
                        
                        self.root.after(0, lambda c=len(all_result_codes): self.log_result(f"筛选完成！共 {c} 只股票"))
                    else:
                        all_result_codes.sort()
                        self.filtered_list = [(code, code_to_name.get(code, ''), 0, code in shareholding) for code in all_result_codes]
                        self.root.after(0, self.update_result_list)
                        self.root.after(0, lambda c=len(all_result_codes): self.log_result(f"筛选完成！共 {c} 只股票"))
                else:
                    self.root.after(0, lambda: self.log_result("筛选结果为空"))
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"筛选失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"筛选失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"筛选失败: {msg}"))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()


def main():
    """主函数：创建Tkinter窗口并启动GUI"""
    root = tk.Tk()
    app = StockFilterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
