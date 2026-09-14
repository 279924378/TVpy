#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话心跳工具——豆包会话触发技能时调用此脚本发送心跳
中央处理器收到心跳后：
  - 容器存在：刷新存活时间（30分钟无心跳才关闭）
  - 容器已销毁：自动唤醒重建容器（旧会话恢复）

用法:
  python3 session_heartbeat.py <session_id>          # 发送心跳
  python3 session_heartbeat.py <session_id> <url>    # 发送心跳并关联网址
  python3 session_heartbeat.py --status               # 查看当前会话容器状态
"""
import os
import sys
import json
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT_FILE = os.path.join(SCRIPT_DIR, "session_heartbeat.json")
STATE_FILE = os.path.join(SCRIPT_DIR, "central_state.json")


def send_heartbeat(session_id, url=""):
    """发送会话心跳"""
    try:
        if os.path.isfile(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
                heartbeats = json.load(f)
        else:
            heartbeats = {}
    except Exception:
        heartbeats = {}

    heartbeats[session_id] = {
        "url": url,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
        json.dump(heartbeats, f, ensure_ascii=False, indent=2)

    print(f"💓 会话心跳已发送: {session_id}")
    if url:
        print(f"   关联网址: {url}")
    print(f"   中央处理器将在5秒内处理（刷新或唤醒容器）")


def check_status(session_id=None):
    """查看会话容器状态"""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        containers = state.get("containers", {})
    except Exception:
        containers = {}

    print("=" * 50)
    print("  📦 会话容器状态")
    print("=" * 50)

    if not containers:
        print("  （无运行中容器）")
        print("=" * 50)
        return

    for cid, c in containers.items():
        if session_id and c.get("session_id") != session_id and cid != session_id:
            continue
        print(f"  📦 {cid}")
        print(f"     会话ID: {c.get('session_id', '未关联')}")
        print(f"     网址: {c.get('url', '')[:50]}")
        print(f"     代理端口: {c.get('proxy_port')} ({c.get('proxy_node')})")
        print(f"     状态: {c.get('status')}")
        print(f"     创建时间: {c.get('created_at')}")
        print(f"     最后心跳: {c.get('last_heartbeat', '从未')}")
        print()

    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--status":
        session_id = sys.argv[2] if len(sys.argv) > 2 else None
        check_status(session_id)
        return

    session_id = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else ""
    send_heartbeat(session_id, url)

    # 等待中央处理器处理，然后显示状态
    time.sleep(6)
    check_status(session_id)


if __name__ == "__main__":
    main()
