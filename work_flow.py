import pandas as pd
import akshare as ak
import tushare as ts
import settings
import datetime
import requests
import os
import traceback

# ==========================================
# 1. 核心：三级数据瀑布 (Data Waterfall)
# ==========================================

def fetch_from_sina(code):
    """
    【通道 C】新浪财经 (急速快照)
    仅在 Akshare 和 Tushare 都挂了时使用，只返回当日最新数据
    """
    try:
        # 格式转换: 000001.SZ -> sz000001
        if code.endswith('.SZ'): sina_code = 'sz' + code[:6]
        elif code.endswith('.SH'): sina_code = 'sh' + code[:6]
        else: return None

        url = f"http://hq.sinajs.cn/list={sina_code}"
        resp = requests.get(url, timeout=5)
        text = resp.text
        
        if "," in text:
            elements = text.split(',')
            if len(elements) > 30:
                data = {
                    'date': [pd.to_datetime(datetime.date.today())],
                    'open': [float(elements[1])],
                    'high': [float(elements[4])],
                    'low': [float(elements[5])],
                    'close': [float(elements[3])],
                    'volume': [float(elements[8])]
                }
                return pd.DataFrame(data)
    except:
        pass
    return pd.DataFrame()

def fetch_data_robust(code):
    """
    数据获取总控：Akshare -> Tushare -> Sina
    """
    # -----------------------------------
    # 优先通道: Akshare (东方财富源 - 数据最全)
    # -----------------------------------
    try:
        pure_code = code[:6] # 去掉 .SZ 后缀给 Akshare 用
        # 获取日线 (前复权)
        df = ak.stock_zh_a_hist(symbol=pure_code, period="daily", adjust="qfq")
        
        if not df.empty:
            # 标准化列名
            df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            return df
    except:
        pass # 失败则静默进入下一级

    # -----------------------------------
    # 备用通道: Tushare (官方源 - 极稳)
    # -----------------------------------
    try:
        token = os.environ.get('TS_TOKEN')
        if token:
            ts.set_token(token)
            pro = ts.pro_api()
            # 获取最近 200 天 (满足均线计算)
            end_dt = datetime.datetime.now().strftime('%Y%m%d')
            start_dt = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y%m%d')
            
            df = pro.daily(ts_code=code, start_date=start_dt, end_date=end_dt)
            if not df.empty:
                df = df.iloc[::-1].reset_index(drop=True) # 倒序
                df.rename(columns={'trade_date': 'date', 'vol': 'volume'}, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                return df
    except:
        pass

    # -----------------------------------
    # 急救通道: 新浪 (仅当日数据)
    # -----------------------------------
    # 如果策略只需要今日收盘价，这个可以救命；如果需要 MA20，这个会报错(行数不够)
    # 但总比空着好
    try:
        df = fetch_from_sina(code)
        if not df.empty:
            return df
    except:
        pass

    return pd.DataFrame()

# ==========================================
# 2. 执行流程
# ==========================================
def process():
    codes = settings.config['codes']
    print(f"DEBUG: work_flow 开始处理 {len(codes)} 只股票")
    
    # 检查策略文件是否存在
    try:
        import statistics
    except ImportError:
        print("🚨 致命错误：找不到 statistics.py！")
        return []

    results = []
    
    for i, code in enumerate(codes):
        # 进度显示 (每 100 只显示一次)
        if i % 100 == 0:
            print(f"   ... 进度 {i}/{len(codes)} (当前: {code})")
            
        # 1. 获取数据 (瀑布流)
        df = fetch_data_robust(code)
        
        if df.empty:
            continue
            
        # 2. 运行策略
        try:
            # 确保传递给策略的是标准 DataFrame
            if statistics.run(df):
                print(f"   🚀 🎯 触发信号: {code}")
                results.append(code)
        except Exception:
            continue
            
    return results

def prepare():
    selected = process()
    
    if selected:
        print(f"✅ 选股完成！共选中 {len(selected)} 只。")
        with open('data/stock.db', 'w') as f:
            f.write('\n'.join(selected))
    else:
        print("⚠️ 扫描完成，今日无符合条件的股票。")
        # 创建空文件防止报错
        with open('data/stock.db', 'w') as f:
            f.write("No stocks selected.")
