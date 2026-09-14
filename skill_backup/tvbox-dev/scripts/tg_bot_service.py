#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 精简版（2026-09-14重大修订）
功能：只保留网址自动记录，群里发http/https网址自动记入待掘队列。
已下线：上线通知、所有口令、签到积分、小程序推送、历史撤回。

用法:
  python3 tg_bot_service.py              # 前台运行
  python3 tg_bot_service.py --debug      # 调试模式
  nohup python3 tg_bot_service.py &      # 后台运行
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "tg_config.json")
PENDING_FILE = os.path.join(SCRIPT_DIR, "tg_pending_urls.json")

# 网址正则
URL_PATTERN = re.compile(r'https?://[^\s]+', re.IGNORECASE)

# 守护监控配置（铁律27）
POLL_INTERVAL = 600       # 轮询间隔：10分钟（600秒）
NIGHT_START = 0            # 夜间静默开始：0点
NIGHT_END = 8              # 夜间静默结束：早8点


def is_night():
    """判断当前是否在夜间静默期（00:00-08:00）"""
    hour = datetime.now().hour
    return NIGHT_START <= hour < NIGHT_END

# 常驻代理端口（金字塔架构统一代理）
PROXY_PORT = 10809

# 调试模式
DEBUG = "--debug" in sys.argv


def log(msg):
    """日志输出"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")


def load_config():
    """加载配置"""
    if not os.path.isfile(CONFIG_FILE):
        log(f"❌ 配置文件不存在: {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_opener():
    """构建带代理的URL opener"""
    proxy_handler = urllib.request.ProxyHandler({
        "http": f"http://127.0.0.1:{PROXY_PORT}",
        "https": f"http://127.0.0.1:{PROXY_PORT}"
    })
    return urllib.request.build_opener(proxy_handler)


def api_request(token, method, params=None, timeout=30):
    """调用Telegram Bot API"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        import urllib.parse
        url += "?" + urllib.parse.urlencode(params)
    
    opener = build_opener()
    req = urllib.request.Request(url)
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def send_message(token, chat_id, text):
    """发送消息"""
    return api_request(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })


def load_pending():
    """加载待掘队列"""
    if not os.path.isfile(PENDING_FILE):
        return []
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_pending(data):
    """保存待掘队列"""
    try:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"❌ 队列保存失败: {e}")
        return False


def handle_url(text, from_user):
    """处理网址：自动记入待掘队列，静默不通知（2026-09-14取消入队通知）。夜间静默期不收集。"""
    # 铁律27：夜间静默期（00:00-08:00）不自动收集，作者豆包手动触发仍可处理队列
    if is_night():
        log(f"🌙 夜间静默期，跳过网址收集 (来自: {from_user})")
        return None
    
    urls = URL_PATTERN.findall(text)
    if not urls:
        return None
    
    pending = load_pending()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    
    for url in urls:
        # 去掉末尾的标点符号
        url = url.rstrip(".,;:!?，。；：！？")
        # 去重
        if not any(p.get("url") == url for p in pending):
            pending.append({
                "url": url,
                "from_user": from_user,
                "time": now,
                "status": "pending"
            })
            added += 1
            log(f"📝 网址入队(静默): {url} (来自: {from_user})")
    
    if added > 0:
        save_pending(pending)
    
    # 2026-09-14：取消入队通知，只静默记录队列，不发群消息
    return None


def main():
    """主循环"""
    log("=" * 50)
    log("🤖 Telegram Bot 精简版启动（只保留网址自动记录）")
    log("=" * 50)
    
    cfg = load_config()
    token = cfg.get("bot", {}).get("token", "")
    chat_id = cfg.get("bot", {}).get("chat_id", "")
    
    if not token:
        log("❌ 配置中缺少 bot.token")
        sys.exit(1)
    
    log(f"📡 目标群: {chat_id}")
    log(f"🔄 长轮询 getUpdates 启动...")
    log("（上线通知/口令/签到积分已下线，只保留网址自动记录）")
    log("")
    
    offset = 0
    fail_count = 0
    
    while True:
        try:
            result = api_request(token, "getUpdates", {
                "offset": offset,
                "timeout": 0,
                "allowed_updates": json.dumps(["message"])
            }, timeout=30)
            
            if not result.get("ok"):
                fail_count += 1
                log(f"❌ getUpdates失败 ({fail_count}/3): {result.get('description','')[:80]}")
                if fail_count >= 3:
                    log("⚠️  连续失败3次，等待10秒后重试...")
                    time.sleep(10)
                    fail_count = 0
                continue
            
            fail_count = 0
            updates = result.get("result", [])
            
            for update in updates:
                offset = max(offset, update["update_id"] + 1)
                
                message = update.get("message", {})
                if not message:
                    continue
                
                msg_chat_id = message.get("chat", {}).get("id", "")
                text = message.get("text", "") or message.get("caption", "")
                from_user = message.get("from", {}).get("username", "") or message.get("from", {}).get("first_name", "未知")
                
                if DEBUG:
                    log(f"📨 收到消息 (chat={msg_chat_id}, from={from_user}): {text[:80]}")
                
                # 只处理目标群的消息
                if str(msg_chat_id) != str(chat_id):
                    if DEBUG:
                        log(f"  ↳ 非目标群，跳过")
                    continue
                
                # 只处理包含网址的消息
                if not URL_PATTERN.search(text or ""):
                    continue
                
                # 处理网址
                reply = handle_url(text or "", from_user)
                if reply:
                    send_result = send_message(token, msg_chat_id, reply)
                    if send_result.get("ok"):
                        log(f"✅ 已回复网址入队提示")
                    else:
                        log(f"❌ 回复失败: {send_result.get('description','')[:80]}")
        
        except KeyboardInterrupt:
            log("\n⚠️  收到中断信号，Bot服务停止")
            break
        except Exception as e:
            fail_count += 1
            log(f"❌ 主循环异常 ({fail_count}): {e}")
            time.sleep(5)
        
        # 铁律27：10分钟轮询间隔（非实时监听，每POLL_INTERVAL秒收集一次）
        night_status = "🌙夜间静默" if is_night() else "☀️日间收集"
        log(f"💤 等待 {POLL_INTERVAL}s 后下一轮收集 ({night_status})...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
