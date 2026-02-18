import settings
import work_flow
import akshare as ak
import pandas as pd
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. 超级防抖补丁 (Anti-Shake Patch)
# ==========================================
# 能够自动处理 ConnectionReset, ReadTimeout 等网络错误
def apply_retry_strategy():
    retry_strategy = Retry(
        total=5,  # 失败后重试 5 次
        backoff_factor=1,  # 每次重试间隔 1s, 2s, 4s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    
    # 强制修改 requests 的默认超时时间为 60 秒
    _original_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 60
        return _original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request

apply_retry_strategy()

# ==========================================
# 2. 主程序逻辑
# ==========================================
if __name__ == '__main__':
    settings.init()
    
    print("🚀 正在拉取全市场股票名单...")
    try:
        # 获取所有A股实时数据
        df = ak.stock_zh_a_spot_em()
        all_codes = df['code'].tolist()
        
        main_board_codes = []
        for code in all_codes:
            code = str(code)
            # --- 过滤逻辑 ---
            if code.startswith('688'): continue  # 剔除科创板
            if code.startswith('30'):  continue  # 剔除创业板
            if code.startswith('8') or code.startswith('4'): continue # 剔除北交所
            
            # --- 格式补全 (适配 Tushare/Akshare 格式) ---
            # 如果是 6 开头 -> .SH, 否则 -> .SZ
            if code.startswith('6'):
                main_board_codes.append(f"{code}.SH")
            else:
                main_board_codes.append(f"{code}.SZ")
        
        count = len(main_board_codes)
        print(f"✅ 筛选完成！即将扫描 {count} 只主板股票 (已剔除科创/创业/北交所)")
        
        # 强制覆盖配置里的股票列表
        if count > 0:
            settings.config['codes'] = main_board_codes
        else:
            print("⚠️ 警告：未获取到股票代码，将使用默认配置")
            
    except Exception as e:
        print(f"❌ 获取全市场列表失败，将使用 config.yaml 中的默认列表。错误: {e}")
        # 如果 akshare 失败，这里不中断，继续用 config 里的（哪怕只有一只）

    # 开始执行工作流
    work_flow.prepare()
