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
from typing import Optional, Tuple

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


def main():
    """命令行测试"""
    inserted, skipped = migrate_trade_records()
    print(f"迁移完成：新增 {inserted} 条，跳过重复 {skipped} 条")


if __name__ == '__main__':
    main()
