# -*- coding: utf-8 -*-
"""
K线图独立窗口脚本
支持多tab显示，通过队列接收命令动态添加股票
"""

import sys
import traceback
import multiprocessing
import time
import threading

from utils.window_state import load_window_state, save_window_state


def run_kline_window(cmd_queue):
    """
    K线图窗口主函数（供 multiprocessing.Process 调用）
    
    Args:
        cmd_queue: 命令队列，用于接收添加/关闭股票的命令
    """
    try:
        print(f"[DEBUG] 启动K线图窗口进程，PID: {multiprocessing.current_process().pid}")
        sys.stdout.flush()
        
        import webview
        from kline_window import KLineAPI, get_kline_html
        
        print(f"[DEBUG] 创建API实例...")
        sys.stdout.flush()
        
        # 创建 API 实例
        api = KLineAPI()
        
        print(f"[DEBUG] 生成HTML...")
        sys.stdout.flush()
        
        # 生成 HTML
        html = get_kline_html()
        
        print(f"[DEBUG] 创建webview窗口...")
        sys.stdout.flush()
        
        # 恢复上次保存的窗口位置和尺寸
        saved = load_window_state('kline') or {}

        # 创建窗口
        window = webview.create_window(
            title='K线图',
            html=html,
            width=saved.get('width', 1000),
            height=saved.get('height', 700),
            x=saved.get('x'),
            y=saved.get('y'),
            js_api=api,
            resizable=True
        )
        
        print(f"[DEBUG] 设置回调...")
        sys.stdout.flush()
        
        # 窗口加载完成标志
        window_loaded = False
        
        # 设置窗口加载完成回调
        def on_loaded():
            nonlocal window_loaded
            print(f"[DEBUG] K线图窗口已加载")
            sys.stdout.flush()
            window_loaded = True
            # 等待 JavaScript 完全初始化
            time.sleep(0.3)
        
        window.events.loaded += on_loaded
        
        # 关闭前保存窗口位置和尺寸
        def on_closing():
            try:
                save_window_state('kline', {
                    'x': window.x,
                    'y': window.y,
                    'width': window.width,
                    'height': window.height,
                })
            except Exception as e:
                print(f"[ERROR] 保存窗口状态失败: {e}")
                sys.stdout.flush()
            return True
        
        window.events.closing += on_closing
        
        print(f"[DEBUG] 启动命令监听线程...")
        sys.stdout.flush()
        
        # 命令监听函数
        def listen_commands():
            print(f"[DEBUG] 开始监听命令队列...")
            sys.stdout.flush()
            
            while True:
                try:
                    # 非阻塞获取命令
                    try:
                        cmd = cmd_queue.get(timeout=0.5)
                    except:
                        continue
                    
                    if cmd is None:
                        print(f"[DEBUG] 收到退出信号")
                        sys.stdout.flush()
                        break
                    
                    action = cmd.get('action')
                    
                    if action == 'close':
                        print(f"[DEBUG] 收到关闭命令")
                        sys.stdout.flush()
                        window.destroy()
                        break
                    
                    elif action == 'show_stock':
                        stock_code = cmd.get('stock_code')
                        stock_name = cmd.get('stock_name')
                        print(f"[DEBUG] 收到显示股票命令: {stock_code} - {stock_name}")
                        sys.stdout.flush()
                        
                        # 等待窗口加载完成
                        if not window_loaded:
                            print(f"[DEBUG] 等待窗口加载...")
                            sys.stdout.flush()
                            for _ in range(10):
                                time.sleep(0.1)
                                if window_loaded:
                                    break
                        
                        # 调用 JavaScript 函数显示股票
                        try:
                            window.evaluate_js(f'showStock("{stock_code}", "{stock_name}")')
                            print(f"[DEBUG] 已调用 showStock: {stock_code}")
                            sys.stdout.flush()
                        except Exception as e:
                            print(f"[ERROR] 调用 showStock 失败: {e}")
                            sys.stdout.flush()
                    
                except Exception as e:
                    print(f"[ERROR] 命令监听异常: {e}")
                    traceback.print_exc()
                    sys.stdout.flush()
        
        # 启动命令监听线程
        cmd_thread = threading.Thread(target=listen_commands, daemon=True)
        cmd_thread.start()
        
        print(f"[DEBUG] 启动webview事件循环...")
        sys.stdout.flush()
        
        # 启动 webview 事件循环（阻塞）
        webview.start()
        
        print(f"[DEBUG] webview事件循环结束")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"[ERROR] 发生异常: {e}")
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)


def main():
    """主函数（独立运行模式）"""
    try:
        if len(sys.argv) < 2:
            print("用法: python kline_standalone.py <队列名称>")
            sys.exit(1)
        
        queue_name = sys.argv[1]
        print(f"[DEBUG] 启动K线图窗口，队列: {queue_name}")
        sys.stdout.flush()
        
        # 获取队列引用
        cmd_queue = multiprocessing.Queue(queue_name)
        
        # 运行窗口
        run_kline_window(cmd_queue)
        
    except Exception as e:
        print(f"[ERROR] 发生异常: {e}")
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)


if __name__ == '__main__':
    main()
