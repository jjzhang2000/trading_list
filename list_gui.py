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

from data import init_db, extract_data, read_data
from tech import supertrend, vegas, bollingerband, occross, vp_slope


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
        stock_codes: 当前加载的所有股票代码列表
        filtered_codes: 筛选后的股票代码列表
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
        
        self.stock_codes: List[str] = []
        self.filtered_codes: List[str] = []
        self.is_running = False
        self.worker_thread: Optional[StoppableThread] = None
        
        self.setup_ui()
        
        atexit.register(self.cleanup)
    
    def setup_ui(self):
        """
        设置UI界面
        
        将界面分为三个部分：
        - 上部：数据操作区
        - 中部：筛选器设置区
        - 下部：股票列表区
        """
        self.setup_top_frame()
        self.setup_middle_frame()
        self.setup_bottom_frame()
    
    def cleanup(self):
        """清理资源，在程序退出时调用"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.stop()
            self.worker_thread.join(timeout=1.0)
    
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
            ('vegas', 'Vegas通道 (多头排列)'),
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
    
    def log_result(self, message: str):
        """
        在运行结果文本框中记录日志
        
        Args:
            message: 要记录的消息
        """
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
                self.root.after(0, lambda: self.log_result(f"初始化失败: {str(e)}"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"初始化失败: {str(e)}"))
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
                
                stock_codes = extract_data.get_sh_a_stock_list()
                total = len(stock_codes)
                
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
                
                for i, stock_code in enumerate(stock_codes):
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
                            extract_data.update_stock_info(conn, stock_code, df_adj)
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
                                        extract_data.update_stock_info(conn, stock_code, df_adj_full)
                                else:
                                    new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                                    
                                    if not new_data.empty:
                                        success_count += 1
                                        total_records += len(new_data)
                                        extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                                        extract_data.update_stock_info(conn, stock_code, new_data)
                            else:
                                new_data = df_adj[df_adj['date'] > stock_info['end_date']]
                                
                                if not new_data.empty:
                                    success_count += 1
                                    total_records += len(new_data)
                                    extract_data.insert_data(extract_data.DB_PATH, stock_code, new_data)
                                    extract_data.update_stock_info(conn, stock_code, new_data)
                    
                    if (i + 1) % 50 == 0:
                        progress = (i + 1) / total * 100
                        self.root.after(0, lambda p=progress, s=success_count, r=total_records: 
                                       self.log_result(f"进度: {p:.1f}% - 成功: {s} 只股票, {r} 条记录"))
                    
                    time.sleep(extract_data.REQUEST_DELAY)
                
                conn.close()
                
                self.stock_codes = read_data.get_all_stock_codes()
                self.root.after(0, self.update_stock_list)
                self.root.after(0, lambda: self.log_result(f"提取完成！成功 {success_count} 只股票, 共 {total_records} 条记录"))
                self.root.after(0, lambda: messagebox.showinfo("成功", f"提取完成！\n成功: {success_count} 只股票\n共: {total_records} 条记录"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_result(f"提取失败: {str(e)}"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"提取失败: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def update_stock_list(self):
        """更新左侧股票列表显示"""
        self.stock_listbox.delete(0, tk.END)
        for code in self.stock_codes:
            self.stock_listbox.insert(tk.END, code)
        self.stock_count_label.config(text=f"共 {len(self.stock_codes)} 只股票")
    
    def update_result_list(self):
        """更新右侧筛选结果列表显示"""
        self.result_listbox.delete(0, tk.END)
        for code in self.filtered_codes:
            self.result_listbox.insert(tk.END, code)
        self.result_count_label.config(text=f"共 {len(self.filtered_codes)} 只股票")
    
    def on_filter(self):
        """
        开始筛选按钮回调
        
        根据选中的筛选器依次执行筛选，更新右侧结果列表。
        
        筛选流程：
            1. 检查是否已加载数据
            2. 获取启用的筛选器列表
            3. 在后台线程中依次执行筛选
            4. 更新右侧结果列表
        """
        if self.is_running:
            return
        
        if not self.stock_codes:
            messagebox.showwarning("警告", "请先提取数据！")
            return
        
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
                codes = self.stock_codes.copy()
                
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
                
                self.filtered_codes = codes
                self.root.after(0, self.update_result_list)
                self.root.after(0, lambda: self.log_result(f"筛选完成！共 {len(codes)} 只股票符合条件"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_result(f"筛选失败: {str(e)}"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"筛选失败: {str(e)}"))
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
