import pandas as pd
import settings
import strategy
import datetime

def process(stocks, strategies):
    # 这里假设 stocks 是列表，但 process 实际上可能需要加载数据
    # 根据你的报错，check 接收的是 {code: DataFrame}
    # 所以我们需要先加载数据
    stocks_data = {}
    for code in stocks:
        try:
            # 尝试加载数据
            df = pd.read_csv(settings.data_dir + "/" + code + ".csv", dtype={'code': str})
            # 强制转换日期列
            df['日期'] = pd.to_datetime(df['日期'])
            stocks_data[code] = df
        except Exception:
            continue

    for strategy_config in strategies:
        strategy_func = getattr(strategy, strategy_config['func'])
        check(stocks_data, strategy_config, strategy_func)

def check(stocks_data, strategy_config, strategy_func):
    # 1. 修复结束日期格式
    config_date = settings.config['end_date']
    if not config_date:
        end_date = datetime.date.today()
    else:
        try:
            end_date = datetime.datetime.strptime(config_date, "%Y-%m-%d").date()
        except:
            end_date = datetime.date.today()

    # 2. 修复比较逻辑
    def end_date_filter(item):
        df = item[1]
        if df is None or df.empty:
            return False
        # 获取该股票最早的日期
        try:
            stock_start_date = df['日期'].min().date()
            return end_date >= stock_start_date
        except:
            return False

    # 3. 执行过滤
    results = dict(filter(end_date_filter, stocks_data.items()))
    strategy_func(results)

def statistics(all_data, stocks):
    limitup = len(all_data[all_data['涨跌幅'] >= 9.5])
    limitdown = len(all_data[all_data['涨跌幅'] <= -9.5])
    up5 = len(all_data[all_data['涨跌幅'] >= 5])
    down5 = len(all_data[all_data['涨跌幅'] <= -5])
    
    msg = f"统计：\n涨停：{limitup} 家\n跌停：{limitdown} 家\n涨幅>5%：{up5} 家\n跌幅>5%：{down5} 家"
    
    import push
    push.statistics(msg)

def prepare():
    # 简单的透传
    pass
