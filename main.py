import settings
import work_flow
import akshare as ak
import tushare as ts
import pandas as pd
import requests
import os
import traceback # 用于打印详细错误堆栈
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. 超级防抖补丁 (解决 Read timed out)
# ==========================================
def apply_retry_strategy():
    retry_strategy = Retry(
        total=10, 
        backoff_factor=2, 
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    
    _original_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 90 # 90秒超长耐心
        return _original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request

apply_retry_strategy()

# ==========================================
# 2. 稳健获取主板名单逻辑
# ==========================================
def get_robust_main_board_list():
    codes = []
    # 通道 A: 极速接口
    try:
        print("🔍 尝试接口 A (Akshare Code List)...")
        df = ak.stock_info_a_code_name()
        codes = df['code'].tolist()
    except Exception as e:
        print(f"⚠️ 接口 A 失败: {e}")

    # 通道 B: Tushare 备份
    if not codes:
        try:
            print("🔍 尝试接口 B (Tushare Fallback)...")
            token = os.environ.get('TS_TOKEN')
            if token:
                pro = ts.pro_api(token)
                df = pro.stock_basic(exchange='', list_status='L', fields='symbol')
                codes = df['symbol'].tolist()
            else:
                print("❌ 未发现 Tushare Token")
        except Exception as e:
            print(f"⚠️ 接口 B 失败: {e}")

    # 统一过滤逻辑：只留 60 (沪主板) 和 00 (深主板)
    main_board = []
    for c in codes:
        c = str(c).zfill(6)
        if c.startswith('60') or c.startswith('00'):
            suffix = ".SH" if c.startswith('6') else ".SZ"
            main_board.append(f"{c}{suffix}")
            
    return sorted(list(set(main_board)))

# ==========================================
# 3. 强化版执行入口
# ==========================================
if __name__ == '__main__':
    try:
        # 初始化配置
        settings.init()
        
        # --- 核心修复：强制关闭时间检查 ---
        # 防止程序因为现在是凌晨而直接 return
        settings.config['cron'] = False 
        
        print("🚀 正在初始化全主板扫描任务...")
        final_codes = get_robust_main_board_list()
        
        if final_codes:
            print(f"✅ 名单确认！共 {len(final_codes)} 只主板股票。样本: {final_codes[:3]}")
            # 强制同步名单到全局配置
            settings.config['codes'] = final_codes
            
            print(f"🔬 正在唤醒扫描引擎 (即将处理 {len(final_codes)} 个目标)...")
            # 启动工作流
            work_flow.prepare()
            
            print("🏁 扫描任务全部执行完毕！")
        else:
            print("❌ 致命错误：未能获取到股票名单。")
            
    except Exception as e:
        print("🚨 程序运行过程中崩溃！")
        traceback.print_exc() # 打印详细的错误位置
