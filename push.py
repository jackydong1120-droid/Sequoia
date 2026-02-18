import settings
import requests
from wxpusher import WxPusher

def push(msg):
    # 获取推送配置
    push_config = settings.config['push']
    
    # 优先检查是否有 PushPlus Token
    if 'pushplus_token' in push_config and push_config['pushplus_token']:
        print("正在尝试使用 PushPlus 推送...")
        url = 'http://www.pushplus.plus/send'
        data = {
            "token": push_config['pushplus_token'],
            "title": "Sequoia 选股日报",
            "content": msg,
            "template": "html"
        }
        try:
            response = requests.post(url, json=data)
            print(f"PushPlus 响应: {response.text}")
        except Exception as e:
            print(f"PushPlus 推送失败: {e}")
            
    # 如果没有 PushPlus，再尝试 WxPusher (兼容旧代码)
    elif 'wxpusher_token' in push_config and push_config['wxpusher_token']:
        print("正在尝试使用 WxPusher 推送...")
        try:
            WxPusher.send_message(
                msg, 
                uids=[push_config['wxpusher_uid']],
                token=push_config['wxpusher_token']
            )
        except Exception as e:
            print(f"WxPusher 推送失败: {e}")
    else:
        print("未检测到有效的推送 Token，跳过推送。")

def statistics(msg):
    push(msg)

def strategy(msg):
    push(msg)
