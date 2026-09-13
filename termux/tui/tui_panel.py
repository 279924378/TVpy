#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 终端实时面板 (TUI)
# 在Termux终端内全屏显示，开机自动启动
# ============================================================

import json, os, sys, time, sqlite3, subprocess, signal
from datetime import datetime

# 配置
PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
DB_FILE = os.path.join(SCRIPTS_DIR, "user_points.db")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
PENDING_FILE = os.path.join(SCRIPTS_DIR, "tg_pending_urls.json")
REFRESH_INTERVAL = 60  # 刷新间隔秒

# ANSI颜色
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_DARK = "\033[48;5;236m"

def get_terminal_size():
    try:
        result = subprocess.run(["stty", "size"], capture_output=True, text=True)
        rows, cols = map(int, result.stdout.strip().split())
        return rows, cols
    except:
        return 24, 80

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def move_cursor(row, col):
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()

def get_bot_status():
    try:
        r = subprocess.run(["pgrep", "-f", "tg_bot_service.py"], capture_output=True, text=True)
        bot = bool(r.stdout.strip())
    except: bot = False
    try:
        r = subprocess.run(["pgrep", "-f", "watchdog.sh"], capture_output=True, text=True)
        wd = bool(r.stdout.strip())
    except: wd = False
    try:
        r = subprocess.run(["pgrep", "-f", "chat_monitor.py"], capture_output=True, text=True)
        mon = bool(r.stdout.strip())
    except: mon = False
    return bot, wd, mon

def get_chat_messages(limit=30):
    msgs = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    msgs = data[-limit:]
        except: pass
    return msgs

def get_points_ranking(limit=10):
    ranking = []
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT nickname, points FROM user_points ORDER BY points DESC LIMIT ?", (limit,))
            for row in cur.fetchall():
                ranking.append((row[0] or "未知", row[1] or 0))
            conn.close()
        except: pass
    return ranking

def get_pending_tasks():
    tasks = []
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    tasks = [t for t in data if t.get("status") == "pending"]
        except: pass
    return tasks

def get_system_info():
    info = {}
    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True)
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            p = lines[1].split()
            info["mem"] = f"{p[2]}/{p[1]}"
    except: info["mem"] = "?"
    try:
        r = subprocess.run(["df", "-h", "/data"], capture_output=True, text=True)
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            p = lines[1].split()
            info["disk"] = f"{p[2]}/{p[1]} ({p[4]})"
    except: info["disk"] = "?"
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True)
        info["uptime"] = r.stdout.strip().split("up")[1].split(",")[0].strip() if "up" in r.stdout else "?"
    except: info["uptime"] = "?"
    return info

def draw_border(rows, cols):
    """绘制面板边框和布局"""
    # 顶部标题栏
    move_cursor(1, 1)
    sys.stdout.write(f"{C.BG_DARK}{C.BOLD}{C.RED} ⚱️ 段德机器人控制台 {C.RESET}")
    move_cursor(1, cols - 20)
    sys.stdout.write(f"{C.GRAY}{datetime.now().strftime('%H:%M:%S')}{C.RESET}")
    
    # 状态栏
    move_cursor(2, 1)
    bot, wd, mon = get_bot_status()
    status_str = f"  🤖 机器人:{C.GREEN if bot else C.RED}{'●在线' if bot else '○离线'}{C.RESET}  "
    status_str += f"🛡️ 守护:{C.GREEN if wd else C.RED}{'●正常' if wd else '○异常'}{C.RESET}  "
    status_str += f"📡 监听:{C.GREEN if mon else C.RED}{'●运行' if mon else '○停止'}{C.RESET}"
    sys.stdout.write(status_str)
    
    # 分隔线
    move_cursor(3, 1)
    sys.stdout.write(C.GRAY + "─" * cols + C.RESET)
    
    return bot, wd, mon

def draw_chat_panel(start_row, end_row, cols):
    """左侧：群消息面板"""
    width = cols // 2 - 1
    move_cursor(start_row, 1)
    sys.stdout.write(f"{C.BOLD}{C.CYAN}💬 最新群消息{C.RESET}")
    
    msgs = get_chat_messages(limit=end_row - start_row - 1)
    msgs.reverse()  # 最新在上面
    
    for i, msg in enumerate(msgs[:end_row - start_row - 1]):
        row = start_row + 1 + i
        if row >= end_row: break
        move_cursor(row, 1)
        sender = msg.get("sender", "?")[:10]
        time_str = msg.get("time", "")
        content = msg.get("content", "")[:width - 15]
        sys.stdout.write(f"{C.YELLOW}{sender}{C.RESET} {C.GRAY}{time_str}{C.RESET}")
        move_cursor(row + 1, 3) if row + 1 < end_row else None
        if row + 1 < end_row:
            sys.stdout.write(f"  {content}")
    
    # 右侧分隔线
    for r in range(start_row, end_row):
        move_cursor(r, cols // 2)
        sys.stdout.write(C.GRAY + "│" + C.RESET)

def draw_right_panel(start_row, end_row, cols):
    """右侧：积分+任务+系统"""
    col_start = cols // 2 + 2
    width = cols - col_start - 1
    
    # 积分排行
    move_cursor(start_row, col_start)
    sys.stdout.write(f"{C.BOLD}{C.YELLOW}🏆 积分排行{C.RESET}")
    ranking = get_points_ranking(limit=5)
    for i, (name, points) in enumerate(ranking):
        row = start_row + 1 + i
        if row >= start_row + 7: break
        move_cursor(row, col_start)
        medal = ["🥇","🥈","🥉","4️⃣","5️⃣"][i] if i < 5 else f"{i+1}."
        sys.stdout.write(f"{medal} {name[:12]:<12} {C.GREEN}{points}分{C.RESET}")
    
    # 任务队列
    task_start = start_row + 8
    move_cursor(task_start, col_start)
    sys.stdout.write(f"{C.BOLD}{C.MAGENTA}📋 待处理任务{C.RESET}")
    tasks = get_pending_tasks()
    if not tasks:
        move_cursor(task_start + 1, col_start)
        sys.stdout.write(f"{C.GRAY}  队列为空{C.RESET}")
    else:
        for i, t in enumerate(tasks[:3]):
            row = task_start + 1 + i
            if row >= end_row: break
            move_cursor(row, col_start)
            url = t.get("url", "")[:width - 5]
            sys.stdout.write(f"  {C.BLUE}{url}{C.RESET}")
    
    # 系统信息
    sys_start = end_row - 4
    move_cursor(sys_start, col_start)
    sys.stdout.write(f"{C.BOLD}{C.GREEN}📊 系统信息{C.RESET}")
    info = get_system_info()
    move_cursor(sys_start + 1, col_start)
    sys.stdout.write(f"  内存: {info.get('mem','?')}")
    move_cursor(sys_start + 2, col_start)
    sys.stdout.write(f"  存储: {info.get('disk','?')}")

def draw_bottom_bar(rows, cols):
    """底部状态栏"""
    move_cursor(rows, 1)
    sys.stdout.write(f"{C.BG_DARK}{C.GRAY} 按 Ctrl+C 退出面板 | 每{REFRESH_INTERVAL}秒自动刷新 | 段德机器人 v2.0 {C.RESET}")

def main():
    # 处理退出
    def signal_handler(sig, frame):
        clear_screen()
        sys.stdout.write(f"{C.GREEN}👋 面板已退出{C.RESET}\n")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 隐藏光标
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            rows, cols = get_terminal_size()
            clear_screen()
            
            # 绘制各区域
            draw_border(rows, cols)
            draw_chat_panel(4, rows - 1, cols)
            draw_right_panel(4, rows - 1, cols)
            draw_bottom_bar(rows, cols)
            
            sys.stdout.flush()
            time.sleep(REFRESH_INTERVAL)
    
    except KeyboardInterrupt:
        pass
    finally:
        # 恢复光标
        sys.stdout.write("\033[?25h")
        clear_screen()
        sys.stdout.write(f"{C.GREEN}👋 段德机器人面板已退出{C.RESET}\n")

if __name__ == "__main__":
    main()
