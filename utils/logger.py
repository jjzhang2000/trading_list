#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块

提供统一的日志配置，用于所有模块的日志输出。
日志同时输出到控制台和文件。
"""

import logging
import sys
import os
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')


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
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    log_filename = datetime.now().strftime('%Y-%m-%d.log')
    log_filepath = os.path.join(LOG_DIR, log_filename)
    
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
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


def get_log_dir() -> str:
    """
    获取日志文件目录路径
    
    Returns:
        日志目录的绝对路径
    """
    return os.path.abspath(LOG_DIR)
