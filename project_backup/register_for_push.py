#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件落地登记工具——AI生成成品后调用此脚本登记，Bot后台监控自动推送到Telegram群
无需AI手动调用tg_pusher.py，登记后Bot自动推送，避免遗漏。

用法:
  python3 register_for_push.py /path/to/色花堂视频.py
  python3 register_for_push.py /path/to/色花堂视频.py /path/to/色花堂视频_小程序.zip
  python3 register_for_push.py --site "色花堂视频" /path/to/file1.py /path/to/file2.zip
"""
import os
import sys
import json
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PUSH_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_push_queue.json")


def load_queue():
    if os.path.isfile(PUSH_QUEUE_FILE):
        try:
            with open(PUSH_QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_queue(queue):
    with open(PUSH_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    site_name = None
    url = None
    files = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--site" and i + 1 < len(args):
            site_name = args[i + 1]
            i += 2
        elif args[i] == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        else:
            files.append(args[i])
            i += 1

    if not files:
        print("❌ 未指定文件路径")
        sys.exit(1)

    queue = load_queue()
    added = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for fp in files:
        abs_path = os.path.abspath(fp)
        if not os.path.isfile(abs_path):
            print(f"⚠️  文件不存在，跳过: {abs_path}")
            continue

        # 去重：同路径未推送的不重复登记
        if any(item["file_path"] == abs_path and item["status"] == "pending" for item in queue):
            print(f"⏭️  已在推送队列中: {os.path.basename(abs_path)}")
            continue

        file_size = os.path.getsize(abs_path)
        queue.append({
            "file_path": abs_path,
            "file_name": os.path.basename(abs_path),
            "file_size": file_size,
            "site_name": site_name or "",
            "url": url or "",
            "register_time": now,
            "status": "pending",
            "retry_count": 0,
        })
        print(f"✅ 登记推送: {os.path.basename(abs_path)} ({file_size} bytes)")
        if url:
            print(f"   关联网址: {url}（推送成功后自动标记为已爬）")
        added += 1

    save_queue(queue)
    pending_count = len([x for x in queue if x["status"] == "pending"])
    print(f"\n登记完成: 新增{added}个，队列共{pending_count}个待推送")
    print("Bot后台监控将自动推送到Telegram群，无需手动操作。")


if __name__ == "__main__":
    main()
