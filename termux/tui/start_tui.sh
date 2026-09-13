#!/data/data/com.termux/files/usr/bin/bash
# 启动段德机器人终端面板
# 先确保后台服务都在运行，然后启动前台TUI面板

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "⚱️ 段德机器人终端面板启动中..."

# 1. 确保守护进程在运行
if ! pgrep -f "watchdog.sh" > /dev/null 2>&1; then
    echo "  启动守护进程..."
    cd "$PROJECT_DIR"
    nohup bash scripts/watchdog.sh >> logs/watchdog.log 2>&1 &
    sleep 2
fi

# 2. 确保消息监听器在运行
if ! pgrep -f "chat_monitor.py" > /dev/null 2>&1; then
    echo "  启动消息监听器..."
    cd "$SCRIPTS_DIR"
    nohup python3 chat_monitor.py >> "$LOG_DIR/chat_monitor.log" 2>&1 &
    sleep 2
fi

# 3. 启动前台TUI面板
echo "  启动终端面板..."
cd "$SCRIPTS_DIR"
python3 tui_panel.py

# 面板退出后提示
echo ""
echo "👋 面板已退出，后台服务仍在运行"
echo "   重新打开面板: bash ~/段德机器人项目/start_tui.sh"
