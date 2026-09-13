#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 终端面板 v6（curses局部更新，不闪烁）
# 去掉周期性刷新，有新消息才更新，显示群+私聊
# ============================================================

import json, os, sys, time, subprocess, threading, curses
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")

messages = []
last_mtime = 0
need_refresh = True
bot_online = False
mon_online = False

def get_bot_status():
    global bot_online, mon_online
    try:
        r = subprocess.run(["pgrep", "-f", "tg_bot_service.py"], capture_output=True, text=True)
        bot_online = bool(r.stdout.strip())
    except: bot_online = False
    try:
        r = subprocess.run(["pgrep", "-f", "chat_monitor.py"], capture_output=True, text=True)
        mon_online = bool(r.stdout.strip())
    except: mon_online = False

def load_messages():
    global messages, last_mtime, need_refresh
    try:
        mtime = os.path.getmtime(CHAT_LOG_FILE)
        if mtime != last_mtime:
            last_mtime = mtime
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    messages = data[-200:]
                    need_refresh = True
    except:
        pass

def file_watcher():
    """后台线程监控文件变化"""
    global need_refresh
    while True:
        load_messages()
        get_bot_status()
        time.sleep(1)

def draw(stdscr):
    global need_refresh
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)
    
    # 启动文件监控线程
    watcher = threading.Thread(target=file_watcher, daemon=True)
    watcher.start()
    
    while True:
        try:
            key = stdscr.getch()
            if key == ord('q') or key == 3:  # q或Ctrl+C
                break
        except:
            pass
        
        if need_refresh:
            need_refresh = False
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            
            # 顶部标题栏
            title = f"⚱️ 段德机器人控制台  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            stdscr.addstr(0, 0, title[:w-1], curses.color_pair(1) | curses.A_BOLD)
            
            # 状态栏
            bot_str = f"🤖机器人:{'●在线' if bot_online else '○离线'}"
            mon_str = f"📡监听:{'●运行' if mon_online else '○停止'}"
            status = f"  {bot_str}  {mon_str}  共{len(messages)}条消息"
            stdscr.addstr(1, 0, status[:w-1], curses.color_pair(2))
            
            # 分隔线
            stdscr.addstr(2, 0, "─" * (w-1), curses.color_pair(3))
            
            # 消息标题
            stdscr.addstr(3, 0, "💬 最新消息（群+私聊）", curses.color_pair(4) | curses.A_BOLD)
            
            # 显示消息（最新在上面）
            row = 4
            msgs = list(reversed(messages))
            
            for msg in msgs:
                if row >= h - 1:
                    break
                
                sender = msg.get("sender", "?")[:12]
                time_str = msg.get("time", "")
                source = msg.get("source", "")
                content = msg.get("content", "")
                
                # 第一行：来源 + 时间 + 用户名
                header = f"[{time_str}] {source} {sender}"
                try:
                    stdscr.addstr(row, 0, header[:w-1], curses.color_pair(5))
                except:
                    pass
                row += 1
                
                # 内容（自动换行）
                content_w = w - 4
                while content and row < h - 1:
                    line = content[:content_w]
                    content = content[content_w:]
                    try:
                        stdscr.addstr(row, 2, line, curses.color_pair(6))
                    except:
                        pass
                    row += 1
                
                row += 1  # 消息间空行
            
            # 如果没有消息
            if row == 4:
                try:
                    stdscr.addstr(5, 2, "暂无消息，等待中...", curses.color_pair(3))
                except:
                    pass
            
            # 底部状态栏
            bottom = " 按 q 退出 | 有新消息自动更新 | 段德机器人 v6.0 "
            try:
                stdscr.addstr(h-1, 0, bottom[:w-1], curses.color_pair(1) | curses.A_REVERSE)
            except:
                pass
            
            stdscr.refresh()
        
        time.sleep(0.1)

def main():
    # 初始化颜色
    def init_colors(stdscr):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)      # 标题
        curses.init_pair(2, curses.COLOR_GREEN, -1)    # 状态
        curses.init_pair(3, curses.COLOR_WHITE, -1)    # 分隔线/普通
        curses.init_pair(4, curses.COLOR_CYAN, -1)     # 消息标题
        curses.init_pair(5, curses.COLOR_YELLOW, -1)   # 消息头
        curses.init_pair(6, curses.COLOR_WHITE, -1)    # 消息内容
    
    try:
        stdscr = curses.initscr()
        init_colors(stdscr)
        draw(stdscr)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            curses.endwin()
        except:
            pass
        print("👋 段德机器人面板已退出")

if __name__ == "__main__":
    main()
