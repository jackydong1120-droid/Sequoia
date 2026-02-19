import pandas as pd
import akshare as ak
import tushare as ts
import settings
import datetime
import requests
import os
import traceback

# ==========================================
# 核心组件：多源数据瀑布 (Data Waterfall)
# ==========================================

def fetch_from_sina(code):
    """
    【通道 A】新浪财经极速接口
    优点：速度极快，无门槛，直接返回当日最新行情
    缺点：只返回当日数据，无历史 K 线
    """
    try:
        # 转换代码格式：000001.SZ -> sz000001
        if code.endswith('.SZ'):
            sina_code = 'sz' + code[:6]
        elif code.endswith('.SH'):
            sina_code = 'sh' + code[:6]
        else:
            return None

        url = f"http://hq.sinajs.cn/list={sina_code}"
        resp = requests.get(url, timeout=3)
        
        # 解析返回字符串: var hq_str_sz000001="平安银行,27.50,27.55,27.30,..."
        text = resp.text
        if "," in text:
            elements = text.split(',')
            if len(elements) > 30:
                # 构造 DataFrame (模拟日线格式)
                data = {
                    'date': [elements[30]], # 日期
                    'open': [float(elements[1])],
                    'high': [float(elements[4])],
                    'low': [float(elements[5])],
                    'close': [float(elements[3])],
                    'volume': [float(elements[8])]
                }
                df = pd.DataFrame(data)
                # 简单的日期清洗
                df['date'] = pd.to_datetime(df['date'])
                return df
    except Exception:
        pass
    return None

def fetch_from_akshare(code):
    """
    【通道 B】Akshare (东方财富)
    优点：数据字段最全，支持历史回测
    """
    try:
        pure_code = code[:6]
        # 抓取日线
        df = ak.stock_zh_a_hist(symbol=pure_code, period="daily", adjust="qfq")
        if not df.empty:
            df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            return df
    except Exception:
        pass
    return None

def fetch_from_tushare(code):
    """
    【通道 C】Tushare (官方备用)
    优点：极度稳定，适合做最后的防线
    """
    try:
        token = os.environ.get('TS_TOKEN')
        if token:
            ts.set_token(token)
            pro = ts.pro_api()
            # 抓取最近 100 天数据
            end_date = datetime.datetime.now().strftime('%Y%m%d')
            start_date = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime('%Y%m%d')
            
            df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
            if not df.empty:
                df = df.iloc[::-1].reset_index(drop=True) # 倒序
                df.rename(columns={'trade_date': 'date', 'vol': 'volume'}, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                return df
    except Exception:
        pass
    return None

# ==========================================
# 统一调度器
# ==========================================

def fetch_data_robust(code):
    # 策略：如果我们需要【历史K线】来计算均线(MA20, MA60)，新浪的单日数据是不够的。
    # 所以优先用 Akshare/Tushare，新浪可以作为“当日收盘价校准”或“停牌检测”。
    
    # 1. 优先尝试 Akshare (最全)
    df = fetch_from_akshare(code)
    
    # 2. 失败则尝试 Tushare (最稳)
    if df is None or df.empty:
        # print(f"   ⚠️ Akshare 失败，切换 Tushare: {code}")
        df = fetch_from_tushare(code)
        
    # 3. 如果前两者都挂了，或者数据太旧，尝试新浪 (急救)
    # (注：如果你的策略必须依赖20日均线，单靠新浪是不够的，但至少能拿到今天的价格)
    if df is None or df.empty:
        # print(f"   ⚠️ 历史源全挂，尝试新浪极速接口: {code}")
        df = fetch_from_sina(code)
        
    return df

# ==========================================
# 流程控制
# ==========================================

def process():
    codes = settings.config['codes']
    print(f"DEBUG: work_flow 准备扫描 {len(codes)} 只股票")
    
    try:
        import statistics
    except ImportError:
        print("🚨 错误：找不到 statistics.py，无法计算指标！")
        return []

    results = []
    print(f"   📊 扫描引擎启动...")
    
    for i, code in enumerate(codes):
        if i % 100 == 0:
            print(f"   ... 进度 {i}/{len(codes)}")
            
        df = fetch_data_robust(code)
        
        # 数据审计：如果是空的，跳过
        if df is None or df.empty:
            continue
            
        # 策略执行
        try:
            if statistics.run(df):
                print(f"   🚀 🎯 锁定目标: {code}")
                results.append(code)
        except Exception:
            continue
            
    return results

def prepare():
    selected = process()
    if selected:
        print(f"✅ 选股完成，共 {len(selected)} 只")
        with open('data/stock.db', 'w') as f:
            f.write('\n'.join(selected))
    else:
        print("⚠️ 扫描结束，今日无标的入选。")
        with open('data/stock.db', 'w') as f:
            f.write("No stocks selected.")
