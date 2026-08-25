#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易流水迁移模块
从 Excel 文件（含两个账户的 sheet）读取交易流水，迁移到 SQLite 数据库的 trade_records 表。

两个账户 sheet 的共有字段：
    成交日期、业务名称、证券代码、证券名称、成交价格、成交数量、发生金额

迁移规则：
    1. 成交日期 int YYYYMMDD -> 'YYYY-MM-DD'
    2. 证券代码 float 600708.0 -> '600708'，空 -> NULL
    3. 证券代码为空时，从证券名称反查 stock_info 补全
    4. 成交价格/成交数量 '---' -> NULL
    5. 成交数量统一符号（正=买入，负=卖出）：弓长表"证券卖出"取负
    6. 资金类交易（证券代码、证券名称均为空）成交价格/数量置 NULL
    7. 按业务字段组合去重，避免重复迁入
"""

import os
import sys
import sqlite3
from typing import List, Optional, Tuple

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'stock_data.db')
EXCEL_PATH = r'D:\OneDrive\文档\个人财务\交易流水.xlsx'

# sheet 名与账户标识的映射
SHEET_ACCOUNTS = [
    ('交易流水(弓长)', '弓长'),
    ('交易流水(40)', '40'),
]


def create_trade_table(db_path: str = DB_PATH):
    """创建交易流水表（幂等）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            account        TEXT NOT NULL,
            trade_date     DATE NOT NULL,
            business_name  TEXT,
            stock_code     TEXT,
            trade_price    REAL,
            trade_quantity INTEGER,
            amount         REAL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trade_records_account_date ON trade_records(account, trade_date)')
    conn.commit()
    conn.close()


def _to_date_str(value) -> Optional[str]:
    """成交日期 int YYYYMMDD -> 'YYYY-MM-DD'"""
    if pd.isna(value):
        return None
    s = str(int(value))
    if len(s) == 8:
        return f'{s[:4]}-{s[4:6]}-{s[6:8]}'
    return None


def _to_text(value) -> Optional[str]:
    """转为文本，空 -> None"""
    if pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def _to_stock_code(value) -> Optional[str]:
    """证券代码 float 600708.0 -> '600708'"""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s if s else None


def _to_number(value) -> Optional[float]:
    """数值转换，'---' 或空 -> None"""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s in ('---', ''):
        return None
    try:
        return round(float(s), 4)
    except ValueError:
        return None


def _normalize_row(row, account: str, name_code_map: dict) -> Optional[Tuple]:
    """将一行原始数据归一化为统一字段，返回 None 表示跳过（缺日期）"""
    trade_date = _to_date_str(row.get('成交日期'))
    if trade_date is None:
        return None

    business_name = _to_text(row.get('业务名称'))
    stock_code = _to_stock_code(row.get('证券代码'))
    stock_name = _to_text(row.get('证券名称'))

    # 证券代码为空时，从证券名称反查 stock_info 补全
    if stock_code is None and stock_name is not None:
        stock_code = name_code_map.get(stock_name)

    trade_price = _to_number(row.get('成交价格'))
    trade_quantity = _to_number(row.get('成交数量'))
    amount = _to_number(row.get('发生金额'))

    # 成交数量统一符号：弓长表"证券卖出"取负（正=买入，负=卖出）
    if account == '弓长' and business_name == '证券卖出' and trade_quantity is not None:
        trade_quantity = -trade_quantity

    # 资金类交易（证券代码、证券名称均为空）：成交价格/数量置空
    if stock_code is None and stock_name is None:
        trade_price = None
        trade_quantity = None

    # 成交数量转为整数
    if trade_quantity is not None:
        trade_quantity = int(trade_quantity)

    return (account, trade_date, business_name, stock_code, trade_price, trade_quantity, amount)


def _load_name_code_map(conn) -> dict:
    """加载 stock_info 表 证券名称 -> 证券代码 映射"""
    cursor = conn.cursor()
    cursor.execute("SELECT stock_code, stock_name FROM stock_info WHERE stock_name IS NOT NULL AND stock_name != ''")
    return {name: code for code, name in cursor.fetchall()}


def _load_existing_keys(conn, account: str) -> set:
    """读取库中该账户已存在的记录指纹集合（用于去重）"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT trade_date, business_name, stock_code, trade_price, trade_quantity, amount
        FROM trade_records WHERE account = ?
    ''', (account,))
    return set(cursor.fetchall())


def migrate_trade_records(excel_path: str = EXCEL_PATH, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    从 Excel 迁移交易流水到数据库

    Args:
        excel_path: Excel 文件路径
        db_path: 数据库路径

    Returns:
        (新插入记录数, 跳过的重复记录数)
    """
    create_trade_table(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    inserted_total = 0
    skipped_total = 0

    try:
        name_code_map = _load_name_code_map(conn)

        for sheet, account in SHEET_ACCOUNTS:
            df = pd.read_excel(excel_path, sheet_name=sheet)
            existing_keys = _load_existing_keys(conn, account)

            records = []
            skipped = 0
            for _, row in df.iterrows():
                rec = _normalize_row(row, account, name_code_map)
                if rec is None:
                    continue
                key = rec[1:]  # 去掉 account，与库中读取的指纹对齐
                if key in existing_keys:
                    skipped += 1
                    continue
                records.append(rec)
                existing_keys.add(key)

            if records:
                cursor.executemany('''
                    INSERT INTO trade_records
                        (account, trade_date, business_name, stock_code, trade_price, trade_quantity, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', records)
                conn.commit()

            inserted_total += len(records)
            skipped_total += skipped
            logger.info(f"账户[{account}] 迁移完成：新增 {len(records)} 条，跳过重复 {skipped} 条")

        # 迁移完成后，删除所有临时交易记录（GUI右键买卖产生）
        cursor.execute(
            "DELETE FROM trade_records WHERE business_name IN ('证券买入(临时)', '证券卖出(临时)')"
        )
        deleted_temp = cursor.rowcount
        conn.commit()
        if deleted_temp > 0:
            logger.info(f"已删除 {deleted_temp} 条临时交易记录")
    finally:
        conn.close()

    return inserted_total, skipped_total


def get_bank_cash_stats(db_path: str = DB_PATH) -> list:
    """
    统计各账户银行现金流水：账户、银行转入、银行转出、净投入

    转入业务（金额为正）：银行转证券、银行转存
    转出业务（金额为负，返回时取绝对值）：证券转银行、银行转取

    Args:
        db_path: 数据库路径

    Returns:
        [{'account': 账户, 'transfer_in': 银行转入, 'transfer_out': 银行转出, 'net_invest': 净投入}, ...]
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT account,
                   SUM(CASE WHEN business_name IN ('银行转证券', '银行转存') THEN amount ELSE 0 END) AS transfer_in,
                   SUM(CASE WHEN business_name IN ('证券转银行', '银行转取') THEN -amount ELSE 0 END) AS transfer_out
            FROM trade_records
            WHERE business_name IN ('银行转证券', '证券转银行', '银行转存', '银行转取')
            GROUP BY account
            ORDER BY account
        ''')
        rows = cursor.fetchall()
    finally:
        conn.close()

    result = []
    for account, transfer_in, transfer_out in rows:
        transfer_in = transfer_in or 0.0
        transfer_out = transfer_out or 0.0
        result.append({
            'account': account,
            'transfer_in': round(transfer_in, 2),
            'transfer_out': round(transfer_out, 2),
            'net_invest': round(transfer_in - transfer_out, 2),
        })
    return result


def get_trade_pnl_stats(db_path: str = DB_PATH) -> dict:
    """
    统计各账户已完成交易的盈亏之和（含资金类收支）

    采用移动平均成本法，按账户、股票代码分组，按交易日期顺序处理：
    - 证券买入：增加持仓，累计成本（发生金额为负，转为正成本）
    - 证券卖出：按平均成本计算已实现盈亏，并减少持仓
    - 红股入账：增加股数，成本为0
    - 资金类业务（股息入账、红利入账、利息归本及相关税费）：直接累加发生金额

    Args:
        db_path: 数据库路径

    Returns:
        {账户: 盈亏之和}，仅包含发生过买卖或资金类收支的账户

    已知待办（TODO）：
        交易流水中的「股份转出」「配股权证」等拆股/转股类业务，会改变持仓股数
        但发生金额为 0。当前实现未处理这些股数变化，它们会落入下方 else 分支
        直接累加金额（金额为 0，因此不影响盈亏数值）。等未来出现这类业务实际
        影响盈亏（例如拆股后卖出）时，再补充相应的股数增减逻辑。
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT account, stock_code, trade_date, business_name, trade_quantity, amount
            FROM trade_records
            WHERE business_name NOT IN ('银行转证券', '证券转银行', '银行转存', '银行转取')
            ORDER BY account, stock_code, trade_date, id
        ''')
        rows = cursor.fetchall()
    finally:
        conn.close()

    pnl_by_account = {}
    positions = {}  # {account: {stock_code: [持仓数量, 持仓成本]}}

    for account, stock_code, _trade_date, business_name, qty, amount in rows:
        qty = qty or 0
        amount = amount or 0.0
        pos = positions.setdefault(account, {}).setdefault(stock_code, [0, 0.0])

        if business_name == '红股入账':
            # 送股：增加股数，成本为0
            pos[0] += qty
        elif business_name.startswith('证券买入'):
            # 买入：增加持仓，累计成本（发生金额为负，取反为正成本）
            pos[0] += qty
            pos[1] += -amount
        elif business_name.startswith('证券卖出'):
            # 卖出：按平均成本计算已实现盈亏
            sell_qty = -qty
            sell_income = amount
            avg_cost = pos[1] / pos[0] if pos[0] > 0 else 0.0
            realized = sell_income - avg_cost * sell_qty
            pnl_by_account[account] = pnl_by_account.get(account, 0.0) + realized
            pos[0] -= sell_qty
            pos[1] -= avg_cost * sell_qty
            if pos[0] <= 0:
                pos[0] = 0
                pos[1] = 0.0
        else:
            # 资金类业务：股息、红利、利息及相关税费，直接累加发生金额
            # 注意：此处也包含「股份转出」「配股权证」等拆股/转股类业务，
            # 它们 amount 为 0 且暂未处理股数变化（见函数 docstring 的 TODO）。
            pnl_by_account[account] = pnl_by_account.get(account, 0.0) + amount

    return pnl_by_account


def get_holding_valuation_stats(db_path: str = DB_PATH) -> dict:
    """
    统计各账户当前持仓的估值与浮盈（按最近交易日收盘价）

    采用与 get_trade_pnl_stats 相同的移动平均成本法维护各账户持仓，
    对净持仓数量>0的股票，取 stock_daily 中该股票最近交易日的收盘价计算：
    - market_value：Σ(持仓数量 × 最新收盘价)
    - cost：持仓累计成本
    - floating_pnl：market_value - cost

    资金类业务（股息、红利、利息）以及「配股权证」「股份转出」等
    拆股/转股类业务不改变持仓股数，故跳过。

    Args:
        db_path: 数据库路径

    Returns:
        {账户: {'market_value': 持仓估值, 'cost': 持仓成本, 'floating_pnl': 持仓浮盈}, ...}
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT account, stock_code, trade_date, business_name, trade_quantity, amount
            FROM trade_records
            WHERE stock_code IS NOT NULL
              AND business_name NOT IN ('银行转证券', '证券转银行', '银行转存', '银行转取')
            ORDER BY account, stock_code, trade_date, id
        ''')
        rows = cursor.fetchall()

        positions = {}  # {account: {stock_code: [持仓数量, 持仓成本]}}
        for account, stock_code, _trade_date, business_name, qty, amount in rows:
            qty = qty or 0
            amount = amount or 0.0
            pos = positions.setdefault(account, {}).setdefault(stock_code, [0, 0.0])

            if business_name == '红股入账':
                # 送股：增加股数，成本为0
                pos[0] += qty
            elif business_name.startswith('证券买入'):
                # 买入：增加持仓，累计成本（发生金额为负，取反为正成本）
                pos[0] += qty
                pos[1] += -amount
            elif business_name.startswith('证券卖出'):
                # 卖出：按平均成本减少持仓与成本
                sell_qty = -qty
                avg_cost = pos[1] / pos[0] if pos[0] > 0 else 0.0
                pos[0] -= sell_qty
                pos[1] -= avg_cost * sell_qty
                if pos[0] <= 0:
                    pos[0] = 0
                    pos[1] = 0.0
            # 其余业务（股息、红利、利息、配股权证、股份转出等）不改变持仓股数

        result = {}
        for account, pos_map in positions.items():
            market_value = 0.0
            cost = 0.0
            for stock_code, (qty, _cost) in pos_map.items():
                if qty <= 0:
                    continue
                cost += _cost
                cursor.execute(
                    'SELECT close FROM stock_daily WHERE stock_code = ? ORDER BY date DESC LIMIT 1',
                    (stock_code,)
                )
                row = cursor.fetchone()
                if row is not None and row[0] is not None:
                    market_value += qty * float(row[0])

            result[account] = {
                'market_value': round(market_value, 2),
                'cost': round(cost, 2),
                'floating_pnl': round(market_value - cost, 2),
            }
    finally:
        conn.close()

    return result


def get_holding_position_codes(db_path: str = DB_PATH) -> List[str]:
    """
    获取当前持仓股票代码（净持仓数量>0的股票）

    统计 trade_records 中各股票代码的成交数量之和，净数量>0表示当前仍持有。
    只统计会真实改变持仓股数的业务（证券买入/证券卖出/红股入账），
    排除「配股权证」「股份转出」等未处理的拆股/转股类业务以及资金类业务。

    Args:
        db_path: 数据库路径

    Returns:
        持仓股票代码列表（按代码升序）
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT stock_code
            FROM trade_records
            WHERE stock_code IS NOT NULL
              AND (business_name LIKE '证券买入%'
                   OR business_name LIKE '证券卖出%'
                   OR business_name = '红股入账')
            GROUP BY stock_code
            HAVING SUM(trade_quantity) > 0
            ORDER BY stock_code
        ''')
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_closed_position_codes(db_path: str = DB_PATH) -> List[str]:
    """
    获取所有已平仓股票代码（净持仓为0的股票）

    统计 trade_records 中各股票代码的成交数量之和，净数量为0表示已全部卖出（平仓）。
    只统计会真实改变持仓股数的业务（证券买入/证券卖出/红股入账），
    排除「配股权证」「股份转出」等未处理的拆股/转股类业务以及资金类业务。

    Args:
        db_path: 数据库路径

    Returns:
        已平仓股票代码列表（按代码升序）
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT stock_code
            FROM trade_records
            WHERE stock_code IS NOT NULL
              AND (business_name LIKE '证券买入%'
                   OR business_name LIKE '证券卖出%'
                   OR business_name = '红股入账')
            GROUP BY stock_code
            HAVING SUM(trade_quantity) = 0
            ORDER BY stock_code
        ''')
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def add_temp_sell_record(stock_code: str, trade_date: str, close_price: float,
                         quantities: List[tuple], db_path: str = DB_PATH) -> int:
    """
    为指定股票记录临时卖出交易（持仓tab右键"卖出"功能）。

    Args:
        stock_code: 股票代码
        trade_date: 交易日期（YYYY-MM-DD）
        close_price: 卖出价格（最新收盘价）
        quantities: [(account, 持仓数量), ...]
        db_path: 数据库路径

    Returns:
        插入的交易记录条数
    """
    create_trade_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        records = []
        for account, qty in quantities:
            qty = int(qty)
            if qty <= 0:
                continue
            records.append((
                account,
                trade_date,
                '证券卖出(临时)',   # 标记为临时记录，便于与Excel迁移的正式流水区分
                stock_code,
                round(close_price, 4),
                -qty,               # 卖出数量取负（正=买入，负=卖出）
                round(close_price * qty, 2),  # 交易金额 = 收盘价 × 持仓数
            ))
        if records:
            cursor.executemany('''
                INSERT INTO trade_records
                    (account, trade_date, business_name, stock_code, trade_price, trade_quantity, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', records)
            conn.commit()
        return len(records)
    finally:
        conn.close()


def sell_holding(stock_code: str, trade_date: str, db_path: str = DB_PATH) -> Tuple[int, float]:
    """
    持仓右键卖出：按数据库最新收盘价记录临时卖出交易。

    卖出数量 = 该股票在各账户的净持仓数量（跨账户分别记录）；
    卖出价格 = 数据库中的最新收盘价；
    交易金额 = 收盘价 × 持仓数。

    Args:
        stock_code: 股票代码
        trade_date: 交易日期（YYYY-MM-DD）
        db_path: 数据库路径

    Returns:
        (插入记录数, 卖出价格)；无持仓或无法获取收盘价时插入记录数为0
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # 各账户净持仓数量（只统计改变持仓股数的业务）
        cursor.execute('''
            SELECT account, SUM(trade_quantity)
            FROM trade_records
            WHERE stock_code = ?
              AND (business_name LIKE '证券买入%'
                   OR business_name LIKE '证券卖出%'
                   OR business_name = '红股入账')
            GROUP BY account
            HAVING SUM(trade_quantity) > 0
        ''', (stock_code,))
        quantities = [(account, int(qty)) for account, qty in cursor.fetchall()]

        # 数据库最新收盘价
        cursor.execute(
            'SELECT close FROM stock_daily WHERE stock_code = ? ORDER BY date DESC LIMIT 1',
            (stock_code,)
        )
        row = cursor.fetchone()
        if not quantities or row is None or row[0] is None:
            return 0, 0.0
        close_price = float(row[0])
    finally:
        conn.close()

    count = add_temp_sell_record(stock_code, trade_date, close_price, quantities, db_path)
    return count, close_price


def add_temp_buy_record(stock_code: str, trade_date: str, close_price: float,
                        account: str, quantity: int = 100,
                        db_path: str = DB_PATH) -> int:
    """
    为指定股票记录临时买入交易（股票/ETF/历史tab右键"买入"功能）。

    Args:
        stock_code: 股票代码
        trade_date: 交易日期（YYYY-MM-DD）
        close_price: 买入价格（最新收盘价）
        account: 归属账户
        quantity: 买入数量，默认100
        db_path: 数据库路径

    Returns:
        插入的交易记录条数（0或1）
    """
    create_trade_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        quantity = int(quantity)
        if quantity <= 0:
            return 0
        # 买入：数量为正，发生金额为负（与Excel迁移的买入流水符号一致）
        record = (
            account,
            trade_date,
            '证券买入(临时)',   # 标记为临时记录，便于与Excel迁移的正式流水区分
            stock_code,
            round(close_price, 4),
            quantity,
            round(-(close_price * quantity), 2),  # 交易金额 = -收盘价 × 数量
        )
        cursor.execute('''
            INSERT INTO trade_records
                (account, trade_date, business_name, stock_code, trade_price, trade_quantity, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', record)
        conn.commit()
        return 1
    finally:
        conn.close()


def buy_holding(stock_code: str, trade_date: str, account: str = '40',
                quantity: int = 100, db_path: str = DB_PATH) -> Tuple[int, float]:
    """
    右键买入：按数据库最新收盘价记录临时买入交易。

    买入数量固定（默认100股），卖出价格 = 数据库中的最新收盘价，
    交易金额 = 收盘价 × 数量。

    Args:
        stock_code: 股票代码
        trade_date: 交易日期（YYYY-MM-DD）
        account: 归属账户
        quantity: 买入数量，默认100
        db_path: 数据库路径

    Returns:
        (插入记录数, 买入价格)；无法获取收盘价时插入记录数为0
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT close FROM stock_daily WHERE stock_code = ? ORDER BY date DESC LIMIT 1',
            (stock_code,)
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return 0, 0.0
        close_price = float(row[0])
    finally:
        conn.close()

    count = add_temp_buy_record(stock_code, trade_date, close_price, account, quantity, db_path)
    return count, close_price


def main():
    """命令行测试"""
    inserted, skipped = migrate_trade_records()
    print(f"迁移完成：新增 {inserted} 条，跳过重复 {skipped} 条")


if __name__ == '__main__':
    main()
