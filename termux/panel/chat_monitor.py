#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 群消息监听器 v3（修复作用域bug）
# ============================================================

import json, os, sys, time, socket
import urllib.request, urllib.error, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
CONFIG_FILE = os.path.join(SCRIPTS_DIR, "tg_config.json")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
MAX_MESSAGES = 200

os.makedirs(LOG_DIR, exist_ok=True)

def detect_proxy():
    for port in [7890, 10809, 8080, 1080, 7891, 1087]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            if result == 0:
                return f"http://127.0.0.1:{port}"
        except:
            pass
    return None

PROXY_URL = detect_proxy()
if PROXY_URL:
    proxy_handler = urllib.request.ProxyHandler({"http": PROXY_URL, "https": PROXY_URL})
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)
    print(f"📡 使用代理: {PROXY_URL}")
else:
    print("📡 未检测到代理，使用直连")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def tg_api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def load_chat_log():
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_chat_log(messages):
    with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(messages[-MAX_MESSAGES:], f, ensure_ascii=False, indent=2)

def main():
    print("📡 群消息监听器启动中...")
    try:
        config = load_config()
        token = config["bot"]["token"]
        target_chat_id = str(config["bot"]["chat_id"])
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return
    
    me = tg_api(token, "getMe")
    if me.get("ok"):
        print(f"✅ 机器人: @{me['result']['username']}")
    else:
        print(f"❌ 获取机器人信息失败: {me.get('error', me)}")
        return
    
    messages = load_chat_log()
    print(f"📋 已加载历史消息: {len(messages)} 条")
    
    offset = 0
    if messages:
        offset = messages[-1].get("update_id", 0) + 1
    
    print("🔄 开始监听群消息...")
    
    while True:
        try:
            result = tg_api(token, "getUpdates", {"offset": offset, "timeout": 30})
            if result.get("ok") and result.get("result"):
                for update in result["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        
                        if chat_id == target_chat_id:
                            sender = msg.get("from", {})
                            sender_name = sender.get("first_name", "") or sender.get("username", "未知")
                            if sender.get("last_name"):
                                sender_name += " " + sender["last_name"]
                            
                            content = ""
                            if "text" in msg:
                                content = msg["text"]
                            elif "document" in msg:
                                content = f"[文件] {msg['document'].get('file_name', '未知')}"
                            elif "photo" in msg:
                                content = "[图片]"
                            elif "sticker" in msg:
                                content = f"[贴纸] {msg['sticker'].get('emoji', '')}"
                            
                            if content:
                                msg_entry = {
                                    "update_id": update["update_id"],
                                    "message_id": msg.get("message_id"),
                                    "sender": sender_name,
                                    "sender_id": sender.get("id"),
                                    "content": content,
                                    "time": datetime.fromtimestamp(msg.get("date", time.time())).strftime("%m-%d %H:%M:%S"),
                                    "timestamp": msg.get("date", time.time())
                                }
                                messages.append(msg_entry)
                                save_chat_log(messages)
                                print(f"  [{msg_entry['time']}] {sender_name}: {content[:50]}")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n👋 监听器已停止")
            break
        except Exception as e:
            print(f"⚠️  错误: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
