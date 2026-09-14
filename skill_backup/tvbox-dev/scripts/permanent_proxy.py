#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常驻代理管理工具（所有会话共享一个xray进程，固定端口10809，智能节点切换永不掉线）

功能：
  - 固定端口10809，所有会话共享，不启动临时xray，永不冲突
  - 智能节点切换：定期检测连通性+网速，挂了或慢了自动切下一个节点
  - 后台监控模式：持续守护，节点故障自动切换，无需人工干预

用法:
  python3 permanent_proxy.py start      # 启动常驻代理（自动选最优节点）
  python3 permanent_proxy.py stop       # 停止常驻代理
  python3 permanent_proxy.py restart    # 重启常驻代理
  python3 permanent_proxy.py status     # 查看状态（当前节点/连通性/网速）
  python3 permanent_proxy.py test       # 测试连通性和网速
  python3 permanent_proxy.py switch     # 手动切换到下一个节点
  python3 permanent_proxy.py monitor    # 后台监控模式（持续检测，故障自动切换）
  python3 permanent_proxy.py nodes      # 列出所有代理节点
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XRAY_BIN = os.path.join(SCRIPT_DIR, "xray")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "xray_permanent_config.json")
PID_FILE = os.path.join(SCRIPT_DIR, "xray_permanent.pid")
STATE_FILE = os.path.join(SCRIPT_DIR, "xray_permanent_state.json")
PROXY_POOL_FILE = os.path.join(SCRIPT_DIR, "..", "assets", "tg_proxy_pool.json")
LOG_FILE = "/tmp/xray_permanent.log"
PORT = 10809

# 监控参数
CHECK_INTERVAL = 30       # 检测间隔（秒）
MAX_FAIL_COUNT = 3        # 连续失败多少次后切换节点
MIN_SPEED_KBPS = 10       # 最低网速阈值（KB/s），低于此值视为慢节点（Telegram推送10KB/s够用）
SPEED_TEST_URL = "https://api.telegram.org"  # 网速测试地址


# ==================== 工具函数 ====================

def load_proxy_pool():
    """加载代理池节点列表"""
    if not os.path.isfile(PROXY_POOL_FILE):
        print(f"[警告] 代理池文件不存在: {PROXY_POOL_FILE}")
        return []
    try:
        with open(PROXY_POOL_FILE, "r", encoding="utf-8") as f:
            pool = json.load(f)
        return pool.get("nodes", [])
    except Exception as e:
        print(f"[警告] 加载代理池失败: {e}")
        return []


def load_state():
    """加载当前状态（当前节点索引等）"""
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_node_idx": 0, "fail_count": 0, "last_check": None}


def save_state(state):
    """保存当前状态"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 保存状态失败: {e}")


def gen_xray_config(node, port):
    """根据节点生成xray配置"""
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "http_in",
            "port": port,
            "listen": "127.0.0.1",
            "protocol": "http",
            "settings": {"timeout": 300}
        }],
        "outbounds": [{
            "tag": "proxy_out",
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node["server"],
                    "port": node["port"],
                    "users": [{
                        "id": node["uuid"],
                        "encryption": "none",
                        "flow": node.get("flow", "xtls-rprx-vision")
                    }]
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": node.get("server_name", node["server"]),
                    "allowInsecure": node.get("insecure", True),
                    "fingerprint": "chrome"
                }
            }
        }]
    }


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


def test_connectivity(timeout=8):
    """测试代理连通性，返回 (是否成功, 延迟秒数)"""
    try:
        start = time.time()
        proxy = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{PORT}",
            "https": f"http://127.0.0.1:{PORT}"
        })
        opener = urllib.request.build_opener(proxy)
        req = urllib.request.Request(SPEED_TEST_URL, method="HEAD")
        r = opener.open(req, timeout=timeout)
        elapsed = time.time() - start
        return r.status == 200, elapsed
    except Exception:
        return False, 999


def test_speed(timeout=10):
    """测试代理网速，返回 (是否成功, 网速KB/s)"""
    try:
        proxy = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{PORT}",
            "https": f"http://127.0.0.1:{PORT}"
        })
        opener = urllib.request.build_opener(proxy)
        start = time.time()
        r = opener.open(SPEED_TEST_URL, timeout=timeout)
        data = r.read()
        elapsed = time.time() - start
        if elapsed > 0:
            speed_kbps = (len(data) / 1024) / elapsed
            return True, speed_kbps
        return False, 0
    except Exception:
        return False, 0


# ==================== 核心命令 ====================

def start_xray_with_node(node):
    """用指定节点启动xray，返回 (proc, config_path)"""
    config = gen_xray_config(node, PORT)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    log = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        [XRAY_BIN, "run", "-c", CONFIG_FILE],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    return proc, CONFIG_FILE


def stop_xray():
    """停止当前xray进程"""
    pid = get_pid()
    if not is_running(pid):
        if os.path.isfile(PID_FILE):
            os.unlink(PID_FILE)
        return
    try:
        os.kill(pid, 15)
        time.sleep(2)
        if is_running(pid):
            os.kill(pid, 9)
            time.sleep(1)
    except Exception:
        pass
    if os.path.isfile(PID_FILE):
        os.unlink(PID_FILE)


def find_best_node(nodes):
    """从节点列表中找到最优节点（连通性+网速测试）"""
    print(f"[智能选点] 测试 {len(nodes)} 个节点，寻找最优...")
    best_node = None
    best_speed = 0
    best_idx = 0

    # 随机打乱顺序，避免每次都从同一个节点开始
    shuffled = list(enumerate(nodes))
    random.shuffle(shuffled)

    for idx, node in shuffled[:5]:  # 最多测试5个节点，避免太慢
        node_name = node.get("name", f"节点{idx+1}")
        print(f"  测试 {node_name}...", end=" ", flush=True)

        # 临时启动xray测试
        config = gen_xray_config(node, PORT + 100)  # 用临时端口测试
        tmp_config = CONFIG_FILE + ".tmp"
        with open(tmp_config, "w") as f:
            json.dump(config, f)

        try:
            proc = subprocess.Popen(
                [XRAY_BIN, "run", "-c", tmp_config],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            time.sleep(2)

            # 测试连通性
            ok, latency = test_connectivity_on_port(PORT + 100, timeout=5)
            speed = 0
            if ok:
                _, speed = test_speed_on_port(PORT + 100, timeout=8)

            proc.terminate()
            proc.wait(timeout=3)
            os.unlink(tmp_config)

            if ok and speed > best_speed:
                best_speed = speed
                best_node = node
                best_idx = idx
                print(f"✅ 延迟{latency:.1f}s 网速{speed:.0f}KB/s")
            elif ok:
                print(f"⚠️  连通但网速{speed:.0f}KB/s（较慢）")
            else:
                print("❌ 连通失败")
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            try:
                os.unlink(tmp_config)
            except Exception:
                pass

    if best_node:
        print(f"[智能选点] 最优节点: {best_node.get('name')} (网速{best_speed:.0f}KB/s)")
    else:
        print("[智能选点] 所有节点均不可用，使用第一个节点")
        best_node = nodes[0] if nodes else None
        best_idx = 0
    return best_node, best_idx


def test_connectivity_on_port(port, timeout=8):
    """在指定端口测试连通性"""
    try:
        start = time.time()
        proxy = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}"
        })
        opener = urllib.request.build_opener(proxy)
        req = urllib.request.Request(SPEED_TEST_URL, method="HEAD")
        r = opener.open(req, timeout=timeout)
        return r.status == 200, time.time() - start
    except Exception:
        return False, 999


def test_speed_on_port(port, timeout=10):
    """在指定端口测试网速"""
    try:
        proxy = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}"
        })
        opener = urllib.request.build_opener(proxy)
        start = time.time()
        r = opener.open(SPEED_TEST_URL, timeout=timeout)
        data = r.read()
        elapsed = time.time() - start
        if elapsed > 0:
            return True, (len(data) / 1024) / elapsed
        return False, 0
    except Exception:
        return False, 0


def switch_to_next_node():
    """切换到下一个节点"""
    nodes = load_proxy_pool()
    if not nodes:
        print("❌ 代理池为空，无法切换")
        return False

    state = load_state()
    current_idx = state.get("current_node_idx", 0)
    next_idx = (current_idx + 1) % len(nodes)
    next_node = nodes[next_idx]

    print(f"[切换节点] {nodes[current_idx].get('name')} → {next_node.get('name')}")

    # 停止当前xray
    stop_xray()
    time.sleep(1)

    # 启动新xray
    proc, _ = start_xray_with_node(next_node)
    time.sleep(3)

    # 测试新节点连通性
    ok, latency = test_connectivity()
    if ok:
        state["current_node_idx"] = next_idx
        state["fail_count"] = 0
        state["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_state(state)
        print(f"✅ 切换成功，新节点连通正常（延迟{latency:.1f}s）")
        return True
    else:
        print("❌ 新节点连通失败，继续切换...")
        state["current_node_idx"] = next_idx
        save_state(state)
        return switch_to_next_node()  # 递归切换，直到找到可用节点


# ==================== 命令实现 ====================

def cmd_start():
    pid = get_pid()
    if is_running(pid):
        ok, _ = test_connectivity()
        if ok:
            state = load_state()
            nodes = load_proxy_pool()
            node_name = nodes[state.get("current_node_idx", 0)].get("name", "?") if nodes else "?"
            print(f"✅ 常驻代理已在运行 (PID: {pid}, 节点: {node_name})")
            return
        else:
            print("⚠️  进程在运行但代理连通失败，重启...")
            cmd_restart()
            return

    nodes = load_proxy_pool()
    if not nodes:
        print("❌ 代理池为空，无法启动")
        sys.exit(1)

    # 智能选最优节点
    best_node, best_idx = find_best_node(nodes)
    if not best_node:
        print("❌ 无可用节点")
        sys.exit(1)

    print(f"🚀 启动常驻代理 (节点: {best_node.get('name')}, 端口: {PORT})...")
    proc, _ = start_xray_with_node(best_node)
    print(f"   PID: {proc.pid}")

    # 等待启动并测试
    for i in range(10):
        time.sleep(1)
        ok, latency = test_connectivity()
        if ok:
            state = load_state()
            state["current_node_idx"] = best_idx
            state["fail_count"] = 0
            state["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_state(state)
            print(f"✅ 常驻代理启动成功，连通正常（延迟{latency:.1f}s）")
            return
    print("❌ 启动失败或连通超时")
    sys.exit(1)


def cmd_stop():
    pid = get_pid()
    if not is_running(pid):
        print("ℹ️  常驻代理未在运行")
        return
    print(f"🛑 停止常驻代理 (PID: {pid})...")
    stop_xray()
    print("✅ 常驻代理已停止")


def cmd_restart():
    cmd_stop()
    time.sleep(1)
    cmd_start()


def cmd_status():
    pid = get_pid()
    running = is_running(pid)
    state = load_state()
    nodes = load_proxy_pool()
    node_name = nodes[state.get("current_node_idx", 0)].get("name", "?") if nodes else "?"

    print("=" * 45)
    print("  常驻代理状态（智能节点切换版）")
    print("=" * 45)
    print(f"  端口: {PORT}")
    print(f"  PID: {pid if pid else '无'}")
    print(f"  进程: {'✅ 运行中' if running else '❌ 未运行'}")
    print(f"  当前节点: {node_name}")
    print(f"  失败计数: {state.get('fail_count', 0)}/{MAX_FAIL_COUNT}")
    print(f"  上次检测: {state.get('last_check', '从未')}")
    if running:
        ok, latency = test_connectivity()
        print(f"  连通性: {'✅ 正常' if ok else '❌ 失败'} (延迟{latency:.1f}s)")
        if ok:
            _, speed = test_speed()
            print(f"  网速: {speed:.0f} KB/s {'✅ 正常' if speed >= MIN_SPEED_KBPS else '⚠️  较慢'}")
    print(f"  节点池: {len(nodes)} 个节点")
    print(f"  监控间隔: {CHECK_INTERVAL}秒 / 故障阈值: {MAX_FAIL_COUNT}次")
    print("=" * 45)


def cmd_test():
    print(f"🔍 测试常驻代理 (127.0.0.1:{PORT})...")
    ok, latency = test_connectivity()
    if ok:
        print(f"✅ 连通正常（延迟{latency:.1f}s）")
        _, speed = test_speed()
        print(f"📊 网速: {speed:.0f} KB/s {'✅ 正常' if speed >= MIN_SPEED_KBPS else '⚠️  较慢（低于阈值'+str(MIN_SPEED_KBPS)+'KB/s）'}")
    else:
        print("❌ 连通失败")
        sys.exit(1)


def cmd_switch():
    print("🔄 手动切换节点...")
    if switch_to_next_node():
        print("✅ 切换完成")
    else:
        print("❌ 切换失败")
        sys.exit(1)


def cmd_nodes():
    nodes = load_proxy_pool()
    state = load_state()
    current_idx = state.get("current_node_idx", 0)
    print(f"代理节点列表（共{len(nodes)}个）：")
    for i, node in enumerate(nodes):
        marker = "⭐ 当前" if i == current_idx else "  "
        print(f"  {marker} {i+1}. {node.get('name')} - {node.get('server')}:{node.get('port')}")


def cmd_monitor():
    """后台监控模式：持续检测连通性和网速，故障自动切换"""
    print(f"👁️  启动常驻代理监控（间隔{CHECK_INTERVAL}秒，故障阈值{MAX_FAIL_COUNT}次）...")
    print("   按 Ctrl+C 停止监控")

    # 确保常驻代理在运行
    if not is_running(get_pid()):
        print("   常驻代理未运行，先启动...")
        cmd_start()

    state = load_state()
    fail_count = state.get("fail_count", 0)

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            # 检测连通性
            ok, latency = test_connectivity()
            speed = 0
            if ok:
                _, speed = test_speed()

            state["last_check"] = now

            if ok and speed >= MIN_SPEED_KBPS:
                # 正常
                fail_count = 0
                state["fail_count"] = 0
                save_state(state)
                print(f"[{now}] ✅ 正常 (延迟{latency:.1f}s, 网速{speed:.0f}KB/s)")
            elif ok and speed < MIN_SPEED_KBPS:
                # 连通但网速慢
                fail_count += 1
                state["fail_count"] = fail_count
                save_state(state)
                print(f"[{now}] ⚠️  网速慢 ({speed:.0f}KB/s < {MIN_SPEED_KBPS}KB/s) 失败计数: {fail_count}/{MAX_FAIL_COUNT}")
                if fail_count >= MAX_FAIL_COUNT:
                    print(f"[{now}] 🔄 网速持续过慢，自动切换节点...")
                    if switch_to_next_node():
                        fail_count = 0
                        state = load_state()
            else:
                # 连通失败
                fail_count += 1
                state["fail_count"] = fail_count
                save_state(state)
                print(f"[{now}] ❌ 连通失败 失败计数: {fail_count}/{MAX_FAIL_COUNT}")
                if fail_count >= MAX_FAIL_COUNT:
                    print(f"[{now}] 🔄 连续失败，自动切换节点...")
                    if switch_to_next_node():
                        fail_count = 0
                        state = load_state()
    except KeyboardInterrupt:
        print("\n⏹️  监控已停止")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "test": cmd_test,
        "switch": cmd_switch,
        "nodes": cmd_nodes,
        "monitor": cmd_monitor,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"❌ 未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
