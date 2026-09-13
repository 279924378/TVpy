#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中央处理器（金字塔中间层）
职责：
  1. 接收金字塔顶端下发的任务指令
  2. 新建任务容器：分配独立代理端口 + 独立工作目录
  3. 启动容器内的xray代理（独占端口，容器间完全隔离，绝不冲突）
  4. 监控容器状态，任务完成后回收资源（杀代理、删临时目录、释放端口）
  5. 向顶端上报任务状态

容器池：最多同时运行N个容器，端口范围10900-10999，每个容器独占一个端口。

用法:
  python3 central_processor.py start          # 启动中央处理器（后台守护）
  python3 central_processor.py stop           # 停止
  python3 central_processor.py status         # 查看容器池状态
  python3 central_processor.py dispatch <url> # 手动下发一个任务（测试用）
  python3 central_processor.py list           # 列出所有容器
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
PID_FILE = os.path.join(SCRIPT_DIR, "central_processor.pid")
LOG_FILE = "/tmp/central_processor.log"
STATE_FILE = os.path.join(SCRIPT_DIR, "central_state.json")

# 顶端指令队列（monitor_daemon写入，中央处理器读取）
TASK_QUEUE_FILE = os.path.join(SCRIPT_DIR, "central_task_queue.json")
# 容器状态上报（中央处理器写入，顶端读取）
CONTAINER_REPORT_FILE = os.path.join(SCRIPT_DIR, "container_report.json")
# 路由队列（待掘网址，中央处理器智能调度：pending→processing→done/failed）
ROUTE_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_pending_urls.json")
# 代理池配置
PROXY_POOL_FILE = os.path.join(SCRIPT_DIR, "..", "assets", "tg_proxy_pool.json")
XRAY_BIN = os.path.join(SCRIPT_DIR, "xray")

# 容器池配置
MAX_CONTAINERS = 5            # 最多同时运行5个容器
PORT_RANGE_START = 10900      # 代理端口起始
PORT_RANGE_END = 10999        # 代理端口结束
CONTAINER_WORKSPACE = os.path.join(SCRIPT_DIR, "containers")  # 容器工作目录根
CHECK_INTERVAL = 5             # 主循环检测间隔（秒）
CONTAINER_TIMEOUT = 1800       # 容器最大存活时间（秒），30分钟无心跳自动回收，旧会话唤醒时重建
SESSION_HEARTBEAT_FILE = os.path.join(SCRIPT_DIR, "session_heartbeat.json")  # 会话心跳文件
# 中央处理器指令队列（技能发指令到这里，中央处理器验证后下发顶端执行）
COMMAND_QUEUE_FILE = os.path.join(SCRIPT_DIR, "central_command_queue.json")
# 顶端推送队列（中央处理器验证指令后写入这里，顶端监控执行）
TOP_PUSH_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_push_queue.json")


def log(msg):
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


# ==================== 容器管理 ====================

def load_containers():
    """加载容器状态"""
    state = load_json(STATE_FILE, {})
    return state.get("containers", {})


def save_containers(containers):
    """保存容器状态"""
    state = load_json(STATE_FILE, {})
    state["containers"] = containers
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json(STATE_FILE, state)


def allocate_port(containers):
    """分配一个未被占用的代理端口"""
    used_ports = set()
    for c in containers.values():
        if c.get("status") in ("running", "starting"):
            used_ports.add(c.get("proxy_port", 0))

    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port not in used_ports:
            # 额外检查端口是否真的空闲
            if not is_port_in_use(port):
                return port
    return None


def is_port_in_use(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def get_proxy_node():
    """从代理池获取一个可用节点"""
    pool = load_json(PROXY_POOL_FILE, {})
    # 代理池是字典结构，节点在nodes字段里
    nodes = pool.get("nodes", []) if isinstance(pool, dict) else pool
    if not nodes:
        return None
    # 简单轮询，返回第一个节点
    return nodes[0]


def generate_xray_config(node, port):
    """生成xray配置文件内容"""
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": port,
            "listen": "127.0.0.1",
            "protocol": "http",
            "settings": {"timeout": 300}
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node.get("server", ""),
                    "port": node.get("port", 443),
                    "users": [{
                        "id": node.get("uuid", ""),
                        "encryption": "none",
                        "flow": node.get("flow", "xtls-rprx-vision")
                    }]
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": node.get("server_name", ""),
                    "allowInsecure": node.get("allow_insecure", True)
                }
            }
        }]
    }
    return config


def create_container(task_id, url):
    """新建任务容器：分配端口、创建工作目录、启动xray代理"""
    containers = load_containers()

    # 检查容器数量上限
    running_count = len([c for c in containers.values() if c.get("status") in ("running", "starting")])
    if running_count >= MAX_CONTAINERS:
        log(f"[容器] 已达上限{MAX_CONTAINERS}个，任务{task_id}等待")
        return None, "容器池已满"

    # 分配端口
    port = allocate_port(containers)
    if not port:
        log(f"[容器] 无可用端口，任务{task_id}等待")
        return None, "无可用端口"

    # 创建工作目录
    container_dir = os.path.join(CONTAINER_WORKSPACE, task_id)
    os.makedirs(container_dir, exist_ok=True)
    os.makedirs(os.path.join(container_dir, "output"), exist_ok=True)

    # 生成xray配置
    node = get_proxy_node()
    if not node:
        return None, "代理池为空"

    xray_config = generate_xray_config(node, port)
    config_path = os.path.join(container_dir, "xray_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(xray_config, f, ensure_ascii=False, indent=2)

    # 启动xray代理
    log_file = os.path.join(container_dir, "xray.log")
    try:
        proc = subprocess.Popen(
            [XRAY_BIN, "run", "-c", config_path],
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
    except Exception as e:
        return None, f"启动xray失败: {e}"

    # 等待代理启动
    time.sleep(2)
    proxy_ok = check_proxy(port)

    container = {
        "task_id": task_id,
        "url": url,
        "proxy_port": port,
        "proxy_node": node.get("name", "unknown"),
        "workspace": container_dir,
        "output_dir": os.path.join(container_dir, "output"),
        "xray_pid": proc.pid,
        "xray_config": config_path,
        "status": "running" if proxy_ok else "starting",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_heartbeat": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    containers[task_id] = container
    save_containers(containers)

    if proxy_ok:
        log(f"[容器] ✅ 创建成功 {task_id} 代理端口:{port} 节点:{node.get('name')}")
    else:
        log(f"[容器] ⏳ 创建中 {task_id} 代理端口:{port} 等待代理连通")

    return container, None


def check_proxy(port):
    """检查容器代理是否可用"""
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


def destroy_container(task_id):
    """销毁容器：杀xray进程、删除工作目录、释放端口"""
    containers = load_containers()
    if task_id not in containers:
        return False

    container = containers[task_id]
    log(f"[容器] 🗑️  销毁 {task_id} 端口:{container.get('proxy_port')}")

    # 杀xray进程
    pid = container.get("xray_pid")
    if pid:
        try:
            os.kill(pid, 15)
            time.sleep(1)
            if os.path.exists(f"/proc/{pid}"):
                os.kill(pid, 9)
        except Exception:
            pass

    # 删除工作目录
    workspace = container.get("workspace", "")
    if workspace and os.path.isdir(workspace):
        import shutil
        try:
            shutil.rmtree(workspace)
        except Exception as e:
            log(f"[容器] 删除工作目录失败: {e}")

    # 从状态中移除
    del containers[task_id]
    save_containers(containers)
    log(f"[容器] ✅ 已销毁 {task_id}")
    return True


def process_session_heartbeats():
    """处理会话心跳：豆包会话有新消息时写入心跳，中央处理器刷新容器存活时间
    如果容器已超时销毁，则自动唤醒重建容器"""
    if not os.path.isfile(SESSION_HEARTBEAT_FILE):
        return 0

    try:
        with open(SESSION_HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            heartbeats = json.load(f)
    except Exception:
        return 0

    if not heartbeats:
        return 0

    containers = load_containers()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refreshed = 0
    awakened = 0

    for session_id, hb in heartbeats.items():
        # 查找该会话对应的容器（task_id以session_id开头，或直接匹配）
        container = None
        for cid, c in containers.items():
            if c.get("session_id") == session_id or cid == session_id:
                container = c
                container_id = cid
                break

        if container:
            # 容器存在，刷新心跳
            container["last_heartbeat"] = now_str
            container["status"] = "running"
            refreshed += 1
            log(f"[会话] 💓 {session_id} 心跳刷新，容器端口:{container.get('proxy_port')}")
        else:
            # 容器不存在（已超时销毁），自动唤醒重建
            log(f"[会话] 🔔 {session_id} 旧会话唤醒，重建容器...")
            url = hb.get("url", "")
            new_container, err = create_container(session_id, url)
            if new_container:
                new_container["session_id"] = session_id
                new_container["last_heartbeat"] = now_str
                containers[session_id] = new_container
                awakened += 1
                log(f"[会话] ✅ {session_id} 唤醒成功，代理端口:{new_container.get('proxy_port')}")
            else:
                log(f"[会话] ❌ {session_id} 唤醒失败: {err}")

    save_containers(containers)

    # 清空心跳文件
    try:
        with open(SESSION_HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    except Exception:
        pass

    if refreshed > 0 or awakened > 0:
        log(f"[会话] 心跳处理完成: 刷新{refreshed}个，唤醒{awakened}个")

    return refreshed + awakened


def monitor_containers():
    """监控所有容器：检查代理状态、超时回收、上报状态"""
    containers = load_containers()
    now = time.time()
    report = []

    for task_id, container in list(containers.items()):
        # 检查是否超时：优先用last_heartbeat（会话活动时间），没有则用created_at
        # 3小时无心跳自动回收，旧会话唤醒时重建
        last_activity = container.get("last_heartbeat") or container.get("created_at", "")
        if last_activity:
            try:
                activity_ts = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S").timestamp()
                if now - activity_ts > CONTAINER_TIMEOUT:
                    hours = CONTAINER_TIMEOUT // 3600
                    log(f"[容器] ⏰ {task_id} {hours}小时无活动，自动回收（旧会话唤醒时重建）")
                    destroy_container(task_id)
                    continue
            except Exception:
                pass

        # 检查代理状态
        port = container.get("proxy_port", 0)
        if container.get("status") == "running":
            if not check_proxy(port):
                container["status"] = "proxy_down"
                log(f"[容器] ⚠️ {task_id} 代理端口{port}不可用")
            else:
                container["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 收集上报信息
        report.append({
            "task_id": task_id,
            "url": container.get("url", ""),
            "proxy_port": port,
            "proxy_node": container.get("proxy_node", ""),
            "status": container.get("status", "unknown"),
            "output_dir": container.get("output_dir", ""),
            "created_at": container.get("created_at", ""),
        })

    save_containers(containers)
    save_json(CONTAINER_REPORT_FILE, report)
    return report


# ==================== 任务分发 ====================

def process_task_queue():
    """处理顶端下发的任务队列，为每个任务新建容器"""
    if not os.path.isfile(TASK_QUEUE_FILE):
        return 0

    try:
        tasks = load_json(TASK_QUEUE_FILE, [])
        if not tasks:
            return 0

        dispatched = 0
        for task in tasks:
            if task.get("status") != "pending":
                continue

            task_id = task.get("task_id", "")
            url = task.get("url", "")

            if not task_id or not url:
                task["status"] = "failed"
                task["error"] = "缺少task_id或url"
                continue

            # 新建容器
            container, err = create_container(task_id, url)
            if container:
                task["status"] = "dispatched"
                task["proxy_port"] = container.get("proxy_port")
                task["workspace"] = container.get("workspace")
                task["dispatched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dispatched += 1
                log(f"[分发] ✅ 任务{task_id}已分发到容器 端口:{container.get('proxy_port')}")
            else:
                # 容器池满或端口不足，保持pending等待
                if "已满" in err or "端口" in err:
                    log(f"[分发] ⏳ 任务{task_id}等待: {err}")
                else:
                    task["status"] = "failed"
                    task["error"] = err
                    log(f"[分发] ❌ 任务{task_id}失败: {err}")

        save_json(TASK_QUEUE_FILE, tasks)
        return dispatched
    except Exception as e:
        log(f"[分发] 处理任务队列异常: {e}")
        return 0


# ==================== 主循环 ====================

def main_loop():
    log("=" * 50)
    log("⚙️  中央处理器启动（金字塔中间层）")
    log(f"  容器上限: {MAX_CONTAINERS}个")
    log(f"  代理端口范围: {PORT_RANGE_START}-{PORT_RANGE_END}")
    log(f"  容器工作目录: {CONTAINER_WORKSPACE}")
    log(f"  任务队列: {TASK_QUEUE_FILE}")
    log("=" * 50)

    os.makedirs(CONTAINER_WORKSPACE, exist_ok=True)

    cycle = 0
    while True:
        try:
            cycle += 1

            # 1. 处理任务队列，新建容器
            dispatched = process_task_queue()

            # 2. 处理会话心跳：刷新存活时间，旧会话唤醒重建容器
            heartbeat_count = process_session_heartbeats()

            # 3. 监控所有容器（30分钟无心跳自动回收）
            report = monitor_containers()
            running = len([r for r in report if r["status"] == "running"])

            if dispatched > 0 or heartbeat_count > 0 or cycle % 12 == 1:
                log(f"[第{cycle}轮] 分发{dispatched}个，心跳{heartbeat_count}个，运行中{running}个容器")

        except Exception as e:
            log(f"[主循环] 异常: {e}")

        time.sleep(CHECK_INTERVAL)


# ==================== 命令行 ====================

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


def cmd_start():
    pid = get_pid()
    if pid and is_running(pid):
        print(f"中央处理器已在运行 (PID: {pid})")
        return
    print("🚀 启动中央处理器...")
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    print(f"中央处理器已启动 (PID: {proc.pid})")
    print(f"日志: {LOG_FILE}")


def cmd_stop():
    pid = get_pid()
    if not pid or not is_running(pid):
        print("中央处理器未在运行")
        if os.path.isfile(PID_FILE):
            os.unlink(PID_FILE)
        return
    print(f"🛑 停止中央处理器 (PID: {pid})...")
    try:
        os.kill(pid, 15)
        time.sleep(2)
        if is_running(pid):
            os.kill(pid, 9)
    except Exception as e:
        print(f"停止异常: {e}")
    if os.path.isfile(PID_FILE):
        os.unlink(PID_FILE)
    print("中央处理器已停止")


def cmd_status():
    pid = get_pid()
    running = is_running(pid)
    containers = load_containers()
    running_containers = [c for c in containers.values() if c.get("status") in ("running", "starting")]

    print("=" * 50)
    print("  ⚙️  中央处理器状态")
    print("=" * 50)
    print(f"  进程: {'✅ 运行中' if running else '❌ 未运行'} (PID: {pid or '无'})")
    print(f"  容器上限: {MAX_CONTAINERS}个")
    print(f"  运行中容器: {len(running_containers)}个")
    print(f"  代理端口范围: {PORT_RANGE_START}-{PORT_RANGE_END}")
    print("-" * 50)
    if running_containers:
        for c in running_containers:
            print(f"  📦 {c['task_id']}")
            print(f"     网址: {c.get('url', '')[:50]}")
            print(f"     代理端口: {c.get('proxy_port')} ({c.get('proxy_node')})")
            print(f"     状态: {c.get('status')}")
            print(f"     创建时间: {c.get('created_at')}")
            print()
    else:
        print("  （无运行中容器）")
    print("=" * 50)


def cmd_dispatch(url):
    """手动下发一个任务（测试用）"""
    task_id = f"task_{int(time.time())}"
    tasks = load_json(TASK_QUEUE_FILE, [])
    tasks.append({
        "task_id": task_id,
        "url": url,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_json(TASK_QUEUE_FILE, tasks)
    print(f"✅ 任务已下发: {task_id}")
    print(f"   网址: {url}")
    print(f"   中央处理器将在{CHECK_INTERVAL}秒内创建容器")


def cmd_command_push(args):
    """【铁律】技能推送必须经过中央处理器发指令
    技能调用此函数发推送指令，中央处理器验证后下发顶端执行
    禁止技能直接调用tg_pusher.py或直接写tg_push_queue.json

    用法: central_processor.py command push --file <path1> [--file <path2>] [--url <url>] [--site <name>]
    """
    # 解析参数
    file_paths = []
    url = ""
    site_name = ""
    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            file_paths.append(args[i + 1])
            i += 2
        elif args[i] == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif args[i] == "--site" and i + 1 < len(args):
            site_name = args[i + 1]
            i += 2
        else:
            i += 1

    if not file_paths:
        print("❌ 错误：必须指定 --file 参数（可多次指定）")
        print("用法: central_processor.py command push --file <path1> [--file <path2>] [--url <url>] [--site <name>]")
        sys.exit(1)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commands = load_json(COMMAND_QUEUE_FILE, [])
    push_queue = load_json(TOP_PUSH_QUEUE_FILE, [])
    success_count = 0
    command_ids = []

    for file_path in file_paths:
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            print(f"⚠️  文件不存在，跳过: {abs_path}")
            continue

        command_id = f"cmd_{int(time.time())}_{os.getpid()}_{success_count}"
        file_size = os.path.getsize(abs_path)
        file_name = os.path.basename(abs_path)

        # 1. 记录指令到中央处理器指令队列
        command_record = {
            "command_id": command_id,
            "type": "push",
            "file_path": abs_path,
            "file_name": file_name,
            "file_size": file_size,
            "url": url,
            "site_name": site_name,
            "status": "dispatched",
            "created_at": now_str,
            "dispatched_at": now_str,
        }
        commands.append(command_record)
        command_ids.append(command_id)

        # 2. 下发指令到顶端推送队列（去重）
        if not any(item.get("file_path") == abs_path and item.get("status") == "pending" for item in push_queue):
            push_queue.append({
                "file_path": abs_path,
                "file_name": file_name,
                "file_size": file_size,
                "site_name": site_name,
                "url": url,
                "command_id": command_id,
                "register_time": now_str,
                "status": "pending",
                "retry_count": 0,
            })

        success_count += 1
        print(f"✅ 已下发: {file_name} ({file_size} bytes)")

    save_json(COMMAND_QUEUE_FILE, commands)
    save_json(TOP_PUSH_QUEUE_FILE, push_queue)

    # 3. 返回结果
    print("=" * 50)
    print("  ⚙️  中央处理器 - 推送指令已下发")
    print("=" * 50)
    print(f"  指令数: {success_count}个文件")
    if site_name:
        print(f"  站点: {site_name}")
    if url:
        print(f"  关联网址: {url}")
        print(f"  （推送成功后自动标记为已爬）")
    print(f"  状态: 已下发顶端，将在10秒内自动推送")
    print("=" * 50)
    print("  【铁律】技能推送必须经过中央处理器，禁止直接调用推送脚本")
    print("=" * 50)

    return command_ids


# ==================== 智能任务调度（全自动任务分配） ====================

def cmd_task_get(session_id=""):
    """【全自动】智能获取一个待掘网址任务
    技能触发时调用此函数，中央处理器从路由队列中取一个pending的网址，
    标记为processing（防止其他会话重复处理），返回给会话执行。
    多个会话并行时，中央处理器自动分配不同网址，绝不重复。

    用法: central_processor.py task get [session_id]
    """
    route_queue = load_json(ROUTE_QUEUE_FILE, [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 找第一个pending的网址
    for item in route_queue:
        if item.get("status") == "pending":
            item["status"] = "processing"
            item["processing_session"] = session_id or f"session_{os.getpid()}"
            item["processing_start"] = now_str
            save_json(ROUTE_QUEUE_FILE, route_queue)

            print("=" * 50)
            print("  ⚙️  中央处理器 - 智能任务分配")
            print("=" * 50)
            print(f"  任务网址: {item['url']}")
            print(f"  投递者: {item.get('from_user', '未知')}")
            print(f"  投递时间: {item.get('time', '未知')}")
            print(f"  处理会话: {item['processing_session']}")
            print(f"  状态: 已标记为处理中（其他会话不会重复取）")
            print("=" * 50)
            print(f"  剩余待处理: {len([x for x in route_queue if x.get('status') == 'pending'])}个")
            print(f"  处理中: {len([x for x in route_queue if x.get('status') == 'processing'])}个")
            print("=" * 50)
            return item

    # 没有pending的网址
    print("=" * 50)
    print("  ⚙️  中央处理器 - 任务队列状态")
    print("=" * 50)
    print("  ❌ 待掘队列为空，没有待处理的网址")
    print(f"  处理中: {len([x for x in route_queue if x.get('status') == 'processing'])}个")
    print(f"  已完成: {len([x for x in route_queue if x.get('status') == 'done'])}个")
    print(f"  失败: {len([x for x in route_queue if x.get('status') == 'failed'])}个")
    print("=" * 50)
    print("  道友可以往Telegram群里扔个网址，Bot会自动入队")
    print("=" * 50)
    return None


def cmd_task_done(url, success=True, session_id=""):
    """【全自动】上报任务完成
    技能处理完网址后调用此函数，中央处理器标记为done或failed。
    失败的网址可选择回退为pending，让其他会话重试。

    用法: central_processor.py task done <url> [--success/--failed] [--retry]
    """
    route_queue = load_json(ROUTE_QUEUE_FILE, [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found = False

    for item in route_queue:
        if item.get("url") == url:
            found = True
            if success:
                item["status"] = "done"
                item["done_time"] = now_str
                item["done_session"] = session_id or item.get("processing_session", "")
                print(f"✅ 任务已标记为完成: {url}")
            else:
                # 失败：默认标记为failed，--retry则回退为pending
                if "--retry" in sys.argv:
                    item["status"] = "pending"
                    item["fail_count"] = item.get("fail_count", 0) + 1
                    print(f"⚠️  任务失败，已回退为待处理（可重试）: {url}")
                else:
                    item["status"] = "failed"
                    item["fail_time"] = now_str
                    item["fail_count"] = item.get("fail_count", 0) + 1
                    print(f"❌ 任务已标记为失败: {url}")
            break

    if not found:
        print(f"⚠️  未找到该网址在队列中: {url}")
        return False

    save_json(ROUTE_QUEUE_FILE, route_queue)

    # 统计
    pending = len([x for x in route_queue if x.get("status") == "pending"])
    processing = len([x for x in route_queue if x.get("status") == "processing"])
    done = len([x for x in route_queue if x.get("status") == "done"])
    failed = len([x for x in route_queue if x.get("status") == "failed"])

    print("=" * 50)
    print("  📊 队列状态统计")
    print("=" * 50)
    print(f"  待处理: {pending}个")
    print(f"  处理中: {processing}个")
    print(f"  已完成: {done}个")
    print(f"  失败: {failed}个")
    print("=" * 50)

    return True


def cmd_task_status():
    """查看路由队列完整状态"""
    route_queue = load_json(ROUTE_QUEUE_FILE, [])
    print("=" * 55)
    print("  📋 路由队列完整状态（智能任务调度）")
    print("=" * 55)

    status_map = {
        "pending": ("⏳ 待处理", "🟡"),
        "processing": ("⚙️ 处理中", "🔵"),
        "done": ("✅ 已完成", "🟢"),
        "failed": ("❌ 失败", "🔴"),
    }

    for i, item in enumerate(route_queue, 1):
        status = item.get("status", "pending")
        status_text, icon = status_map.get(status, (status, "⚪"))
        print(f"  {icon} {i}. {item['url'][:50]}")
        print(f"     状态: {status_text} | 投递者: {item.get('from_user', '?')} | 时间: {item.get('time', '?')}")
        if status == "processing":
            print(f"     处理会话: {item.get('processing_session', '?')} | 开始: {item.get('processing_start', '?')}")
        if status == "done":
            print(f"     完成时间: {item.get('done_time', '?')}")
        if status == "failed":
            print(f"     失败次数: {item.get('fail_count', 0)} | 失败时间: {item.get('fail_time', '?')}")
        print()

    pending = len([x for x in route_queue if x.get("status") == "pending"])
    processing = len([x for x in route_queue if x.get("status") == "processing"])
    done = len([x for x in route_queue if x.get("status") == "done"])
    failed = len([x for x in route_queue if x.get("status") == "failed"])

    print("=" * 55)
    print(f"  总计: {len(route_queue)}个 | 待处理:{pending} 处理中:{processing} 已完成:{done} 失败:{failed}")
    print("=" * 55)


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
    elif cmd == "dispatch":
        if len(sys.argv) < 3:
            print("用法: central_processor.py dispatch <url>")
            sys.exit(1)
        cmd_dispatch(sys.argv[2])
    elif cmd == "command":
        # 【铁律】技能指令入口：技能必须经过中央处理器发指令
        if len(sys.argv) < 3:
            print("用法: central_processor.py command <push> [参数]")
            print("  push --file <path> [--url <url>] [--site <name>]  推送文件指令")
            sys.exit(1)
        sub_cmd = sys.argv[2].lower()
        if sub_cmd == "push":
            cmd_command_push(sys.argv[3:])
        else:
            print(f"未知指令类型: {sub_cmd}")
            sys.exit(1)
    elif cmd == "task":
        # 【全自动】智能任务调度：技能触发时自动获取任务，完成后上报
        if len(sys.argv) < 3:
            print("用法: central_processor.py task <get|done|status> [参数]")
            print("  get [session_id]           获取一个待掘网址任务（标记为处理中）")
            print("  done <url> [--success|--failed] [--retry]  上报任务完成")
            print("  status                     查看队列完整状态")
            sys.exit(1)
        sub_cmd = sys.argv[2].lower()
        if sub_cmd == "get":
            session_id = sys.argv[3] if len(sys.argv) > 3 else ""
            cmd_task_get(session_id)
        elif sub_cmd == "done":
            if len(sys.argv) < 4:
                print("用法: central_processor.py task done <url> [--success|--failed] [--retry]")
                sys.exit(1)
            url = sys.argv[3]
            success = "--failed" not in sys.argv
            session_id = ""
            for i, arg in enumerate(sys.argv):
                if arg == "--session" and i + 1 < len(sys.argv):
                    session_id = sys.argv[i + 1]
            cmd_task_done(url, success, session_id)
        elif sub_cmd == "status":
            cmd_task_status()
        else:
            print(f"未知任务指令: {sub_cmd}")
            sys.exit(1)
    elif cmd == "list":
        cmd_status()
    elif cmd == "run":
        main_loop()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
