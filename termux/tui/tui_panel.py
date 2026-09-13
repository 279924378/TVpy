#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - 终端实时面板 v5（纯群消息版）
# 去掉积分排行和系统信息，群消息占满全屏
# ============================================================

import json, os, sys, time, subprocess, signal
from datetime import datetime

PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
REFRESH_INTERVAL = 60

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

def get_bot_status():
    try:
        r = subprocess.run(["pgrep", "-f", "tg_bot_service.py"], capture_output=True, text=True)
        bot = bool(r.stdout.strip())
    except: bot = False
    try:
        r = subprocess.run(["pgrep", "-f", "chat_monitor.py"], capture_output=True, text=True)
        mon = bool(r.stdout.strip())
    except: mon = False
    return bot, mon

def get_chat_messages(limit=100):
    msgs = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    msgs = data[-limit:]
        except: pass
    return msgs

def wrap_text(text, width):
    """简单的文本换行"""
    lines = []
    while len(text) > width:
        lines.append(text[:width])
        text = text[width:]
    if text:
        lines.append(text)
    return lines

def draw_panel():
    rows, cols = get_terminal_size()
    clear_screen()
    
    # 顶部标题栏
    move_cursor(1, 1)
    sys.stdout.write(f"{C.BG_DARK}{C.BOLD}{C.RED} ⚱️ 段德机器人控制台 {C.RESET}")
    move_cursor(1, cols - 22)
    sys.stdout.write(f"{C.GRAY}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.RESET}")
    
    # 状态栏
    move_cursor(2, 1)
    bot, mon = get_bot_status()
    status = f"  🤖 机器人:{C.GREEN if bot else C.RED}{'●在线' if bot else '○离线'}{C.RESET}  "
    status += f"📡 监听:{C.GREEN if mon else C.RED}{'●运行' if mon else '○停止'}{C.RESET}"
    sys.stdout.write(status)
    
    # 分隔线
    move_cursor(3, 1)
    sys.stdout.write(C.GRAY + "─" * cols + C.RESET)
    
    # 群消息标题
    move_cursor(4, 1)
    sys.stdout.write(f"{C.BOLD}{C.CYAN}💬 最新群消息{C.RESET}")
    
    # 获取消息，最新在上面
    msgs = get_chat_messages(limit=200)
    msgs.reverse()
    
    # 绘制消息（从第5行开始，到底部倒数第2行）
    current_row = 5
    max_row = rows - 1
    
    for msg in msgs:
        if current_row >= max_row:
            break
        
        sender = msg.get("sender", "?")[:12]
        time_str = msg.get("time", "")
        content = msg.get("content", "")
        
        # 第一行：时间 + 用户名
        if current_row < max_row:
            move_cursor(current_row, 1)
            sys.stdout.write(f"{C.GRAY}[{time_str}]{C.RESET} {C.YELLOW}{sender}{C.RESET}")
            current_row += 1
        
        # 内容行（缩进2格，自动换行）
        content_lines = wrap_text(content, cols - 4)
        for line in content_lines:
            if current_row >= max_row:
                break
            move_cursor(current_row, 3)
            sys.stdout.write(f"{C.WHITE}{line}{C.RESET}")
            current_row += 1
        
        # 消息间空一行
        current_row += 1
    
    # 如果没有消息
    if current_row == 5:
        move_cursor(6, 1)
        sys.stdout.write(f"{C.GRAY}  暂无消息，等待群消息...{C.RESET}")
    
    # 底部状态栏
    move_cursor(rows, 1)
    sys.stdout.write(f"{C.BG_DARK}{C.GRAY} 按 Ctrl+C 退出 | 每{REFRESH_INTERVAL}秒刷新 | 段德机器人 v5.0 {C.RESET}")
    
    sys.stdout.flush()

def main():
    def signal_handler(sig, frame):
        clear_screen()
        sys.stdout.write(f"{C.GREEN}👋 面板已退出{C.RESET}\n")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            draw_panel()
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        clear_screen()
        sys.stdout.write(f"{C.GREEN}👋 段德机器人面板已退出{C.RESET}\n")

if __name__ == "__main__":
    main()
