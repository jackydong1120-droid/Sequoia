import settings
import work_flow
import akshare as ak
import tushare as ts
import pandas as pd
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. 超级防抖补丁：解决 Read timed out
# ==========================================
def apply_retry_strategy():
    retry_strategy = Retry(
        total=10, # 重试 10 次
        backoff_factor=2, # 间隔 2s, 4s, 8s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    
    # 强制修改全局超时时间为 90 秒
    _original_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 90 
        return _original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request

apply_retry_strategy()

# ==========================================
# 2. 稳健获取主板名单逻辑
# ==========================================
def get_robust_main_board_list():
    codes = []
    
    # 通道 A: Akshare 实时接口
    try:
        print("🔍 尝试接口 A (Akshare Spot)...")
        df = ak.stock_zh_a_spot_em()
        codes = df['code'].tolist()
    except Exception as e:
        print(f"⚠️ 接口 A 失败 (超时或网络原因): {e}")

    # 通道 B: Tushare 备用接口 (需配置 Token)
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

    # 统一过滤逻辑：只留 60 (沪) 和 00 (深)
    main_board = []
    for c in codes:
        c = str(c).zfill(6)
        if c.startswith('60') or c.startswith('00'):
            suffix = ".SH" if c.startswith('6') else ".SZ"
            main_board.append(f"{c}{suffix}")
            
    return sorted(list(set(main_board)))

# ==========================================
# 3. 程序入口
# ==========================================
if __name__ == '__main__':
    settings.init()
    
    print("🚀 正在执行全主板扫描初始化...")
    final_codes = get_robust_main_board_list()
    
    if len(final_codes) > 1000:
        print(f"✅ 名单确认！获取到 {len(final_codes)} 只主板股票。即将开始扫描...")
        settings.config['codes'] = final_codes # 强制覆盖空配置
    else:
        print("⚠️ 警告：动态拉取失败，将执行紧急保底逻辑。")
        if not settings.config.get('codes'):
            settings.config['codes'] = ['002050.SZ', '600519.SH'] # 至少保证不空跑

    work_flow.prepare()
