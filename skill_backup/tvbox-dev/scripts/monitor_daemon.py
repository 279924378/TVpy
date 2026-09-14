#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控总控进程（金字塔顶端）
职责：
  1. 网址路由管理：接收Bot同步的网址，分发到路由队列（待掘队列）
  2. 文件推送监控：监控待推送队列，文件落地自动推送到Telegram群
  3. 代理管理：主备双代理自动切换，节点故障自愈
  4. 状态管理：记录所有操作日志和状态

所有Bot和会话都在本监控总控下运行，开多少会话都不冲突。

用法:
  python3 monitor_daemon.py start    # 启动监控总控（后台守护）
  python3 monitor_daemon.py stop     # 停止监控总控
  python3 monitor_daemon.py status   # 查看状态
  python3 monitor_daemon.py restart  # 重启
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import threading
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(SCRIPT_DIR, "monitor_daemon.pid")
LOG_FILE = "/tmp/monitor_daemon.log"
STATE_FILE = os.path.join(SCRIPT_DIR, "monitor_state.json")

# 路由队列（待掘网址）
ROUTE_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_pending_urls.json")
# Bot同步过来的网址（Bot写入，监控读取后移入路由队列）
BOT_SYNC_FILE = os.path.join(SCRIPT_DIR, "tg_bot_sync.json")
# 中央处理器任务队列（监控写入任务，中央处理器读取后创建容器）
CENTRAL_TASK_QUEUE_FILE = os.path.join(SCRIPT_DIR, "central_task_queue.json")
# 中央处理器容器状态上报（中央处理器写入，监控读取）
CONTAINER_REPORT_FILE = os.path.join(SCRIPT_DIR, "container_report.json")
# 待推送文件队列（AI登记，监控读取后推送）
PUSH_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_push_queue.json")
# 推送历史记录
PUSH_HISTORY_FILE = os.path.join(SCRIPT_DIR, "tg_push_history.json")
# Bot配置
TG_CONFIG_FILE = os.path.join(SCRIPT_DIR, "tg_config.json")
# 常驻代理配置
XRAY_CONFIG_FILE = os.path.join(SCRIPT_DIR, "xray_permanent_config.json")
XRAY_BIN = os.path.join(SCRIPT_DIR, "xray")
PROXY_POOL_FILE = os.path.join(SCRIPT_DIR, "..", "assets", "tg_proxy_pool.json")

# 监控参数
CHECK_INTERVAL = 10          # 主循环检测间隔（秒）
PROXY_MAIN_PORT = 10809     # 主代理端口
PROXY_BACKUP_PORT = 10810   # 备用代理端口
MAX_PUSH_RETRY = 3           # 推送最大重试次数


def log(msg):
    """写日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"保存文件失败 {path}: {e}")
        return False


# ==================== 1. 网址路由管理 ====================

def process_bot_sync():
    """处理Bot同步过来的网址，移入路由队列"""
    if not os.path.isfile(BOT_SYNC_FILE):
        return 0

    try:
        sync_data = load_json(BOT_SYNC_FILE, [])
        if not sync_data:
            return 0

        route_queue = load_json(ROUTE_QUEUE_FILE, [])
        added = 0

        for item in sync_data:
            url = item.get("url", "")
            if not url:
                continue
            # 去重
            if not any(p.get("url") == url for p in route_queue):
                # 保留triggered状态（用户发「爬虫+网址」扣积分主动触发）
                item_status = item.get("status", "pending")
                route_entry = {
                    "url": url,
                    "from_user": item.get("from_user", "未知"),
                    "user_id": item.get("user_id"),
                    "time": item.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "status": item_status,
                    "source": "bot_sync",
                }
                if item_status == "triggered":
                    route_entry["trigger_time"] = item.get("trigger_time")
                    route_entry["trigger_by"] = item.get("trigger_by")
                    log(f"[路由] ⚡ 主动触发网址入队: {url} (来自: {item.get('from_user')}, status=triggered)")
                else:
                    log(f"[路由] 网址入队: {url} (来自: {item.get('from_user')})")
                route_queue.append(route_entry)
                added += 1

        if added > 0:
            save_json(ROUTE_QUEUE_FILE, route_queue)
            # 清空Bot同步文件
            save_json(BOT_SYNC_FILE, [])
            log(f"[路由] 本次新增{added}个网址，路由队列共{len(route_queue)}个待掘")

            # 金字塔架构：同时下发任务给中央处理器，创建独立代理容器
            dispatch_to_central(sync_data)

        return added
    except Exception as e:
        log(f"[路由] 处理Bot同步异常: {e}")
        return 0


def dispatch_to_central(sync_data):
    """金字塔架构：把网址任务下发给中央处理器，由中央处理器创建独立代理容器
    每个任务一个容器，独占代理端口，开多少任务都不冲突"""
    try:
        tasks = load_json(CENTRAL_TASK_QUEUE_FILE, [])
        dispatched = 0

        for item in sync_data:
            url = item.get("url", "")
            if not url:
                continue
            # 去重：已在任务队列中的不重复下发
            if any(t.get("url") == url and t.get("status") in ("pending", "dispatched", "triggered") for t in tasks):
                continue

            task_id = f"task_{int(time.time())}_{dispatched}"
            item_status = item.get("status", "pending")
            task_entry = {
                "task_id": task_id,
                "url": url,
                "from_user": item.get("from_user", "未知"),
                "user_id": item.get("user_id"),
                "status": item_status,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if item_status == "triggered":
                task_entry["trigger_time"] = item.get("trigger_time")
                task_entry["trigger_by"] = item.get("trigger_by")
            tasks.append(task_entry)
            dispatched += 1
            if item_status == "triggered":
                log(f"[下发] ⚡ 主动触发任务{task_id}已下发中央处理器: {url}")
            else:
                log(f"[下发] 任务{task_id}已下发中央处理器: {url}")

        if dispatched > 0:
            save_json(CENTRAL_TASK_QUEUE_FILE, tasks)
            log(f"[下发] 本次下发{dispatched}个任务，中央处理器将创建独立代理容器")

        return dispatched
    except Exception as e:
        log(f"[下发] 下发中央处理器异常: {e}")
        return 0


# ==================== 2. 文件推送监控 ====================

def get_proxy_port():
    """获取可用的代理端口（优先主代理，失败用备用）"""
    for port in [PROXY_MAIN_PORT, PROXY_BACKUP_PORT]:
        try:
            proxy = urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{port}",
                "https": f"http://127.0.0.1:{port}"
            })
            opener = urllib.request.build_opener(proxy)
            req = urllib.request.Request("https://api.telegram.org", method="HEAD")
            r = opener.open(req, timeout=8)
            if r.status == 200:
                return port
        except Exception:
            continue
    return None


def send_document(token, chat_id, file_path, caption, proxy_port):
    """发送文件附件到Telegram群（手动构造multipart，支持中文文件名）"""
    import urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    filename = os.path.basename(file_path)

    boundary = "----MonitorBoundary" + "".join("0123456789abcdef"[i % 16] for i in range(16))
    body = b""

    # chat_id
    body += f"--{boundary}\r\n".encode("utf-8")
    body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body += str(chat_id).encode("utf-8") + b"\r\n"

    # caption
    if caption:
        body += f"--{boundary}\r\n".encode("utf-8")
        body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
        body += caption.encode("utf-8") + b"\r\n"

    # document
    with open(file_path, "rb") as f:
        file_data = f.read()
    filename_encoded = urllib.parse.quote(filename)
    body += f"--{boundary}\r\n".encode("utf-8")
    body += f'Content-Disposition: form-data; name="document"; filename="{filename_encoded}"\r\n'.encode("utf-8")
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += file_data + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")

    proxy = urllib.request.ProxyHandler({
        "http": f"http://127.0.0.1:{proxy_port}",
        "https": f"http://127.0.0.1:{proxy_port}"
    })
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    resp = opener.open(req, timeout=120)
    return json.loads(resp.read().decode("utf-8"))


def send_message(token, chat_id, text, proxy_port):
    """发送文字消息"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    proxy = urllib.request.ProxyHandler({
        "http": f"http://127.0.0.1:{proxy_port}",
        "https": f"http://127.0.0.1:{proxy_port}"
    })
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    resp = opener.open(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))


def process_push_queue():
    """处理待推送文件队列，自动推送到Telegram群"""
    push_queue = load_json(PUSH_QUEUE_FILE, [])
    pending = [x for x in push_queue if x.get("status") == "pending"]

    if not pending:
        return 0

    # 加载Bot配置
    tg_config = load_json(TG_CONFIG_FILE, {})
    bot_cfg = tg_config.get("bot", {})
    token = bot_cfg.get("token", "")
    chat_id = bot_cfg.get("chat_id", "")

    if not token or not chat_id:
        log("[推送] Bot配置缺失，跳过")
        return 0

    proxy_port = get_proxy_port()
    if not proxy_port:
        log("[推送] 无可用代理，跳过本轮")
        return 0

    pushed = 0
    for item in pending:
        file_path = item.get("file_path", "")
        file_name = item.get("file_name", "")
        site_name = item.get("site_name", "")
        retry_count = item.get("retry_count", 0)

        if not os.path.isfile(file_path):
            item["status"] = "failed"
            item["error"] = "文件不存在"
            log(f"[推送] 文件不存在，标记失败: {file_name}")
            continue

        if retry_count >= MAX_PUSH_RETRY:
            item["status"] = "failed"
            item["error"] = "超过最大重试次数"
            log(f"[推送] 超过重试次数，标记失败: {file_name}")
            continue

        try:
            # 发送文件附件
            caption = f"📦 {site_name or file_name}\n文件: {file_name}\n大小: {item.get('file_size', 0)//1024} KB\n—— 监控总控自动推送"
            result = send_document(token, chat_id, file_path, caption, proxy_port)

            if result.get("ok"):
                msg_id = result.get("result", {}).get("message_id", 0)
                item["status"] = "done"
                item["message_id"] = msg_id
                item["pushed_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                pushed += 1
                log(f"[推送] ✅ {file_name} 推送成功 (消息ID:{msg_id})")

                # 记录推送历史
                history = load_json(PUSH_HISTORY_FILE, {})
                site_key = site_name or file_name
                if site_key not in history:
                    history[site_key] = {"message_ids": {}, "last_push_time": ""}
                ext = os.path.splitext(file_name)[1].lower()
                if ext == ".py":
                    history[site_key]["message_ids"]["py"] = msg_id
                elif ext == ".zip":
                    history[site_key]["message_ids"]["zip"] = msg_id
                history[site_key]["last_push_time"] = item["pushed_time"]
                save_json(PUSH_HISTORY_FILE, history)
            else:
                item["retry_count"] = retry_count + 1
                err = result.get("description", "未知错误")
                log(f"[推送] ❌ {file_name} 推送失败: {err} (重试{item['retry_count']}/{MAX_PUSH_RETRY})")

        except Exception as e:
            item["retry_count"] = retry_count + 1
            log(f"[推送] ❌ {file_name} 推送异常: {e} (重试{item['retry_count']}/{MAX_PUSH_RETRY})")

    save_json(PUSH_QUEUE_FILE, push_queue)
    return pushed


# ==================== 3. 代理管理 ====================

def check_proxy(port):
    """检查代理是否可用"""
    try:
        proxy = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}"
        })
        opener = urllib.request.build_opener(proxy)
        req = urllib.request.Request("https://api.telegram.org", method="HEAD")
        r = opener.open(req, timeout=8)
        return r.status == 200
    except Exception:
        return False


def proxy_management():
    """代理管理：主备切换，故障自愈"""
    state = load_json(STATE_FILE, {})
    main_ok = check_proxy(PROXY_MAIN_PORT)
    backup_ok = check_proxy(PROXY_BACKUP_PORT)

    state["proxy_main_ok"] = main_ok
    state["proxy_backup_ok"] = backup_ok
    state["last_proxy_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not main_ok and not backup_ok:
        log("[代理] ⚠️ 主备代理均不可用，尝试重启主代理...")
        # 尝试重启主代理
        try:
            subprocess.Popen(
                [XRAY_BIN, "run", "-c", XRAY_CONFIG_FILE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            time.sleep(3)
            if check_proxy(PROXY_MAIN_PORT):
                log("[代理] ✅ 主代理重启成功")
            else:
                log("[代理] ❌ 主代理重启失败，需要人工介入")
        except Exception as e:
            log(f"[代理] 重启异常: {e}")
    elif not main_ok and backup_ok:
        log("[代理] ⚠️ 主代理不可用，当前使用备用代理")
    elif main_ok and not backup_ok:
        log("[代理] ⚠️ 备用代理不可用，主代理正常")

    save_json(STATE_FILE, state)


# ==================== 主循环 ====================

def main_loop():
    """监控总控主循环"""
    log("=" * 50)
    log("🏛️  监控总控启动（金字塔顶端）")
    log(f"  路由队列: {ROUTE_QUEUE_FILE}")
    log(f"  Bot同步: {BOT_SYNC_FILE}")
    log(f"  推送队列: {PUSH_QUEUE_FILE}")
    log(f"  主代理端口: {PROXY_MAIN_PORT}")
    log(f"  备用代理端口: {PROXY_BACKUP_PORT}")
    log("=" * 50)

    cycle = 0
    while True:
        try:
            cycle += 1

            # 1. 处理Bot同步的网址 → 路由队列
            route_count = process_bot_sync()

            # 2. 处理待推送文件 → 自动推送
            push_count = process_push_queue()

            # 3. 代理管理（每10轮检查一次，约100秒）
            if cycle % 10 == 1:
                proxy_management()

            if route_count > 0 or push_count > 0:
                log(f"[第{cycle}轮] 路由新增{route_count}个，推送完成{push_count}个")

        except Exception as e:
            log(f"[主循环] 异常: {e}")

        time.sleep(CHECK_INTERVAL)


def cmd_start():
    """启动监控总控"""
    pid = get_pid()
    if pid and is_running(pid):
        print(f"监控总控已在运行 (PID: {pid})")
        return

    print("🚀 启动监控总控...")
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    print(f"监控总控已启动 (PID: {proc.pid})")
    print(f"日志: {LOG_FILE}")


def cmd_stop():
    """停止监控总控"""
    pid = get_pid()
    if not pid or not is_running(pid):
        print("监控总控未在运行")
        if os.path.isfile(PID_FILE):
            os.unlink(PID_FILE)
        return

    print(f"🛑 停止监控总控 (PID: {pid})...")
    try:
        os.kill(pid, 15)
        time.sleep(2)
        if is_running(pid):
            os.kill(pid, 9)
            time.sleep(1)
    except Exception as e:
        print(f"停止异常: {e}")

    if os.path.isfile(PID_FILE):
        os.unlink(PID_FILE)
    print("监控总控已停止")


def cmd_status():
    """查看状态"""
    pid = get_pid()
    running = is_running(pid)
    state = load_json(STATE_FILE, {})

    print("=" * 45)
    print("  🏛️  监控总控状态")
    print("=" * 45)
    print(f"  进程: {'✅ 运行中' if running else '❌ 未运行'} (PID: {pid or '无'})")
    print(f"  主代理({PROXY_MAIN_PORT}): {'✅ 正常' if state.get('proxy_main_ok') else '❌ 异常'}")
    print(f"  备用代理({PROXY_BACKUP_PORT}): {'✅ 正常' if state.get('proxy_backup_ok') else '❌ 异常'}")
    print(f"  上次代理检查: {state.get('last_proxy_check', '从未')}")

    route_queue = load_json(ROUTE_QUEUE_FILE, [])
    pending_routes = len([x for x in route_queue if x.get("status") == "pending"])
    print(f"  路由队列: {pending_routes}个待掘")

    push_queue = load_json(PUSH_QUEUE_FILE, [])
    pending_push = len([x for x in push_queue if x.get("status") == "pending"])
    print(f"  推送队列: {pending_push}个待推送")

    bot_sync = load_json(BOT_SYNC_FILE, [])
    print(f"  Bot同步缓冲: {len(bot_sync)}个待处理")
    print("=" * 45)


def get_pid():
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                return int(f.read().strip())
        except Exception:
            return None
    return None


def is_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "restart":
        cmd_stop()
        time.sleep(1)
        cmd_start()
    elif cmd == "status":
        cmd_status()
    elif cmd == "run":
        # 内部运行模式（由start启动）
        main_loop()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
