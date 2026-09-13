#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 消息监听器 v5（群+私聊，读数据库）
# ============================================================

import json, os, sys, time, sqlite3
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
DB_FILE = os.path.join(SCRIPTS_DIR, "user_points.db")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
MAX_MESSAGES = 500
CHECK_INTERVAL = 2  # 每2秒检查一次数据库

os.makedirs(LOG_DIR, exist_ok=True)
last_id = 0

def load_last_id():
    global last_id
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                msgs = json.load(f)
                if msgs:
                    last_id = msgs[-1].get("db_id", 0)
        except:
            pass

def save_chat_log(messages):
    with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(messages[-MAX_MESSAGES:], f, ensure_ascii=False, indent=2)

def get_new_messages():
    global last_id
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        # 读取所有消息（群+私聊），不限制chat_id
        rows = conn.execute(
            "SELECT id, message_id, chat_id, chat_type, from_user, user_id, text, message_type, created_at FROM chat_messages WHERE id > ? ORDER BY id ASC LIMIT 100",
            (last_id,)
        ).fetchall()
        conn.close()
        
        new_msgs = []
        for row in rows:
            last_id = row["id"]
            content = row["text"] or ""
            msg_type = row["message_type"] or "text"
            chat_type = row["chat_type"] or ""
            
            # 标记消息来源
            if chat_type == "private":
                source = "📱私聊"
            elif chat_type == "group" or chat_type == "supergroup":
                source = "👥群聊"
            else:
                source = "📨"
            
            if msg_type != "text":
                content = f"[{msg_type}] {content}"
            if not content:
                continue
            
            try:
                t = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
                time_str = t.strftime("%m-%d %H:%M:%S")
            except:
                time_str = row["created_at"]
            
            new_msgs.append({
                "db_id": row["id"],
                "message_id": row["message_id"],
                "chat_id": row["chat_id"],
                "chat_type": chat_type,
                "source": source,
                "sender": row["from_user"] or "未知",
                "sender_id": row["user_id"],
                "content": content,
                "time": time_str,
                "timestamp": row["created_at"]
            })
        return new_msgs
    except Exception as e:
        print(f"⚠️  读数据库失败: {e}")
        return []

def main():
    print("📡 消息监听器启动 v5（群+私聊，读数据库）...")
    print(f"📂 数据库: {DB_FILE}")
    
    load_last_id()
    
    messages = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except:
            pass
    
    print(f"📋 已加载历史消息: {len(messages)} 条，最后ID: {last_id}")
    print("🔄 开始监听（每2秒检查数据库，群+私聊）...")
    
    while True:
        try:
            new_msgs = get_new_messages()
            if new_msgs:
                messages.extend(new_msgs)
                messages = messages[-MAX_MESSAGES:]
                save_chat_log(messages)
                for m in new_msgs:
                    print(f"  [{m['time']}] {m['source']} {m['sender']}: {m['content'][:50]}")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 监听器已停止")
            break
        except Exception as e:
            print(f"⚠️  错误: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
