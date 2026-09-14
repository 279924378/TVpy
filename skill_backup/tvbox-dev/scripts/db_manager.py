#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tvbox-dev 技能 SQLite 数据库管理脚本
存储：待掘队列、推送历史、Bot配置、任务队列、代理状态、Spider注册表等
优势：事务安全、查询高效、并发安全、数据完整、备份简单
用法:
  python3 db_manager.py init              # 初始化数据库
  python3 db_manager.py migrate           # 从JSON迁移数据到数据库
  python3 db_manager.py stats             # 查看数据库统计
  python3 db_manager.py backup            # 备份数据库
"""
import os
import sys
import json
import sqlite3
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DB_PATH = os.path.join(DATA_DIR, "tvbox_dev.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# JSON数据文件路径（迁移源）
JSON_FILES = {
    "pending_urls": os.path.join(SCRIPT_DIR, "tg_pending_urls.json"),
    "push_history": os.path.join(SCRIPT_DIR, "tg_push_history.json"),
    "bot_config": os.path.join(SCRIPT_DIR, "tg_config.json"),
    "task_queue": os.path.join(SCRIPT_DIR, "central_task_queue.json"),
    "proxy_state": os.path.join(SCRIPT_DIR, "xray_permanent_state.json"),
}


def get_conn():
    """获取数据库连接"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    conn = get_conn()
    c = conn.cursor()
    
    # 1. 待掘队列表
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            from_user TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            site_name TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_urls(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pending_created ON pending_urls(created_at)")
    
    # 2. 推送历史表
    c.execute("""
        CREATE TABLE IF NOT EXISTS push_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_name TEXT NOT NULL,
            file_name TEXT DEFAULT '',
            message_id INTEGER DEFAULT 0,
            version TEXT DEFAULT 'v1.0',
            caption TEXT DEFAULT '',
            categories TEXT DEFAULT '',
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_push_site ON push_history(site_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_push_created ON push_history(created_at)")
    
    # 3. Bot配置表
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 4. 中央任务队列表
    c.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            session_id TEXT DEFAULT '',
            result TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status)")
    
    # 5. 代理状态表
    c.execute("""
        CREATE TABLE IF NOT EXISTS proxy_state (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 6. 技能配置表
    c.execute("""
        CREATE TABLE IF NOT EXISTS skill_config (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 7. Spider注册表
    c.execute("""
        CREATE TABLE IF NOT EXISTS spider_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_name TEXT NOT NULL UNIQUE,
            site_url TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            categories TEXT DEFAULT '',
            cms_type TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            version TEXT DEFAULT 'v1.0',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_spider_status ON spider_registry(status)")
    
    # 8. 操作日志表
    c.execute("""
        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            operator TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_log_action ON operation_logs(action)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_log_created ON operation_logs(created_at)")
    
    conn.commit()
    conn.close()
    
    log_operation("init_db", "数据库初始化完成")
    return True


def log_operation(action, detail="", operator="system"):
    """记录操作日志"""
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)",
            (action, detail, operator)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ==================== 待掘队列操作 ====================

def add_pending_url(url, from_user="", site_name=""):
    """添加待掘网址（去重）"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO pending_urls (url, from_user, site_name) VALUES (?, ?, ?)",
            (url, from_user, site_name)
        )
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def get_pending_urls(status="pending"):
    """获取待掘队列"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_urls WHERE status = ? ORDER BY created_at ASC",
        (status,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_pending_status(url, status, note=""):
    """更新待掘网址状态"""
    conn = get_conn()
    conn.execute(
        "UPDATE pending_urls SET status = ?, note = ?, updated_at = datetime('now','localtime') WHERE url = ?",
        (status, note, url)
    )
    conn.commit()
    conn.close()


# ==================== 推送历史操作 ====================

def add_push_record(site_name, file_name="", message_id=0, version="v1.0", caption="", categories=""):
    """添加推送记录"""
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO push_history (site_name, file_name, message_id, version, caption, categories)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (site_name, file_name, message_id, version, caption, categories)
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_push_history(site_name=None, limit=20):
    """获取推送历史"""
    conn = get_conn()
    if site_name:
        rows = conn.execute(
            "SELECT * FROM push_history WHERE site_name = ? ORDER BY created_at DESC LIMIT ?",
            (site_name, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM push_history ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_push(site_name):
    """获取某站点最新推送记录"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM push_history WHERE site_name = ? ORDER BY created_at DESC LIMIT 1",
        (site_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ==================== Spider注册表操作 ====================

def register_spider(site_name, site_url="", file_path="", categories="", cms_type="", version="v1.0"):
    """注册Spider"""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO spider_registry 
               (site_name, site_url, file_path, categories, cms_type, status, version)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (site_name, site_url, file_path, categories, cms_type, version)
        )
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def get_all_spiders(status="active"):
    """获取所有已注册Spider"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM spider_registry WHERE status = ? ORDER BY created_at DESC",
        (status,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 配置表操作 ====================

def set_config(table, key, value):
    """设置配置（bot_config/skill_config/proxy_state）"""
    conn = get_conn()
    value_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
        (key, value_str)
    )
    conn.commit()
    conn.close()


def get_config(table, key, default=None):
    """获取配置"""
    conn = get_conn()
    row = conn.execute(f"SELECT value FROM {table} WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    value = row["value"]
    try:
        return json.loads(value)
    except Exception:
        return value


# ==================== 数据迁移 ====================

def migrate_from_json():
    """从JSON文件迁移数据到数据库"""
    print("=" * 60)
    print("开始从JSON迁移数据到SQLite数据库")
    print("=" * 60)
    
    stats = {"pending_urls": 0, "push_history": 0, "bot_config": 0, "task_queue": 0, "proxy_state": 0}
    
    # 1. 迁移待掘队列
    if os.path.isfile(JSON_FILES["pending_urls"]):
        try:
            with open(JSON_FILES["pending_urls"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    url = item.get("url", "")
                    if url:
                        add_pending_url(
                            url,
                            from_user=item.get("from_user", ""),
                            site_name=item.get("site_name", "")
                        )
                        if item.get("status") and item["status"] != "pending":
                            update_pending_status(url, item["status"])
                        stats["pending_urls"] += 1
                print(f"✅ 待掘队列: 迁移 {stats['pending_urls']} 条")
        except Exception as e:
            print(f"❌ 待掘队列迁移失败: {e}")
    
    # 2. 迁移推送历史
    if os.path.isfile(JSON_FILES["push_history"]):
        try:
            with open(JSON_FILES["push_history"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for site_name, record in data.items():
                    if isinstance(record, dict):
                        add_push_record(
                            site_name,
                            file_name=record.get("file_name", ""),
                            message_id=record.get("message_id", 0),
                            version=record.get("version", "v1.0"),
                            caption=record.get("caption", ""),
                            categories=record.get("categories", "")
                        )
                        stats["push_history"] += 1
                print(f"✅ 推送历史: 迁移 {stats['push_history']} 条")
        except Exception as e:
            print(f"❌ 推送历史迁移失败: {e}")
    
    # 3. 迁移Bot配置
    if os.path.isfile(JSON_FILES["bot_config"]):
        try:
            with open(JSON_FILES["bot_config"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key, value in data.items():
                    set_config("bot_config", key, value)
                    stats["bot_config"] += 1
                print(f"✅ Bot配置: 迁移 {stats['bot_config']} 项")
        except Exception as e:
            print(f"❌ Bot配置迁移失败: {e}")
    
    # 4. 迁移任务队列
    if os.path.isfile(JSON_FILES["task_queue"]):
        try:
            with open(JSON_FILES["task_queue"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                conn = get_conn()
                for item in data:
                    conn.execute(
                        "INSERT OR IGNORE INTO task_queue (url, status, priority, session_id, result) VALUES (?, ?, ?, ?, ?)",
                        (item.get("url", ""), item.get("status", "pending"),
                         item.get("priority", 0), item.get("session_id", ""),
                         json.dumps(item.get("result", ""), ensure_ascii=False))
                    )
                    stats["task_queue"] += 1
                conn.commit()
                conn.close()
                print(f"✅ 任务队列: 迁移 {stats['task_queue']} 条")
        except Exception as e:
            print(f"❌ 任务队列迁移失败: {e}")
    
    # 5. 迁移代理状态
    if os.path.isfile(JSON_FILES["proxy_state"]):
        try:
            with open(JSON_FILES["proxy_state"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key, value in data.items():
                    set_config("proxy_state", key, value)
                    stats["proxy_state"] += 1
                print(f"✅ 代理状态: 迁移 {stats['proxy_state']} 项")
        except Exception as e:
            print(f"❌ 代理状态迁移失败: {e}")
    
    log_operation("migrate_json", json.dumps(stats, ensure_ascii=False))
    print(f"\n✅ 迁移完成！总计: {sum(stats.values())} 条数据")
    return stats


# ==================== 统计与备份 ====================

def get_stats():
    """获取数据库统计"""
    conn = get_conn()
    stats = {}
    tables = ["pending_urls", "push_history", "bot_config", "task_queue", 
              "proxy_state", "skill_config", "spider_registry", "operation_logs"]
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()["cnt"]
            stats[table] = count
        except Exception:
            stats[table] = 0
    conn.close()
    
    db_size = os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else 0
    stats["_db_size"] = db_size
    stats["_db_path"] = DB_PATH
    return stats


def backup_db():
    """备份数据库"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"tvbox_dev_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    
    # 只保留最近10个备份
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")])
    if len(backups) > 10:
        for old in backups[:-10]:
            os.remove(os.path.join(BACKUP_DIR, old))
    
    log_operation("backup_db", backup_path)
    return backup_path


# ==================== 主入口 ====================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        init_db()
        print("✅ 数据库初始化完成")
        print(f"   路径: {DB_PATH}")
    
    elif cmd == "migrate":
        init_db()
        migrate_from_json()
    
    elif cmd == "stats":
        stats = get_stats()
        print("=" * 50)
        print("📊 数据库统计")
        print("=" * 50)
        print(f"  数据库路径: {stats['_db_path']}")
        print(f"  数据库大小: {stats['_db_size']} bytes")
        print("-" * 50)
        for key, value in stats.items():
            if not key.startswith("_"):
                print(f"  {key:20s}: {value} 条")
    
    elif cmd == "backup":
        path = backup_db()
        print(f"✅ 数据库备份完成: {path}")
    
    else:
        print(f"❌ 未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
