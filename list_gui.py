#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票筛选GUI程序（图形界面版本）

功能说明：
    提供图形界面进行数据库初始化、数据提取和股票筛选。
    支持上证A股（60开头）和ETF指数（5开头）。

界面布局：
    ┌─────────────────────────────────────────────────────────────────┐
    │ 数据操作                                                         │
    │ ┌──────────────┐ ┌───────────────────────────────────────────┐│
    │ │ 提取股票数据 │ │ [日志信息...]                              ││
    │ │ 初始化数据库 │ │                                           ││
    │ │ 迁移交易流水 │ │                                           ││
    │ └──────────────┘ └───────────────────────────────────────────┘│
    ├─────────────────────────────────────────────────────────────────┤
    │ 筛选器设置                                                       │
    │ ☑ SuperTrend  ☑ Vegas通道  ☑ 布林带  ☑ OCC  ☑ VP Slope  [开始筛选]│
    ├─────────────────────────────────────────────────────────────────┤
    │ ┌─────────────────────────────────────────────────────────────┐│
    │ │ [股票] [ETF] [持仓]  ← Notebook 三个tab                     ││
    │ │                                                             ││
    │ │ 股票tab：60开头股票（含持仓）的筛选结果                       ││
    │ │ ETF tab ：5开头ETF（含持仓）的筛选结果                        ││
    │ │ 持仓tab ：shareholding.txt 中所有持仓股票的指标计算结果      ││
    │ │         （不经过筛选流水线，直接计算全部指标）                ││
    │ └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

使用方法：
    python list_gui.py

操作流程：
    1. 点击"初始化数据库"清空或创建数据库
    2. 点击"提取股票数据"从新浪财经获取股票数据
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

from data import init_db, extract_data, read_data, migrate_trades
from tech import supertrend, vegas, bollingerband, occross, vp_slope, trend_score
from data.read_data import save_indicator, get_indicator, get_latest_trading_dates
from utils.logger import get_logger
from utils.window_state import load_window_state, save_window_state
from kline_window import KLineWindow

logger = get_logger(__name__)


def get_holding_codes() -> List[str]:
    """从数据库交易流水读取持仓股票代码（净持仓数量>0）"""
    codes = migrate_trades.get_holding_position_codes()
    logger.info(f"读取到 {len(codes)} 只持仓股票")
    return codes


def merge_holdings(holding_codes: List[str], filtered_codes: List[str]) -> List[str]:
    """合并持仓股票到筛选结果（去重）"""
    result = filtered_codes.copy()
    for code in holding_codes:
        if code not in result:
            result.append(code)
    added = len(result) - len(filtered_codes)
    if added > 0:
        logger.info(f"添加 {added} 只持仓股票到结果")
    return result


def _compute_vegas(stock_code: str, date: str) -> int:
    """计算Vegas指标值并缓存"""
    vegas_df = vegas.get_stock_vegas(stock_code, date, days=50)
    if vegas_df is not None and not vegas_df.empty:
        lr = vegas_df.iloc[-1]
        vp = (lr['close'] - lr['ema144']) / lr['ema144'] * 100
        vp = round(vp)
        save_indicator(stock_code, date, 'vegas', vp)
        return vp
    return 0


def _compute_bb(stock_code: str, date: str) -> int:
    """计算布林带指标值并缓存"""
    bb_df = bollingerband.get_stock_bollinger_band(stock_code, date, days=50)
    if bb_df is not None and not bb_df.empty:
        bw = bb_df.iloc[-1]['bandwidth']
        if hasattr(bw, '__float__') and bw == bw:
            bw = round(bw)
            save_indicator(stock_code, date, 'bollingerbands', bw)
            return bw
    return 0


def _compute_occ(stock_code: str, date: str) -> int:
    """计算OCC指标值并缓存"""
    occ_df = occross.get_stock_occ(stock_code, date, days=50)
    if occ_df is not None and not occ_df.empty:
        lr = occ_df.iloc[-1]
        if lr['occ_open'] > 0:
            op = (lr['occ_close'] - lr['occ_open']) / lr['occ_open'] * 1000
            op = round(op)
            save_indicator(stock_code, date, 'openclosecross', op)
            return op
    return 0


def _compute_vp(stock_code: str, date: str) -> int:
    """计算VP Slope指标值并缓存"""
    vp_df = vp_slope.get_stock_slope(stock_code, date, days=150)
    if vp_df is not None and not vp_df.empty:
        lr = vp_df.iloc[-1]
        if lr['close'] > 0:
            vpp = lr['slope_short'] / lr['close'] * 1000
            vpp = round(vpp)
            save_indicator(stock_code, date, 'volumeprofile', vpp)
            return vpp
    return 0


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
        filtered_list: 筛选结果（不含持仓）数据列表 [{'code', 'name', 'supertrend', ...}, ...]
        holding_list: 持仓股票数据列表 [{'code', 'name', 'supertrend', ...}, ...]
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

        # 恢复上次保存的窗口位置和尺寸，否则使用默认布局
        saved = load_window_state('gui')
        if saved and saved.get('geometry'):
            self.root.geometry(saved['geometry'])
        else:
            screen_width = self.root.winfo_screenwidth()
            screen_height = int(self.root.winfo_screenheight() * 0.94)  # 减去任务栏等占用的高度
            width = screen_width // 3
            self.root.geometry(f"{width}x{screen_height}+{screen_width - width}+0")
        
        self.stock_list: List[tuple] = []
        self.stock_filtered: List[dict] = []   # 股票筛选结果（60开头，扣除持仓）
        self.etf_filtered: List[dict] = []     # ETF筛选结果（5开头，扣除持仓）
        self.holding_list: List[dict] = []     # 持仓股票计算结果（不筛选，直接计算指标）
        self.history_list: List[dict] = []     # 已平仓股票计算结果（扣除持仓）
        self.query_list: List[dict] = []       # 查询tab结果（手动查询的股票）
        self.context_tree: Optional[ttk.Treeview] = None  # 右键选中的表格
        self.context_row: Optional[str] = None            # 右键选中的行
        self.is_running = False
        self.worker_thread: Optional[StoppableThread] = None
        self.kline_window: Optional[KLineWindow] = None  # K线图窗口
        
        self.setup_ui()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        atexit.register(self.cleanup)
    
    def _on_close(self):
        """关闭窗口前保存位置和尺寸"""
        save_window_state('gui', {'geometry': self.root.winfo_geometry()})
        self.cleanup()
        self.root.destroy()
    
    def setup_ui(self):
        """
        设置UI界面
        
        将界面分为三个部分：
        - 上部：数据操作区
        - 中部：交易区
        - 下部：筛选器和结果区
        """
        self.setup_top_frame()
        self.setup_trade_frame()
        self.setup_middle_frame()
    
    def cleanup(self):
        """清理资源，在程序退出时调用"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.stop()
            self.worker_thread.join(timeout=1.0)
        
        # 关闭所有K线图窗口
        if self.kline_window:
            self.kline_window.close()
        
        import logging
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()
    
    def setup_top_frame(self):
        """
        设置上部数据操作区

        包含：
        - 左侧垂直排列：提取股票数据按钮、初始化数据库按钮
        - 右侧：运行日志文本框
        """
        top_frame = ttk.LabelFrame(self.root, text="数据操作", padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.btn_extract = ttk.Button(btn_frame, text="提取股票数据", width=15, command=self.on_extract_data)
        self.btn_extract.pack(pady=2)

        self.btn_init = ttk.Button(btn_frame, text="初始化数据库", width=15, command=self.on_init_db)
        self.btn_init.pack(pady=2)

        result_frame = ttk.Frame(top_frame)
        result_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.result_text = scrolledtext.ScrolledText(result_frame, height=4, state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)
    
    def setup_trade_frame(self):
        """
        设置中部交易区

        包含：
        - 左侧：迁移交易流水按钮、交易盈亏统计按钮
        - 右侧：交易盈亏统计结果表格
        """
        trade_frame = ttk.LabelFrame(self.root, text="交易", padding=10)
        trade_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_frame = ttk.Frame(trade_frame)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.btn_migrate = ttk.Button(btn_frame, text="迁移交易流水", width=15, command=self.on_migrate_trades)
        self.btn_migrate.pack(pady=2)

        self.btn_trade_stats = ttk.Button(btn_frame, text="交易盈亏统计", width=15, command=self.on_trade_stats)
        self.btn_trade_stats.pack(pady=2)

        # 右侧：交易盈亏统计结果表格（Label网格，支持单元格级着色）
        stats_frame = ttk.Frame(trade_frame)
        stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # 列定义：(标题, 宽度, 对齐方式)
        self.trade_stats_columns = [
            ('账户', 7, tk.CENTER),
            ('银行->证券', 10, tk.E),
            ('证券->银行', 10, tk.E),
            ('净投入', 10, tk.E),
            ('已平仓盈亏', 10, tk.E),
            ('持仓估值', 10, tk.E),
            ('持仓浮盈', 10, tk.E),
        ]
        for col, (text, width, anchor) in enumerate(self.trade_stats_columns):
            tk.Label(stats_frame, text=text, width=width, anchor=anchor).grid(
                row=0, column=col, padx=1, pady=1)

        # 数据行容器，刷新时清空重建
        self.trade_stats_rows = ttk.Frame(stats_frame)
        self.trade_stats_rows.grid(row=1, column=0, columnspan=len(self.trade_stats_columns), sticky='ew')
    
    def setup_middle_frame(self):
        """
        设置中部筛选器和结果区

        包含：
        - 第一行：5个筛选器复选框
        - 第二行：开始筛选按钮
        - 第三行：Notebook四个tab（股票、ETF、持仓、历史）
        """
        middle_frame = ttk.LabelFrame(self.root, text="筛选器", padding=10)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 第一行：复选框
        filter_row = ttk.Frame(middle_frame)
        filter_row.pack(fill=tk.X)

        self.filter_vars = {}
        filters = [
            ('supertrend', 'SuperTrend'),
            ('vegas', 'Vegas'),
            ('bollingerband', 'BollingerBands'),
            ('occross', 'OpenClose Cross'),
            ('vp_slope', 'VolumeProfile')
        ]

        for name, label in filters:
            var = tk.BooleanVar(value=True)
            self.filter_vars[name] = var
            cb = ttk.Checkbutton(filter_row, text=label, variable=var)
            cb.pack(side=tk.LEFT, padx=15)

        # 第二行：按钮和查询
        btn_row = ttk.Frame(middle_frame)
        btn_row.pack(fill=tk.X, pady=(5, 0))

        self.btn_filter = ttk.Button(btn_row, text="开始筛选", width=12, command=self.on_filter)
        self.btn_filter.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_query = ttk.Button(btn_row, text="查询", width=6, command=self.on_query)
        self.btn_query.pack(side=tk.RIGHT, padx=(0, 10))
        self.query_entry = ttk.Entry(btn_row, width=10)
        self.query_entry.pack(side=tk.RIGHT, padx=5)

        # Notebook：股票 / ETF / 持仓 / 历史 四个tab
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=(18, 4))

        self.notebook = ttk.Notebook(middle_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        stock_tab = ttk.Frame(self.notebook)
        self.notebook.add(stock_tab, text='股票')
        self.stock_tree = self._make_tree(stock_tab)
        self.stock_tree.pack(fill=tk.BOTH, expand=True)
        # 股票tab右键菜单：买入
        self.stock_tree.bind('<Button-3>', lambda e: self._open_context_menu(e, [('买入', self._on_buy_holding)]))

        etf_tab = ttk.Frame(self.notebook)
        self.notebook.add(etf_tab, text='ETF')
        self.etf_tree = self._make_tree(etf_tab)
        self.etf_tree.pack(fill=tk.BOTH, expand=True)
        # ETFtab右键菜单：买入
        self.etf_tree.bind('<Button-3>', lambda e: self._open_context_menu(e, [('买入', self._on_buy_holding)]))

        holding_tab = ttk.Frame(self.notebook)
        self.notebook.add(holding_tab, text='持仓')
        self.holding_tree = self._make_tree(holding_tab)
        self.holding_tree.pack(fill=tk.BOTH, expand=True)
        # 持仓tab右键菜单：卖出
        self.holding_tree.bind('<Button-3>', lambda e: self._open_context_menu(e, [('卖出', self._on_sell_holding)]))

        history_tab = ttk.Frame(self.notebook)
        self.notebook.add(history_tab, text='历史')
        self.history_tree = self._make_tree(history_tab)
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        # 历史tab右键菜单：买入
        self.history_tree.bind('<Button-3>', lambda e: self._open_context_menu(e, [('买入', self._on_buy_holding)]))

        self.query_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.query_tab, text='查询')
        self.query_tree = self._make_tree(self.query_tab)
        self.query_tree.pack(fill=tk.BOTH, expand=True)
    
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
        self.btn_migrate.config(state=state)
        self.btn_trade_stats.config(state=state)
        self.btn_filter.config(state=state)
    
    def on_init_db(self):
        """
        初始化数据库按钮回调
        
        在后台线程中执行数据库初始化，完成后显示结果。
        """
        if self.is_running:
            return

        if not messagebox.askokcancel("确认", "此操作将清空数据库中所有数据（行情数据、指标缓存、股票信息等），确定继续？", parent=self.root):
            return

        self.is_running = True
        self.set_buttons_state(False)
        self.log_result("开始初始化数据库...")

        def run():
            try:
                init_db.init_database()
                self.root.after(0, lambda: self.log_result("数据库初始化成功！"))
                self.root.after(0, lambda: messagebox.showinfo("成功", "数据库初始化成功！", parent=self.root))
            except Exception as e:
                error_msg = str(e)
                logger.error(f"初始化失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"初始化失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"初始化失败: {msg}", parent=self.root))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def on_migrate_trades(self):
        """
        迁移交易流水按钮回调

        在后台线程中从 Excel 文件迁移交易流水到数据库，完成后显示结果。
        """
        if self.is_running:
            return

        self.is_running = True
        self.set_buttons_state(False)
        self.log_result("开始迁移交易流水...")

        def run():
            try:
                inserted, skipped = migrate_trades.migrate_trade_records()
                self.root.after(0, lambda: self.log_result(f"迁移完成！新增 {inserted} 条，跳过重复 {skipped} 条"))
                self.root.after(0, lambda: messagebox.showinfo("成功", f"迁移完成！\n新增: {inserted} 条\n跳过重复: {skipped} 条", parent=self.root))
            except Exception as e:
                error_msg = str(e)
                logger.error(f"迁移交易流水失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"迁移失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"迁移失败: {msg}", parent=self.root))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False

        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def on_trade_stats(self):
        """
        交易盈亏统计按钮回调

        从数据库 trade_records 表统计各账户的银行转入、银行转出、净投入、
        已完成交易的盈亏之和，以及当前持仓的估值与浮盈，显示在交易组右侧表格中。
        """
        try:
            cash_stats = migrate_trades.get_bank_cash_stats()
            pnl_stats = migrate_trades.get_trade_pnl_stats()
            valuation_stats = migrate_trades.get_holding_valuation_stats()
        except Exception as e:
            error_msg = str(e)
            logger.error(f"交易盈亏统计失败: {error_msg}")
            messagebox.showerror("错误", f"交易盈亏统计失败: {error_msg}", parent=self.root)
            return

        # 清空旧数据行
        for widget in self.trade_stats_rows.winfo_children():
            widget.destroy()

        for row_idx, row in enumerate(cash_stats):
            account = row['account']
            pnl = pnl_stats.get(account, 0.0)
            val = valuation_stats.get(account, {})
            market_value = val.get('market_value', 0.0)
            floating_pnl = val.get('floating_pnl', 0.0)
            cells = [
                account,
                f"{row['transfer_in']:,.2f}",
                f"{row['transfer_out']:,.2f}",
                f"{row['net_invest']:,.2f}",
                f"{pnl:,.2f}",
                f"{market_value:,.2f}",
                f"{floating_pnl:,.2f}",
            ]
            for col_idx, value in enumerate(cells):
                # 已平仓盈亏（第4列）和持仓浮盈（第6列）为负时标红
                negative = (col_idx == 4 and pnl < 0) or (col_idx == 6 and floating_pnl < 0)
                fg = 'red' if negative else None
                tk.Label(self.trade_stats_rows, text=value,
                         width=self.trade_stats_columns[col_idx][1],
                         anchor=self.trade_stats_columns[col_idx][2],
                         fg=fg).grid(row=row_idx, column=col_idx, padx=1, pady=1)

        self.log_result(f"交易盈亏统计完成，共 {len(cash_stats)} 个账户")
    
    def on_extract_data(self):
        """
        提取股票数据按钮回调
        
        在后台线程中执行数据提取，完成后更新股票列表。
        
        算法逻辑：
            1. 初始化HTTP会话和数据库
            2. 获取上证A股和ETF股票列表
            3. 对每只股票进行增量更新：
               - 如果数据库中没有该股票，下载最近5年的所有数据
               - 如果数据库中已有该股票，检测复权因子变动并更新
            4. 更新左侧股票列表
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.set_buttons_state(False)
        self.log_result("开始提取股票数据...")
        
        def run():
            try:
                extract_data.create_database(extract_data.DB_PATH)
                
                stock_list = extract_data.get_sh_a_stock_list()
                total = len(stock_list)
                
                if total == 0:
                    self.root.after(0, lambda: self.log_result("获取股票列表失败"))
                    return
                
                self.root.after(0, lambda: self.log_result(f"获取到 {total} 只股票"))
                
                from datetime import timedelta
                
                end_date = datetime.now()
                end_date_str = end_date.strftime('%Y-%m-%d')
                start_date = end_date - timedelta(days=extract_data.YEARS * 365)
                start_date_str = start_date.strftime('%Y-%m-%d')

                def progress(done, total_cnt, success, fail, message):
                    if done % 50 == 0 or done == total_cnt:
                        self.root.after(0, lambda m=message: self.log_result(m))

                success_count, fail_count, _ = extract_data.update_all_stock_data(
                    stock_list, start_date_str, end_date_str,
                    proxy=None, max_workers=3, progress_cb=progress
                )
                
                self.stock_list = read_data.get_all_stock_codes_with_names()
                self.root.after(0, lambda: self.log_result(f"提取完成！成功 {success_count} 只股票, 失败 {fail_count} 只"))
                self.root.after(0, lambda: messagebox.showinfo("成功", f"提取完成！\n成功: {success_count} 只股票\n失败: {fail_count} 只", parent=self.root))
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"提取失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"提取失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"提取失败: {msg}", parent=self.root))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
                self.is_running = False
        
        self.worker_thread = StoppableThread(target=run)
        self.worker_thread.start()
    
    def _make_tree(self, parent) -> ttk.Treeview:
        """创建标准的结果表格Treeview"""
        columns = ('code', 'name', 'supertrend', 'vegas', 'bollingerbands',
                   'occross', 'volumeprofile', 'total')
        tree = ttk.Treeview(parent, columns=columns, show='headings')

        tree.heading('code', text='代码')
        tree.heading('name', text='股票')
        tree.heading('supertrend', text='Supertrend')
        tree.heading('vegas', text='Vegas')
        tree.heading('bollingerbands', text='BollingerBands')
        tree.heading('occross', text='O/C Cross')
        tree.heading('volumeprofile', text='VolumeProfile')
        tree.heading('total', text='总分')

        tree.column('code', width=70, anchor=tk.CENTER)
        tree.column('name', width=100, anchor=tk.W)
        tree.column('supertrend', width=90, anchor=tk.CENTER)
        tree.column('vegas', width=80, anchor=tk.CENTER)
        tree.column('bollingerbands', width=100, anchor=tk.CENTER)
        tree.column('occross', width=80, anchor=tk.CENTER)
        tree.column('volumeprofile', width=100, anchor=tk.CENTER)
        tree.column('total', width=60, anchor=tk.CENTER)

        # 总分升降对应的字体颜色标签
        tree.tag_configure('up', foreground='green')
        tree.tag_configure('down', foreground='red')
        tree.tag_configure('flat', foreground='black')

        # 绑定双击事件打开K线图
        tree.bind('<Double-1>', self._on_tree_double_click)

        return tree

    def _populate_tree(self, tree, items):
        """填充Treeview数据"""
        tree.delete(*tree.get_children())
        for item in items:
            code = item.get('code', '')
            name = item.get('name', '')
            supertrend_val = item.get('supertrend', '--')
            vegas_val = item.get('vegas', '--')
            bb_val = item.get('bollingerbands', '--')
            occ_val = item.get('occross', '--')
            vp_val = item.get('volumeprofile', '--')
            total = item.get('total', '--')

            supertrend_str = str(supertrend_val) if supertrend_val != '--' else '--'
            vegas_str = str(vegas_val) if vegas_val != '--' else '--'
            bb_str = str(bb_val) if bb_val != '--' else '--'
            occ_str = str(occ_val) if occ_val != '--' else '--'
            vp_str = str(vp_val) if vp_val != '--' else '--'
            total_str = str(total) if isinstance(total, (int, float)) else str(total)

            trend = item.get('trend', 'flat')
            tree.insert('', tk.END, values=(
                code, name, supertrend_str, vegas_str, bb_str, occ_str, vp_str, total_str
            ), tags=(trend,))

    def _on_tree_double_click(self, event):
        """
        Treeview 双击事件处理：打开K线图窗口
        
        Args:
            event: 双击事件
        """
        tree = event.widget
        selection = tree.selection()
        if not selection:
            return
        
        item = tree.item(selection[0])
        values = item['values']
        if not values or len(values) < 2:
            return
        
        stock_code = str(values[0])
        stock_name = str(values[1])
        
        logger.info(f"双击股票: {stock_code} - {stock_name}")
        
        # 创建或更新K线图窗口
        if self.kline_window is None:
            self.kline_window = KLineWindow()
        
        # 直接调用 show()，内部会处理线程
        self.kline_window.show(stock_code, stock_name)

    def _open_context_menu(self, event, menu_items):
        """
        Treeview右键菜单：选中行并弹出菜单

        Args:
            event: 右键事件
            menu_items: [(菜单项文字, 命令), ...]
        """
        tree = event.widget
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        tree.selection_set(row_id)
        self.context_tree = tree
        self.context_row = row_id

        menu = tk.Menu(self.root, tearoff=0)
        for label, command in menu_items:
            menu.add_command(label=label, command=command)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_sell_holding(self):
        """
        右键卖出：在交易流水记录一条临时卖出交易

        卖出日期 = 当天；卖出数量 = 该股票各账户持仓数；
        价格 = 数据库最新收盘价；金额 = 收盘价 × 持仓数。
        """
        values = self.context_tree.item(self.context_row, 'values')
        if not values or len(values) < 2:
            return
        stock_code = str(values[0])
        stock_name = str(values[1])

        if not messagebox.askyesno(
                "确认卖出",
                f"确认按最新收盘价卖出 {stock_code} {stock_name}？\n将在交易流水中记录临时卖出交易。",
                parent=self.root):
            return

        trade_date = datetime.now().strftime('%Y-%m-%d')
        try:
            count, price = migrate_trades.sell_holding(stock_code, trade_date)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"记录卖出失败: {error_msg}")
            messagebox.showerror("错误", f"记录卖出失败: {error_msg}", parent=self.root)
            return

        if count == 0:
            messagebox.showwarning("警告", f"{stock_code} 无持仓或无法获取收盘价，未记录卖出。", parent=self.root)
            return

        self.log_result(f"已记录临时卖出 {stock_code} {stock_name}：{count} 条，卖出价格 {price}")
        messagebox.showinfo("成功", f"已记录临时卖出 {stock_name}\n卖出价格: {price}\n记录条数: {count}", parent=self.root)

    def _on_buy_holding(self):
        """
        右键买入：在交易流水记录一条临时买入交易

        买入日期 = 当天；买入数量 = 100；
        价格 = 数据库最新收盘价；金额 = 收盘价 × 100。
        """
        values = self.context_tree.item(self.context_row, 'values')
        if not values or len(values) < 2:
            return
        stock_code = str(values[0])
        stock_name = str(values[1])

        account = '40'
        if not messagebox.askyesno(
                "确认买入",
                f"确认按最新收盘价买入 {stock_code} {stock_name}？\n"
                f"数量: 100，将记录到 {account} 账户。",
                parent=self.root):
            return

        trade_date = datetime.now().strftime('%Y-%m-%d')
        try:
            count, price = migrate_trades.buy_holding(stock_code, trade_date, account=account, quantity=100)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"记录买入失败: {error_msg}")
            messagebox.showerror("错误", f"记录买入失败: {error_msg}", parent=self.root)
            return

        if count == 0:
            messagebox.showwarning("警告", f"{stock_code} 无法获取收盘价，未记录买入。", parent=self.root)
            return

        self.log_result(f"已记录临时买入 {stock_code} {stock_name}：{count} 条，买入价格 {price}")
        messagebox.showinfo("成功", f"已记录临时买入 {stock_name}\n买入价格: {price}\n数量: 100", parent=self.root)

    def update_result_list(self):
        """更新筛选结果表格显示（股票tab + ETF tab + 持仓tab + 历史tab + 查询tab）"""
        self._populate_tree(self.stock_tree, self.stock_filtered)
        self._populate_tree(self.etf_tree, self.etf_filtered)
        self._populate_tree(self.holding_tree, self.holding_list)
        self._populate_tree(self.history_tree, self.history_list)
        self._populate_tree(self.query_tree, self.query_list)
    
    def _check_vegas_pass(self, stock_code: str, date: str) -> bool:
        """检查Vegas是否通过筛选（多头排列且连续多头>=10天）"""
        vegas_df = vegas.get_stock_vegas(stock_code, date, days=800)
        if vegas_df is not None and not vegas_df.empty:
            if int(vegas_df.iloc[-1]['trend_direction']) != 1:
                return False
            # 计算连续多头天数
            bullish_streak = 0
            for j in range(len(vegas_df) - 1, -1, -1):
                if vegas_df.iloc[j]['trend_direction'] == 1:
                    bullish_streak += 1
                else:
                    break
            return bullish_streak >= 10
        return False

    def _check_vp_pass(self, stock_code: str, date: str) -> bool:
        """检查VP Slope是否通过筛选（slope_long > 0）"""
        vp_df = vp_slope.get_stock_slope(stock_code, date, days=150)
        if vp_df is not None and not vp_df.empty:
            return float(vp_df.iloc[-1]['slope_long']) > 0
        return False

    def _get_stock_name(self, stock_code: str) -> Optional[str]:
        """根据股票代码查找名称，找不到返回None"""
        for code, name in self.stock_list:
            if code == stock_code:
                return name or stock_code
        try:
            for code, name in read_data.get_all_stock_codes_with_names():
                if code == stock_code:
                    return name or stock_code
        except Exception as e:
            logger.warning(f"查询股票名称失败: {e}")
        return None

    def on_query(self):
        """查询按钮回调：计算当前日期下该股票的指标值并加入查询tab"""
        stock_code = self.query_entry.get().strip()
        if not stock_code:
            messagebox.showwarning("警告", "请输入股票代码！", parent=self.root)
            return

        date = datetime.now().strftime('%Y-%m-%d')

        name = self._get_stock_name(stock_code)
        if name is None:
            messagebox.showwarning("警告", f"未找到股票 {stock_code}！", parent=self.root)
            return

        def get_or_compute(col, compute_fn):
            v = get_indicator(stock_code, date, col)
            if v is not None:
                return v
            return compute_fn()

        st_val = get_or_compute('supertrend', lambda: round(supertrend._get_st_signal(stock_code, date) or 0))
        vegas_val = get_or_compute('vegas', lambda: _compute_vegas(stock_code, date))
        bb_val = get_or_compute('bollingerbands', lambda: _compute_bb(stock_code, date))
        occ_val = get_or_compute('openclosecross', lambda: _compute_occ(stock_code, date))
        vp_val = get_or_compute('volumeprofile', lambda: _compute_vp(stock_code, date))

        total = st_val + vegas_val + bb_val + occ_val + vp_val

        item = {
            'code': stock_code,
            'name': name,
            'supertrend': st_val,
            'vegas': vegas_val,
            'bollingerbands': bb_val,
            'occross': occ_val,
            'volumeprofile': vp_val,
            'total': total,
            'trend': self._get_total_trend(stock_code, total),
        }

        # 已查询过相同代码则更新，否则追加
        self.query_list = [it for it in self.query_list if it.get('code') != stock_code]
        self.query_list.append(item)

        self._populate_tree(self.query_tree, self.query_list)
        self.notebook.select(self.query_tab)
        self.log_result(f"查询 {stock_code} {item['name']}：总分 {total}")

    def _run_filter_pipeline(self, codes: list, active_filters: list, date: str, label: str) -> list:
        """
        对一组代码依次执行所有启用的筛选器，返回通过筛选的代码列表。

        Args:
            codes: 待筛选的代码列表
            active_filters: 启用的筛选器名称列表
            date: 筛选日期
            label: 日志标签（如"股票"或"ETF"）
        Returns:
            通过所有筛选器的代码列表
        """
        if not codes:
            return []

        if 'supertrend' in active_filters:
            self.root.after(0, lambda: self.log_result(f"[{label}] SuperTrend筛选 - 输入: {len(codes)}"))
            df = supertrend.filter_bullish_stocks(date, stock_codes=codes)
            codes = df['stock_code'].tolist() if not df.empty else []
            self.root.after(0, lambda c=len(codes): self.log_result(f"[{label}] SuperTrend筛选 - 输出: {c}"))
            if not codes:
                return []

        if 'vegas' in active_filters and codes:
            self.root.after(0, lambda: self.log_result(f"[{label}] Vegas通道筛选 - 输入: {len(codes)}"))
            df = vegas.filter_bullish_stocks(date, codes)
            codes = df['stock_code'].tolist() if not df.empty else []
            self.root.after(0, lambda c=len(codes): self.log_result(f"[{label}] Vegas通道筛选 - 输出: {c}"))
            if not codes:
                return []

        if 'bollingerband' in active_filters and codes:
            self.root.after(0, lambda: self.log_result(f"[{label}] 布林带筛选 - 输入: {len(codes)}"))
            df = bollingerband.filter_stocks_by_bandwidth(date, codes, threshold=10.0)
            codes = df['stock_code'].tolist() if not df.empty else []
            self.root.after(0, lambda c=len(codes): self.log_result(f"[{label}] 布林带筛选 - 输出: {c}"))
            if not codes:
                return []

        if 'occross' in active_filters and codes:
            self.root.after(0, lambda: self.log_result(f"[{label}] OCC指标筛选 - 输入: {len(codes)}"))
            df = occross.filter_bullish_stocks(date, codes)
            codes = df['stock_code'].tolist() if not df.empty else []
            self.root.after(0, lambda c=len(codes): self.log_result(f"[{label}] OCC指标筛选 - 输出: {c}"))
            if not codes:
                return []

        if 'vp_slope' in active_filters and codes:
            self.root.after(0, lambda: self.log_result(f"[{label}] VP Slope筛选 - 输入: {len(codes)}"))
            df = vp_slope.filter_stocks_by_slope(date, codes)
            codes = df['stock_code'].tolist() if not df.empty else []
            self.root.after(0, lambda c=len(codes): self.log_result(f"[{label}] VP Slope筛选 - 输出: {c}"))

        return codes

    def _score_and_build_items(self, codes: list, date: str, code_to_name: dict) -> list:
        """
        对筛选通过的代码计算趋势强度评分，构建展示用的item列表。

        Args:
            codes: 筛选通过的代码列表
            date: 筛选日期
            code_to_name: 代码→名称映射
        Returns:
            包含指标值的dict列表
        """
        if not codes:
            return []

        self.root.after(0, lambda: self.log_result("计算趋势强度评分..."))
        strength_df = trend_score.rank_stocks_by_strength(codes, date)

        if not strength_df.empty:
            items = []
            for _, row in strength_df.iterrows():
                items.append({
                    'code': row['stock_code'],
                    'name': row['stock_name'],
                    'supertrend': row.get('supertrend', 0),
                    'vegas': row.get('vegas', 0),
                    'bollingerbands': row.get('bollingerbands', 0),
                    'occross': row.get('openclosecross', 0),
                    'volumeprofile': row.get('volumeprofile', 0),
                    'total': row['strength_score'],
                })
            for item in items:
                item['trend'] = self._get_total_trend(item['code'], item['total'])
            return items
        else:
            return [{'code': c, 'name': code_to_name.get(c, ''), 'total': 0, 'trend': 'flat'}
                    for c in sorted(codes)]

    def _compute_indicators(self, codes: list, date: str):
        """为指定代码列表补算所有指标（未经过筛选循环，DB中无缓存）"""
        if not codes:
            return
        self.root.after(0, lambda n=len(codes): self.log_result(f"补算 {n} 只股票指标..."))
        for hcode in codes:
            supertrend._get_st_signal(hcode, date)
            vegas_df = vegas.get_stock_vegas(hcode, date, days=50)
            if vegas_df is not None and not vegas_df.empty:
                lr = vegas_df.iloc[-1]
                vp = (lr['close'] - lr['ema144']) / lr['ema144'] * 100
                save_indicator(hcode, date, 'vegas', round(vp))
            bb_df = bollingerband.get_stock_bollinger_band(hcode, date, days=50)
            if bb_df is not None and not bb_df.empty:
                bw = bb_df.iloc[-1]['bandwidth']
                if hasattr(bw, '__float__') and bw == bw:
                    save_indicator(hcode, date, 'bollingerbands', round(bw))
            occ_df = occross.get_stock_occ(hcode, date, days=50)
            if occ_df is not None and not occ_df.empty:
                lr = occ_df.iloc[-1]
                if lr['occ_open'] > 0:
                    op = (lr['occ_close'] - lr['occ_open']) / lr['occ_open'] * 1000
                    save_indicator(hcode, date, 'openclosecross', round(op))
            vp_df = vp_slope.get_stock_slope(hcode, date, days=150)
            if vp_df is not None and not vp_df.empty:
                lr = vp_df.iloc[-1]
                if lr['close'] > 0:
                    vpp = lr['slope_short'] / lr['close'] * 1000
                    save_indicator(hcode, date, 'volumeprofile', round(vpp))

    def _compute_total_for_date(self, stock_code: str, date: str) -> int:
        """计算某股票在指定日期的5指标总分（优先读缓存，未命中则计算并缓存）"""
        def get_or_compute(col, compute_fn):
            v = get_indicator(stock_code, date, col)
            if v is not None:
                return v
            return compute_fn()

        st_val = get_or_compute('supertrend', lambda: round(supertrend._get_st_signal(stock_code, date) or 0))
        vegas_val = get_or_compute('vegas', lambda: _compute_vegas(stock_code, date))
        bb_val = get_or_compute('bollingerbands', lambda: _compute_bb(stock_code, date))
        occ_val = get_or_compute('openclosecross', lambda: _compute_occ(stock_code, date))
        vp_val = get_or_compute('volumeprofile', lambda: _compute_vp(stock_code, date))
        return st_val + vegas_val + bb_val + occ_val + vp_val

    def _get_total_trend(self, stock_code: str, current_total: int) -> str:
        """根据最近两个交易日总分升降返回 'up' / 'down' / 'flat'"""
        dates = get_latest_trading_dates(stock_code, 2)
        if len(dates) < 2:
            return 'flat'

        prev_total = self._compute_total_for_date(stock_code, dates[1])
        if current_total > prev_total:
            return 'up'
        if current_total < prev_total:
            return 'down'
        return 'flat'

    def on_filter(self):
        """
        开始筛选按钮回调

        将股票（60开头）和ETF（5开头）分别筛选（包含持仓），持仓股票单独计算指标，
        已平仓股票（扣除持仓）单独计算指标。

        筛选流程：
            1. 加载数据（如未加载则从数据库读取）
            2. 按代码前缀分为股票（60开头）和ETF（5开头）
            3. 对股票和ETF分别执行筛选流水线（包含持仓股票）
            4. 对所有持仓股票直接计算指标（不筛选）
            5. 对所有已平仓股票（扣除持仓）直接计算指标（不筛选）
            6. 结果分别填充到四个tab
        """
        if self.is_running:
            return

        if not self.stock_list:
            self.stock_list = read_data.get_all_stock_codes_with_names()
            if not self.stock_list:
                messagebox.showwarning("警告", "数据库中没有股票数据，请先提取股票数据！", parent=self.root)
                return

        active_filters = [name for name, var in self.filter_vars.items() if var.get()]
        if not active_filters:
            messagebox.showwarning("警告", "请至少选择一个筛选器！", parent=self.root)
            return

        self.is_running = True
        self.set_buttons_state(False)
        self.log_result(f"开始筛选，启用筛选器: {', '.join(active_filters)}")

        def run():
            try:
                date = datetime.now().strftime('%Y-%m-%d')
                all_codes = [code for code, name in self.stock_list]
                code_to_name = {code: name for code, name in self.stock_list}

                # 读取持仓
                holding_codes = set(get_holding_codes())

                # 按前缀分组（扣除持仓）
                stock_codes = [c for c in all_codes if c.startswith('60') and c not in holding_codes]
                etf_codes = [c for c in all_codes if c.startswith('5') and c not in holding_codes]
                holding_list = [c for c in all_codes if c in holding_codes]

                self.root.after(0, lambda: self.log_result(
                    f"分组: 股票 {len(stock_codes)} 只, ETF {len(etf_codes)} 只, 持仓 {len(holding_list)} 只"))

                # === 股票筛选（60开头，扣除持仓）===
                self.root.after(0, lambda: self.log_result("=== 股票筛选开始 ==="))
                stock_filtered = self._run_filter_pipeline(stock_codes, active_filters, date, '股票')
                stock_items = self._score_and_build_items(stock_filtered, date, code_to_name)

                # === ETF筛选（5开头，扣除持仓）===
                self.root.after(0, lambda: self.log_result("=== ETF筛选开始 ==="))
                etf_filtered = self._run_filter_pipeline(etf_codes, active_filters, date, 'ETF')
                etf_items = self._score_and_build_items(etf_filtered, date, code_to_name)

                # === 持仓股票计算（不筛选，直接计算指标）===
                self.root.after(0, lambda: self.log_result("=== 持仓计算开始 ==="))
                if holding_list:
                    self._compute_indicators(holding_list, date)
                    holding_items = self._score_and_build_items(holding_list, date, code_to_name)
                else:
                    holding_items = []

                # === 历史（已平仓）股票计算（扣除持仓）===
                self.root.after(0, lambda: self.log_result("=== 历史(已平仓)计算开始 ==="))
                closed_codes = migrate_trades.get_closed_position_codes()
                history_codes = [c for c in closed_codes
                                 if c not in holding_codes and c in code_to_name]
                if history_codes:
                    self._compute_indicators(history_codes, date)
                    history_items = self._score_and_build_items(history_codes, date, code_to_name)
                else:
                    history_items = []

                # 更新结果
                self.stock_filtered = stock_items
                self.etf_filtered = etf_items
                self.holding_list = holding_items
                self.history_list = history_items
                self.root.after(0, self.update_result_list)
                self.root.after(0, lambda: self.log_result(
                    f"筛选完成！股票 {len(stock_items)} 只, ETF {len(etf_items)} 只, "
                    f"持仓 {len(holding_items)} 只, 历史 {len(history_items)} 只"))

            except Exception as e:
                error_msg = str(e)
                logger.error(f"筛选失败: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self.log_result(f"筛选失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"筛选失败: {msg}", parent=self.root))
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
