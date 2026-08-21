# -*- coding: utf-8 -*-
"""
K线图独立窗口脚本
通过命令行参数接收股票代码，显示K线图窗口
"""

import sys
import traceback

def main():
    """主函数"""
    try:
        print(f"[DEBUG] 启动K线图窗口: {sys.argv[1]} - {sys.argv[2]}")
        sys.stdout.flush()
        
        import webview
        from kline_window import KLineAPI, get_kline_html
        
        if len(sys.argv) < 3:
            print("用法: python kline_standalone.py <股票代码> <股票名称>")
            sys.exit(1)
        
        stock_code = sys.argv[1]
        stock_name = sys.argv[2]
        
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
        
        # 创建窗口
        window = webview.create_window(
            title=f'{stock_code} - {stock_name} K线图',
            html=html,
            width=1000,
            height=700,
            js_api=api,
            resizable=True
        )
        
        print(f"[DEBUG] 设置回调...")
        sys.stdout.flush()
        
        # 设置窗口加载完成回调
        def on_loaded():
            print(f"[DEBUG] K线图窗口已加载: {stock_code}")
            sys.stdout.flush()
            # 等待 JavaScript 完全初始化
            import time
            time.sleep(0.3)
            try:
                window.evaluate_js(f'loadKLine("{stock_code}")')
                print(f"[DEBUG] K线数据加载成功")
                sys.stdout.flush()
            except Exception as e:
                print(f"[ERROR] 加载K线数据失败: {e}")
                sys.stdout.flush()
        
        window.events.loaded += on_loaded
        
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


if __name__ == '__main__':
    main()
