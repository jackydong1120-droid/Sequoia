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
# 1. 网络超级防抖 (解决 Read timed out)
# ==========================================
def apply_retry_strategy():
    retry_strategy = Retry(
        total=10, 
        backoff_factor=1, # 失败后等待 1s, 2s, 4s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    
    # 强制设置 90秒 超时
    _original_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 90
        return _original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request

apply_retry_strategy()

# ==========================================
# 2. 智能名单获取 (网络 + 本地缓存)
# ==========================================
def get_robust_stock_list():
    codes = []
    backup_file = 'stock_codes.txt'
    network_success = False

    # --- A. 尝试联网更新 (为了抓取新股) ---
    print("🔍 正在尝试联网获取最新 A 股名单...")
    
    # 通道 1: Akshare 极速接口 (只抓代码，速度快)
    if not codes:
        try:
            print("   >>> 尝试通道 A (Akshare)...")
            df = ak.stock_info_a_code_name()
            raw_codes = df['code'].tolist()
            # 格式化
            for c in raw_codes:
                c = str(c).zfill(6)
                if c.startswith('60') or c.startswith('00'):
                    suffix = ".SH" if c.startswith('6') else ".SZ"
                    codes.append(f"{c}{suffix}")
            if len(codes) > 1000:
                print(f"   ✅ Akshare 获取成功: {len(codes)} 只")
                network_success = True
        except Exception as e:
            print(f"   ⚠️ 通道 A 失败: {e}")

    # 通道 2: Tushare (备用，需 Token)
    if not codes:
        try:
            print("   >>> 尝试通道 B (Tushare)...")
            token = os.environ.get('TS_TOKEN')
            if token:
                pro = ts.pro_api(token)
                df = pro.stock_basic(exchange='', list_status='L', fields='symbol')
                raw_codes = df['symbol'].tolist()
                # Tushare 格式通常已经是 000001.SZ，只需简单过滤
                for c in raw_codes:
                    if c.startswith('60') or c.startswith('00'):
                        codes.append(c)
                if len(codes) > 1000:
                    print(f"   ✅ Tushare 获取成功: {len(codes)} 只")
                    network_success = True
        except Exception as e:
            print(f"   ⚠️ 通道 B 失败: {e}")

    codes = sorted(list(set(codes)))

    # --- B. 缓存逻辑 (自动存档) ---
    if network_success and len(codes) > 1000:
        try:
            with open(backup_file, 'w') as f:
                f.write('\n'.join(codes))
            print(f"💾 名单已自动备份至本地 {backup_file}")
        except:
            pass
    
    # --- C. 灾难恢复 (读本地文件) ---
    if not codes:
        print("🚨 联网获取全部失败！启动本地灾难恢复模式...")
        if os.path.exists(backup_file):
            with open(backup_file, 'r') as f:
                codes = [line.strip() for line in f.readlines() if line.strip()]
            print(f"📂 成功读取本地缓存: {len(codes)} 只")
        else:
            print("❌ 本地无备份文件！使用紧急保底名单 (茅指数)。")
            codes = ['600519.SH', '000858.SZ', '000001.SZ', '601318.SH'] # 最小保底

    return codes

# ==========================================
# 3. 主程序入口
# ==========================================
if __name__ == '__main__':
    try:
        settings.init()
        # 强制关闭时间检查，确保任何时候运行都能跑
        settings.config['cron'] = False 
        
        print("\n🚀 Sequoia 自动选股系统初始化...")
        final_codes = get_robust_stock_list()
        
        if final_codes:
            print(f"✅ 最终确认扫描名单: 共 {len(final_codes)} 只。")
            print(f"📊 样本示例: {final_codes[:3]} ... {final_codes[-3:]}")
            
            # 将名单注入全局配置
            settings.config['codes'] = final_codes
            
            print("\n🔬 正在启动扫描引擎 (work_flow)...")
            work_flow.prepare()
            
            print("\n🏁 ===============================")
            print("🏁 所有任务执行完毕！请检查 Artifacts 或 推送消息。")
            print("🏁 ===============================")
        else:
            print("❌ 致命错误：未能获取任何股票代码，程序终止。")
            
    except Exception as e:
        print("\n🚨 程序运行时发生崩溃！")
        traceback.print_exc()
