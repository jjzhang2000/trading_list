#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块

提供统一的日志配置，用于所有模块的日志输出。
"""

import logging
import sys


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    创建并配置一个 logger
    
    Args:
        name: logger 名称
        level: 日志级别，默认为 INFO
    
    Returns:
        配置好的 Logger 对象
    
    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("这是一条信息日志")
        >>> logger.debug("这是一条调试日志")
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的 logger
    
    Args:
        name: logger 名称
    
    Returns:
        Logger 对象
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息日志")
    """
    return setup_logger(name)
