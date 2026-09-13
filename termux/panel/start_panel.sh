#!/data/data/com.termux/files/usr/bin/bash
# 启动机器人面板 + 消息监听器

PROJECT_DIR="$HOME/段德机器人项目"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 启动管理面板                  ║"
echo "╚══════════════════════════════════════════════╝"

# 杀掉旧进程
pkill -f "bot_panel.py" 2>/dev/null && echo "  旧面板已停止" || true
pkill -f "chat_monitor.py" 2>/dev/null && echo "  旧监听器已停止" || true
sleep 1

# 启动消息监听器
echo ""
echo "[1/2] 启动群消息监听器..."
cd "$PROJECT_DIR/scripts"
nohup python3 chat_monitor.py >> "$LOG_DIR/chat_monitor.log" 2>&1 &
sleep 2
if pgrep -f "chat_monitor.py" > /dev/null; then
    echo "  ✅ 消息监听器已启动"
else
    echo "  ⚠️  监听器启动失败，查看日志: tail -f $LOG_DIR/chat_monitor.log"
fi

# 启动面板
echo ""
echo "[2/2] 启动Web管理面板..."
cd "$PROJECT_DIR/scripts"
nohup python3 bot_panel.py >> "$LOG_DIR/panel.log" 2>&1 &
sleep 2
if pgrep -f "bot_panel.py" > /dev/null; then
    echo "  ✅ 面板已启动"
else
    echo "  ⚠️  面板启动失败，查看日志: tail -f $LOG_DIR/panel.log"
fi

# 获取IP
IP=$(ifconfig wlan0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "你的手机IP")
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   面板地址: http://$IP:8080                 ║"
echo "║                                              ║"
echo "║   查看面板日志:                               ║"
echo "║     tail -f $LOG_DIR/panel.log              ║"
echo "║   查看消息监听日志:                           ║"
echo "║     tail -f $LOG_DIR/chat_monitor.log       ║"
echo "║                                              ║"
echo "║   停止面板: pkill -f bot_panel.py           ║"
echo "╚══════════════════════════════════════════════╝"
