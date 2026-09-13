#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 群消息监听器 v4（读SQLite数据库，无getUpdates冲突）
# ============================================================

import json, os, sys, time, sqlite3
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
DB_FILE = os.path.join(SCRIPTS_DIR, "user_points.db")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
TARGET_CHAT_ID = "-1003795519678"  # 目标群ID
MAX_MESSAGES = 200
CHECK_INTERVAL = 3  # 每3秒检查一次数据库

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
    """从数据库读取新消息"""
    global last_id
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, message_id, chat_id, from_user, user_id, text, message_type, created_at FROM chat_messages WHERE id > ? AND chat_id = ? ORDER BY id ASC LIMIT 50",
            (last_id, TARGET_CHAT_ID)
        ).fetchall()
        conn.close()
        
        new_msgs = []
        for row in rows:
            last_id = row["id"]
            content = row["text"] or ""
            if row["message_type"] != "text":
                content = f"[{row['message_type']}] {content}"
            if not content:
                continue
            
            # 解析时间
            try:
                t = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
                time_str = t.strftime("%m-%d %H:%M:%S")
            except:
                time_str = row["created_at"]
            
            new_msgs.append({
                "db_id": row["id"],
                "message_id": row["message_id"],
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
    print("📡 群消息监听器启动（读数据库模式，无冲突）...")
    print(f"📂 数据库: {DB_FILE}")
    print(f"🎯 目标群: {TARGET_CHAT_ID}")
    
    load_last_id()
    
    # 先加载已有消息
    messages = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except:
            pass
    
    print(f"📋 已加载历史消息: {len(messages)} 条，最后ID: {last_id}")
    print("🔄 开始监听群消息（每3秒检查数据库）...")
    
    while True:
        try:
            new_msgs = get_new_messages()
            if new_msgs:
                messages.extend(new_msgs)
                messages = messages[-MAX_MESSAGES:]
                save_chat_log(messages)
                for m in new_msgs:
                    print(f"  [{m['time']}] {m['sender']}: {m['content'][:50]}")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 监听器已停止")
            break
        except Exception as e:
            print(f"⚠️  错误: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
