#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
段德机器人项目 - 统一数据库访问模块（DBHelper）
所有新建会话通过此模块访问数据，无需依赖JSON文件。
数据库文件: scripts/bot_data.db
"""

import sqlite3
import os
import json
import threading
from datetime import datetime
from contextlib import contextmanager

# 数据库路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "bot_data.db")

# 线程锁（防止多会话并发写冲突）
_db_lock = threading.Lock()


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动提交和关闭）"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 支持并发读写
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== 配置表 ====================

def get_config(key, default=None):
    """获取配置项"""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default


def set_config(key, value):
    """设置配置项"""
    with _db_lock:
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                         (key, str(value)))


def get_all_config():
    """获取所有配置"""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {row['key']: row['value'] for row in rows}


# ==================== 用户表 ====================

def get_user(user_id):
    """获取用户信息"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone()
        return dict(row) if row else None


def get_user_points(user_id):
    """获取用户积分"""
    user = get_user(user_id)
    return user['points'] if user else 0


def add_user_points(user_id, username, points, reason=""):
    """增加用户积分（同时记录变动）"""
    with _db_lock:
        with get_db() as conn:
            # 获取或创建用户
            user = conn.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone()
            if not user:
                conn.execute("INSERT INTO users (user_id, username, points) VALUES (?, ?, 0)",
                             (str(user_id), username))
                current_points = 0
            else:
                current_points = user['points']
            
            new_balance = current_points + points
            conn.execute("UPDATE users SET points=?, username=?, updated_at=? WHERE user_id=?",
                         (new_balance, username, datetime.now().isoformat(), str(user_id)))
            
            # 记录变动
            conn.execute('''INSERT INTO point_transactions (user_id, username, points_change, reason, balance_after)
                            VALUES (?, ?, ?, ?, ?)''',
                         (str(user_id), username, points, reason, new_balance))
            return new_balance


def consume_user_points(user_id, points, reason="消费"):
    """扣减用户积分"""
    return add_user_points(user_id, "", -points, reason)


def get_all_users():
    """获取所有用户（积分排行榜）"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY points DESC").fetchall()
        return [dict(row) for row in rows]


def get_point_history(user_id, limit=20):
    """获取用户积分变动记录"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM point_transactions WHERE user_id=? ORDER BY id DESC LIMIT ?",
                            (str(user_id), limit)).fetchall()
        return [dict(row) for row in rows]


# ==================== 待处理网址表 ====================

def get_pending_urls(status="pending"):
    """获取待处理网址"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM pending_urls WHERE status=? ORDER BY id",
                            (status,)).fetchall()
        return [dict(row) for row in rows]


def get_next_pending_url():
    """获取下一个待处理网址（FIFO）"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM pending_urls WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
        return dict(row) if row else None


def add_pending_url(url, from_user="", user_id="", source="manual"):
    """添加待处理网址（去重）"""
    with _db_lock:
        with get_db() as conn:
            existing = conn.execute("SELECT id, status FROM pending_urls WHERE url=?", (url,)).fetchone()
            if existing:
                if existing['status'] not in ('pending', 'processing'):
                    conn.execute("UPDATE pending_urls SET status='pending', submit_time=? WHERE id=?",
                                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), existing['id']))
                    return 'reset'
                return 'exists'
            conn.execute('''INSERT INTO pending_urls (url, status, from_user, user_id, submit_time, source)
                            VALUES (?, 'pending', ?, ?, ?, ?)''',
                         (url, from_user, str(user_id), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source))
            return 'added'


def update_url_status(url, status, **kwargs):
    """更新网址状态"""
    with _db_lock:
        with get_db() as conn:
            updates = [f"{k}=?" for k in kwargs]
            params = list(kwargs.values()) + [status, url]
            if updates:
                conn.execute(f"UPDATE pending_urls SET status=?, {', '.join(updates)} WHERE url=?", params)
            else:
                conn.execute("UPDATE pending_urls SET status=? WHERE url=?", (status, url))


def mark_url_done(url, result="", note=""):
    """标记网址为已完成"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    update_url_status(url, 'done', done_time=now, result=result, note=note)


def mark_url_failed(url, reason=""):
    """标记网址为失败"""
    update_url_status(url, 'failed', note=reason)


def get_url_stats():
    """获取网址统计"""
    with get_db() as conn:
        stats = {}
        for status in ['pending', 'processing', 'done', 'failed']:
            count = conn.execute("SELECT COUNT(*) FROM pending_urls WHERE status=?", (status,)).fetchone()[0]
            stats[status] = count
        stats['total'] = sum(stats.values())
        return stats


# ==================== py成品文件表 ====================

def save_py_file(file_name, content, site_name="", source_url="", version="1.0"):
    """保存py文件到数据库"""
    with _db_lock:
        with get_db() as conn:
            file_size = len(content) if isinstance(content, bytes) else len(content.encode('utf-8'))
            existing = conn.execute("SELECT id FROM py_files WHERE file_name=?", (file_name,)).fetchone()
            if existing:
                conn.execute('''UPDATE py_files SET content=?, file_size=?, site_name=?, source_url=?,
                                version=?, updated_at=? WHERE file_name=?''',
                             (content, file_size, site_name, source_url, version,
                              datetime.now().isoformat(), file_name))
                return 'updated'
            conn.execute('''INSERT INTO py_files (file_name, site_name, source_url, content, file_size, version)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (file_name, site_name, source_url, content, file_size, version))
            return 'created'


def get_py_file(file_name):
    """从数据库获取py文件内容"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM py_files WHERE file_name=?", (file_name,)).fetchone()
        return dict(row) if row else None


def get_py_file_content(file_name):
    """获取py文件内容（bytes）"""
    py_file = get_py_file(file_name)
    return py_file['content'] if py_file else None


def extract_py_to_file(file_name, output_path=None):
    """从数据库提取py文件到本地路径"""
    content = get_py_file_content(file_name)
    if not content:
        return None
    if output_path is None:
        output_path = os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "chats", "38441277210750978", file_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(content)
    return output_path


def list_py_files(status="active"):
    """列出所有py文件"""
    with get_db() as conn:
        rows = conn.execute("SELECT id, file_name, site_name, file_size, version, status, created_at, updated_at FROM py_files WHERE status=? ORDER BY id",
                            (status,)).fetchall()
        return [dict(row) for row in rows]


def delete_py_file(file_name):
    """删除py文件（软删除）"""
    with _db_lock:
        with get_db() as conn:
            conn.execute("UPDATE py_files SET status='deleted' WHERE file_name=?", (file_name,))


# ==================== 代理节点表 ====================

def get_proxy_nodes(is_active=None):
    """获取代理节点列表"""
    with get_db() as conn:
        if is_active is not None:
            rows = conn.execute("SELECT * FROM proxy_nodes WHERE is_active=?", (1 if is_active else 0,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM proxy_nodes").fetchall()
        return [dict(row) for row in rows]


def add_proxy_node(node_data):
    """添加代理节点"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT INTO proxy_nodes (name, type, server, port, uuid, cipher, tls, network, ws_path, ws_host, config_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (node_data.get('name',''), node_data.get('type',''), node_data.get('server',''),
                          node_data.get('port',0), node_data.get('uuid',''), node_data.get('cipher','auto'),
                          node_data.get('tls',''), node_data.get('network','ws'), node_data.get('ws-path',''),
                          node_data.get('ws-headers',{}).get('Host',''), json.dumps(node_data, ensure_ascii=False)))


def set_active_proxy(node_id):
    """设置当前激活的代理节点"""
    with _db_lock:
        with get_db() as conn:
            conn.execute("UPDATE proxy_nodes SET is_active=0")
            conn.execute("UPDATE proxy_nodes SET is_active=1 WHERE id=?", (node_id,))


# ==================== 私聊消息表 ====================

def save_private_message(user_id, username, message_id, text, message_type="text"):
    """保存私聊消息"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT INTO private_messages (user_id, username, message_id, text, message_type)
                            VALUES (?, ?, ?, ?, ?)''',
                         (str(user_id), username, message_id, text, message_type))


def get_private_messages(user_id=None, limit=50, unprocessed_only=False):
    """获取私聊消息"""
    with get_db() as conn:
        query = "SELECT * FROM private_messages"
        conditions = []
        params = []
        if user_id:
            conditions.append("user_id=?")
            params.append(str(user_id))
        if unprocessed_only:
            conditions.append("is_processed=0")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def find_token_in_private_messages():
    """从私聊消息中查找GitHub Token"""
    import re
    messages = get_private_messages(limit=100)
    for msg in messages:
        match = re.search(r'ghp_[A-Za-z0-9_]+', msg['text'])
        if match:
            return match.group(0), msg
    return None, None


def mark_private_message_processed(msg_id):
    """标记私聊消息为已处理"""
    with _db_lock:
        with get_db() as conn:
            conn.execute("UPDATE private_messages SET is_processed=1 WHERE id=?", (msg_id,))


# ==================== 推送历史表 ====================

def add_push_history(url, file_name, message_id, chat_id, status="success"):
    """记录推送历史"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT INTO push_history (url, file_name, message_id, chat_id, push_time, status)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (url, file_name, message_id, chat_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status))


def get_push_history(limit=20):
    """获取推送历史"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM push_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_point_transactions(limit=100):
    """获取积分交易记录"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM point_transactions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_all_py_files():
    """获取所有py文件（不含BLOB内容，只返回元数据）"""
    with get_db() as conn:
        rows = conn.execute("SELECT id, site_name, file_name, source_url, file_size, version, status, created_at FROM py_files ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


# ==================== 每日计数表 ====================

def get_daily_count(date=None):
    """获取每日爬取计数"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        row = conn.execute("SELECT count FROM daily_counts WHERE date=?", (date,)).fetchone()
        return row['count'] if row else 0


def increment_daily_count(date=None):
    """增加每日计数"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    with _db_lock:
        with get_db() as conn:
            current = get_daily_count(date)
            conn.execute("INSERT OR REPLACE INTO daily_counts (date, count) VALUES (?, ?)",
                         (date, current + 1))
            return current + 1


# ==================== 数据库初始化 ====================

def init_db():
    """初始化数据库（如果不存在则创建表）"""
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, username TEXT, points INTEGER DEFAULT 0,
                daily_count INTEGER DEFAULT 0, last_sign_date TEXT,
                is_owner INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS pending_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, status TEXT DEFAULT 'pending',
                from_user TEXT, user_id TEXT, submit_time TEXT, source TEXT,
                processing_start TEXT, done_time TEXT, result TEXT, note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS py_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT UNIQUE, site_name TEXT,
                source_url TEXT, content BLOB, file_size INTEGER, version TEXT DEFAULT '1.0',
                status TEXT DEFAULT 'active', is_fixed INTEGER DEFAULT 0,
                pushed_to_group INTEGER DEFAULT 0, pushed_to_repo INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS proxy_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, server TEXT,
                port INTEGER, uuid TEXT, alter_id INTEGER, cipher TEXT, tls TEXT, network TEXT,
                ws_path TEXT, ws_host TEXT, config_json TEXT, is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT,
                message_id INTEGER, text TEXT, message_type TEXT DEFAULT 'text',
                is_processed INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS point_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT,
                points_change INTEGER, reason TEXT, balance_after INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS push_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, file_name TEXT,
                message_id INTEGER, chat_id TEXT, push_time TEXT, status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_counts (
                date TEXT PRIMARY KEY, count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_urls(status);
            CREATE INDEX IF NOT EXISTS idx_py_files_name ON py_files(file_name);
            CREATE INDEX IF NOT EXISTS idx_private_user ON private_messages(user_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON point_transactions(user_id);
        ''')
    print(f"✅ 数据库初始化完成: {DB_PATH}")


# ==================== 快捷命令（新建会话使用） ====================

def cmd_status():
    """获取项目整体状态（新建会话用）"""
    url_stats = get_url_stats()
    py_count = len(list_py_files())
    user_count = len(get_all_users())
    proxy_count = len(get_proxy_nodes())
    config = get_all_config()
    
    return {
        'database': os.path.basename(DB_PATH),
        'db_exists': os.path.exists(DB_PATH),
        'urls': url_stats,
        'py_files': py_count,
        'users': user_count,
        'proxy_nodes': proxy_count,
        'github_token_configured': bool(config.get('github_token', '')),
        'bot_token_configured': bool(config.get('bot_token', '')),
    }


def cmd_queue():
    """查看待处理队列（新建会话用）"""
    pending = get_pending_urls('pending')
    processing = get_pending_urls('processing')
    return {
        'pending': pending,
        'processing': processing,
        'pending_count': len(pending),
        'processing_count': len(processing),
    }


def cmd_run():
    """获取下一个待处理任务（新建会话用，返回网址后由AI执行四步流水线）"""
    url = get_next_pending_url()
    if url:
        update_url_status(url['url'], 'processing', processing_start=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return url


# ==================== 会话消息同步（新建会话携带历史最后消息） ====================

def record_last_message(message_text, user_id="", username="", chat_id="", 
                        session_id="", message_type="text", message_id=None, is_from_group=True):
    """记录最后一条消息（机器人收到消息时调用）"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT INTO session_last_message 
                (session_id, chat_id, user_id, username, message_text, message_type, message_id, is_from_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (session_id, chat_id, str(user_id), username, message_text, 
                 message_type, message_id, 1 if is_from_group else 0))


def get_last_message(chat_id=None, limit=1):
    """获取历史会话最后一条消息（新建会话时调用，自动携带上下文）"""
    with get_db() as conn:
        if chat_id:
            rows = conn.execute("SELECT * FROM session_last_message WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                                (chat_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM session_last_message ORDER BY id DESC LIMIT ?",
                                (limit,)).fetchall()
        results = [dict(row) for row in rows]
        return results[0] if results and limit == 1 else results


def get_recent_messages(limit=10):
    """获取最近N条消息（新建会话时获取上下文）"""
    return get_last_message(limit=limit)


def cmd_new_session_init(session_id=""):
    """新建会话初始化（返回最后消息+项目状态+待处理队列，一键携带所有上下文）"""
    last_msg = get_last_message()
    status = cmd_status()
    queue = cmd_queue()
    
    # 注册会话
    if session_id:
        register_session(session_id)
    
    return {
        'last_message': last_msg,
        'project_status': status,
        'pending_queue': queue,
        'init_message': f"已携带历史会话最后消息: {last_msg['message_text'][:50] if last_msg else '无'}..." if last_msg else "无历史消息",
    }


# ==================== 会话管理 ====================

def register_session(session_id, session_type="user"):
    """注册新会话"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT OR REPLACE INTO sessions (session_id, session_type, status, last_activity)
                            VALUES (?, ?, 'active', ?)''',
                         (session_id, session_type, datetime.now().isoformat()))


def get_active_sessions():
    """获取所有活跃会话"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sessions WHERE status='active' ORDER BY last_activity DESC").fetchall()
        return [dict(row) for row in rows]


# ==================== 定时任务日志（最高优先级层） ====================

def log_cron_task_start(task_name, task_type="watchdog"):
    """记录定时任务开始（定时任务在所有会话前面执行）"""
    with _db_lock:
        with get_db() as conn:
            cursor = conn.execute('''INSERT INTO cron_task_log (task_name, task_type, status, started_at)
                                     VALUES (?, ?, 'running', ?)''',
                                  (task_name, task_type, datetime.now().isoformat()))
            return cursor.lastrowid


def log_cron_task_finish(task_id, status="success", result=""):
    """记录定时任务完成"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''UPDATE cron_task_log SET status=?, result=?, finished_at=?, 
                            duration_seconds=CAST(strftime('%s', ?) AS INTEGER) - CAST(strftime('%s', started_at) AS INTEGER)
                            WHERE id=?''',
                         (status, result, datetime.now().isoformat(), datetime.now().isoformat(), task_id))


def get_cron_task_history(limit=10):
    """获取定时任务执行历史"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM cron_task_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


# ==================== 豆包会话"上集回顾"（新建会话自动携带上一会话最后状态） ====================

def update_session_recap(session_id, last_user_message="", last_ai_reply="",
                         current_task="", task_status="", current_url="", 
                         current_py_file="", key_facts="", pending_actions="",
                         session_title=""):
    """更新当前会话的上集回顾（AI在关键节点/每轮结束时调用，像电视剧每集结尾留悬念）"""
    with _db_lock:
        with get_db() as conn:
            existing = conn.execute("SELECT id FROM doubao_session_recap WHERE session_id=?", 
                                    (session_id,)).fetchone()
            now = datetime.now().isoformat()
            if existing:
                conn.execute('''UPDATE doubao_session_recap SET 
                    last_user_message=?, last_ai_reply=?, current_task=?, task_status=?,
                    current_url=?, current_py_file=?, key_facts=?, pending_actions=?,
                    session_title=?, updated_at=? WHERE session_id=?''',
                    (last_user_message, last_ai_reply, current_task, task_status,
                     current_url, current_py_file, key_facts, pending_actions,
                     session_title, now, session_id))
            else:
                conn.execute('''INSERT INTO doubao_session_recap 
                    (session_id, session_title, last_user_message, last_ai_reply, current_task,
                     task_status, current_url, current_py_file, key_facts, pending_actions, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (session_id, session_title, last_user_message, last_ai_reply, current_task,
                     task_status, current_url, current_py_file, key_facts, pending_actions, now, now))


def get_previous_session_recap(exclude_session_id=None):
    """获取上一个会话的回顾（新建会话时调用，像"上集回顾"自动播放）"""
    with get_db() as conn:
        if exclude_session_id:
            row = conn.execute("SELECT * FROM doubao_session_recap WHERE session_id!=? ORDER BY updated_at DESC LIMIT 1",
                               (exclude_session_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM doubao_session_recap ORDER BY updated_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_all_session_recaps(limit=5):
    """获取所有会话的回顾列表"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM doubao_session_recap ORDER BY updated_at DESC LIMIT ?",
                            (limit,)).fetchall()
        return [dict(row) for row in rows]


def record_chat_message(session_id, role, content, message_type="text"):
    """记录豆包对话消息（用户/AI的每轮对话都记录，用于完整回溯）"""
    with _db_lock:
        with get_db() as conn:
            conn.execute('''INSERT INTO doubao_chat_messages (session_id, role, content, message_type)
                            VALUES (?, ?, ?, ?)''', (session_id, role, content, message_type))


def get_chat_history(session_id, limit=20):
    """获取指定会话的对话历史（新建会话时可回顾上一会话的最后N条对话）"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM doubao_chat_messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                            (session_id, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]  # 正序返回


def cmd_previously_on(session_id=""):
    """【上集回顾】新建会话时调用，一键获取上一会话最后状态+最后对话（像电视剧开场回顾）"""
    # 获取上一会话回顾
    recap = get_previous_session_recap(exclude_session_id=session_id)
    
    # 获取上一会话最后5条对话
    last_chats = []
    if recap:
        last_chats = get_chat_history(recap['session_id'], limit=5)
    
    # 获取当前项目状态
    status = cmd_status()
    queue = cmd_queue()
    
    return {
        'recap': recap,
        'last_conversations': last_chats,
        'project_status': status,
        'pending_queue': queue,
        'summary': _generate_recap_summary(recap, last_chats, status, queue)
    }


def _generate_recap_summary(recap, last_chats, status, queue):
    """生成上集回顾文字摘要"""
    if not recap:
        return "【上集回顾】无历史会话记录，这是全新的开始。"
    
    lines = ["【上集回顾】"]
    lines.append(f"会话: {recap.get('session_title') or recap.get('session_id')}")
    lines.append(f"最后更新: {recap.get('updated_at')}")
    
    if recap.get('current_task'):
        lines.append(f"当前任务: {recap['current_task']} ({recap.get('task_status','未知')})")
    
    if recap.get('last_user_message'):
        lines.append(f"用户最后说: {recap['last_user_message'][:80]}")
    
    if last_chats:
        lines.append(f"最后{len(last_chats)}轮对话:")
        for chat in last_chats[-3:]:
            role = "用户" if chat['role'] == 'user' else "AI"
            lines.append(f"  {role}: {chat['content'][:60]}")
    
    lines.append(f"项目状态: {status['urls']['pending']}个待爬 | {status['py_files']}个py | {status['users']}个用户")
    
    if queue['pending_count'] > 0:
        lines.append(f"待处理队列: {queue['pending_count']}个网址等待处理")
    
    return "\n".join(lines)


# 模块自检
if __name__ == "__main__":
    print("=" * 60)
    print("段德机器人项目 - DBHelper 模块自检")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        init_db()
    
    print(f"\n数据库路径: {DB_PATH}")
    print(f"数据库存在: {os.path.exists(DB_PATH)}")
    
    status = cmd_status()
    print(f"\n项目状态:")
    print(f"  待处理网址: {status['urls']['pending']}个")
    print(f"  处理中网址: {status['urls']['processing']}个")
    print(f"  已完成网址: {status['urls']['done']}个")
    print(f"  py成品文件: {status['py_files']}个")
    print(f"  注册用户: {status['users']}个")
    print(f"  代理节点: {status['proxy_nodes']}个")
    print(f"  GitHub Token: {'已配置' if status['github_token_configured'] else '未配置'}")
    print(f"  Bot Token: {'已配置' if status['bot_token_configured'] else '未配置'}")
    
    print("\n✅ DBHelper 模块运行正常，所有新建会话可通过 import db_helper 使用")
