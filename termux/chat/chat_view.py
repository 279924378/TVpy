#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 群消息实时查看器
# 简单版：实时滚动显示群消息，像 tail -f 一样
# 格式: [消息] 用户名(user_id): 消息内容
# ============================================================

import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
CONFIG_FILE = os.path.join(SCRIPTS_DIR, "tg_config.json")

# 颜色
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
GRAY = "\033[90m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def tg_api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def format_sender(user):
    """格式化发送者显示: 昵称(user_id)"""
    if not user:
        return "未知"
    name = user.get("first_name", "") or ""
    if user.get("last_name"):
        name += " " + user["last_name"]
    if not name:
        name = user.get("username", "未知")
    uid = user.get("id", "?")
    return f"{name}({uid})"

def format_content(msg):
    """格式化消息内容"""
    if "text" in msg:
        return msg["text"]
    elif "document" in msg:
        doc = msg["document"]
        return f"[文件] {doc.get('file_name', '未知')} ({doc.get('file_size', 0)}字节)"
    elif "photo" in msg:
        return "[图片]"
    elif "sticker" in msg:
        st = msg["sticker"]
        return f"[贴纸] {st.get('emoji', '')}"
    elif "video" in msg:
        return "[视频]"
    elif "voice" in msg:
        return "[语音]"
    elif "audio" in msg:
        return "[音频]"
    elif "location" in msg:
        return "[位置]"
    elif "contact" in msg:
        c = msg["contact"]
        return f"[联系人] {c.get('first_name', '')} {c.get('phone_number', '')}"
    elif "new_chat_members" in msg:
        members = ", ".join([m.get("first_name", m.get("username", "?")) for m in msg["new_chat_members"]])
        return f"[加入群] {members}"
    elif "left_chat_member" in msg:
        m = msg["left_chat_member"]
        return f"[离开群] {m.get('first_name', m.get('username', '?'))}"
    else:
        return "[其他消息]"

def main():
    print(f"{BOLD}{CYAN}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   段德机器人 - 群消息实时查看器              ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════╝{RESET}")
    print()
    
    # 加载配置
    try:
        config = load_config()
        token = config["bot"]["token"]
        chat_id = str(config["bot"]["chat_id"])
    except Exception as e:
        print(f"{RED}❌ 读取配置失败: {e}{RESET}")
        print(f"{GRAY}请确认配置文件存在: {CONFIG_FILE}{RESET}")
        return
    
    # 获取机器人信息
    me = tg_api(token, "getMe")
    if me.get("ok"):
        bot_info = me["result"]
        print(f"{GREEN}✅ Bot: @{bot_info.get('username', '?')}{RESET}")
    else:
        print(f"{RED}❌ 获取机器人信息失败{RESET}")
        return
    
    print(f"{YELLOW}📢 目标群: {chat_id}{RESET}")
    print(f"{YELLOW}🔗 代理: 直连（无代理）{RESET}")
    print()
    print(f"{GRAY}{'='*50}{RESET}")
    print(f"{GRAY}开始监听群消息... (按 Ctrl+C 退出){RESET}")
    print(f"{GRAY}{'='*50}{RESET}")
    print()
    
    # 获取当前最新消息的offset
    offset = 0
    result = tg_api(token, "getUpdates", {"offset": -1, "timeout": 5})
    if result.get("ok") and result.get("result"):
        offset = result["result"][-1]["update_id"] + 1
    
    # 实时监听
    try:
        while True:
            result = tg_api(token, "getUpdates", {"offset": offset, "timeout": 30})
            
            if result.get("ok") and result.get("result"):
                for update in result["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                        
                        # 只显示目标群的消息
                        if msg_chat_id == chat_id:
                            sender = format_sender(msg.get("from"))
                            content = format_content(msg)
                            time_str = datetime.fromtimestamp(msg.get("date", time.time())).strftime("%H:%M:%S")
                            
                            print(f"{GRAY}[{time_str}]{RESET} {YELLOW}[消息]{RESET} {CYAN}{sender}{RESET}: {content}")
                            
                            # 同时写入日志文件供TUI面板读取
                            try:
                                log_file = os.path.join(PROJECT_DIR, "logs", "chat_log.json")
                                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                                msgs = []
                                if os.path.exists(log_file):
                                    with open(log_file, "r", encoding="utf-8") as f:
                                        msgs = json.load(f)
                                msgs.append({
                                    "update_id": update["update_id"],
                                    "sender": sender.split("(")[0],
                                    "sender_id": msg.get("from", {}).get("id"),
                                    "content": content,
                                    "time": time_str,
                                    "timestamp": msg.get("date", time.time())
                                })
                                # 最多保留500条
                                msgs = msgs[-500:]
                                with open(log_file, "w", encoding="utf-8") as f:
                                    json.dump(msgs, f, ensure_ascii=False, indent=2)
                            except:
                                pass
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print()
        print(f"{GRAY}{'='*50}{RESET}")
        print(f"{GREEN}👋 已退出消息查看器{RESET}")
        print(f"{GRAY}后台机器人仍在运行{RESET}")

if __name__ == "__main__":
    main()
