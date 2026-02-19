import settings
import work_flow
import akshare as ak
import tushare as ts
import pandas as pd
import requests
import os
import traceback
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. 网络超级防抖 (90秒超时 + 10次重试)
# ==========================================
def apply_retry_strategy():
    retry_strategy = Retry(
        total=10, 
        backoff_factor=1, 
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
            kwargs['timeout'] = 90
        return _original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request

apply_retry_strategy()

# ==========================================
# 2. 智能名单获取 (强制补全后缀)
# ==========================================
def get_robust_stock_list():
    codes = []
    backup_file = 'stock_codes.txt'
    
    print("🔍 正在初始化 A 股名单...")
    
    # --- 通道 A: Tushare (优先，自带后缀) ---
    try:
        print("   >>> 尝试通道 A (Tushare)...")
        token = os.environ.get('TS_TOKEN')
        if token:
            ts.set_token(token)
            pro = ts.pro_api()
            # 关键：使用 ts_code 字段，它返回带后缀的代码 (如 000001.SZ)
            df = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
            raw_codes = df['ts_code'].tolist()
            # 过滤主板 (60开头或00开头)
            codes = [c for c in raw_codes if c.startswith('60') or c.startswith('00')]
            
            if len(codes) > 1000:
                print(f"   ✅ Tushare 获取成功: {len(codes)} 只")
    except Exception as e:
        print(f"   ⚠️ Tushare 失败: {e}")

    # --- 通道 B: Akshare (备用，需手动补后缀) ---
    if not codes:
        try:
            print("   >>> 尝试通道 B (Akshare)...")
            df = ak.stock_info_a_code_name()
            raw_codes = df['code'].tolist()
            for c in raw_codes:
                c = str(c).zfill(6)
                # 强制补全后缀，修复“跑了个寂寞”的问题
                if c.startswith('60'):
                    codes.append(f"{c}.SH")
                elif c.startswith('00'):
                    codes.append(f"{c}.SZ")
            
            if len(codes) > 1000:
                print(f"   ✅ Akshare 获取成功: {len(codes)} 只")
        except Exception as e:
            print(f"   ⚠️ Akshare 失败: {e}")

    # --- C. 自动缓存与读取 ---
    # 如果联网成功，写入缓存
    if len(codes) > 1000:
        try:
            with open(backup_file, 'w') as f:
                f.write('\n'.join(codes))
            print(f"💾 名单已备份至 {backup_file}")
        except:
            pass
    
    # 如果联网失败，读取缓存
    elif os.path.exists(backup_file):
        print("🚨 联网失败，正在读取本地备份...")
        with open(backup_file, 'r') as f:
            codes = [line.strip() for line in f.readlines() if line.strip()]
        print(f"📂 本地加载成功: {len(codes)} 只")

    return sorted(list(set(codes)))

# ==========================================
# 3. 主程序入口
# ==========================================
if __name__ == '__main__':
    try:
        settings.init()
        settings.config['cron'] = False 
        
        final_codes = get_robust_stock_list()
        
        if final_codes:
            print(f"✅ 最终确认扫描名单: {len(final_codes)} 只")
            print(f"📊 格式样本 (必须带.SZ/.SH): {final_codes[:3]}") 
            
            # 注入全局配置
            settings.config['codes'] = final_codes
            
            print("\n🔬 启动扫描引擎 (work_flow)...")
            work_flow.prepare()
        else:
            print("❌ 致命错误：无法获取任何股票代码。")
            
    except Exception as e:
        print("🚨 程序崩溃：")
        traceback.print_exc()
