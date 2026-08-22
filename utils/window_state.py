# -*- coding: utf-8 -*-
"""
窗口状态持久化模块

负责保存和恢复 GUI 窗口、K线窗口的位置和尺寸，
以 JSON 文件形式存储在项目根目录。
"""

import json
import os

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'window_state.json',
)


def load_window_state(key: str):
    """
    读取指定窗口的保存状态

    Args:
        key: 窗口标识（如 'gui'、'kline'）

    Returns:
        保存的状态字典，不存在时返回 None
    """
    try:
        if not os.path.exists(CONFIG_PATH):
            return None
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(key)
    except Exception:
        return None


def save_window_state(key: str, state: dict) -> None:
    """
    保存指定窗口的状态

    Args:
        key: 窗口标识（如 'gui'、'kline'）
        state: 状态字典
    """
    try:
        data = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data[key] = state
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass