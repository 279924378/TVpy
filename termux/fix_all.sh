#!/data/data/com.termux/files/usr/bin/bash
PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$SCRIPTS_DIR" "$LOG_DIR" "$PROJECT_DIR/tvbox_subscribe/py"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 一键修复+启动面板 v5          ║"
echo "║   (含消息监听器，面板实时显示群消息)          ║"
echo "╚══════════════════════════════════════════════╝"

# 1. 自动检测代理
echo "[1/7] 检测代理..."
PROXY_PORT=""
for port in 7890 10809 8080 1080 7891 1087; do
    if curl -s --connect-timeout 2 --max-time 3 -x "http://127.0.0.1:$port" "https://www.google.com" >/dev/null 2>&1; then
        PROXY_PORT="$port"
        break
    fi
done
if [ -n "$PROXY_PORT" ]; then
    export http_proxy="http://127.0.0.1:$PROXY_PORT"
    export https_proxy="http://127.0.0.1:$PROXY_PORT"
    echo "  ✅ 检测到代理: 127.0.0.1:$PROXY_PORT"
else
    echo "  ⚠️  未检测到代理，使用直连"
fi

# 2. 下载修复版同步脚本
echo "[2/7] 更新仓库同步脚本..."
wget -q --timeout=20 "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/repo_sync/repo_sync.sh" -O "$SCRIPTS_DIR/repo_sync.sh" 2>/dev/null
chmod +x "$SCRIPTS_DIR/repo_sync.sh"
echo "  ✅ 同步脚本已更新"

# 3. 下载TUI面板（60秒刷新）
echo "[3/7] 下载机器人终端面板..."
wget -q --timeout=20 "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/tui/tui_panel.py" -O "$SCRIPTS_DIR/tui_panel.py" 2>/dev/null
echo "  ✅ 终端面板已下载（60秒刷新）"

# 4. 下载消息监听器
echo "[4/7] 下载群消息监听器..."
wget -q --timeout=20 "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/panel/chat_monitor.py" -O "$SCRIPTS_DIR/chat_monitor.py" 2>/dev/null
echo "  ✅ 消息监听器已下载"

# 5. 直接启动所有服务（不用watchdog）
echo "[5/7] 启动后台服务..."
pkill -f "watchdog.sh" 2>/dev/null
pkill -f "tg_bot_service.py" 2>/dev/null
pkill -f "chat_monitor.py" 2>/dev/null
pkill -f "push_tasks.sh daemon" 2>/dev/null
pkill -f "repo_sync.sh daemon" 2>/dev/null
sleep 1

cd "$PROJECT_DIR" && nohup python3 scripts/tg_bot_service.py --silent >> "$LOG_DIR/bot.log" 2>&1 &
cd "$SCRIPTS_DIR" && nohup python3 chat_monitor.py >> "$LOG_DIR/chat_monitor.log" 2>&1 &
cd "$SCRIPTS_DIR" && nohup bash push_tasks.sh daemon >> "$LOG_DIR/task_upload.log" 2>&1 &
cd "$SCRIPTS_DIR" && nohup bash repo_sync.sh daemon >> "$LOG_DIR/repo_sync.log" 2>&1 &

# 等待最多60秒让机器人启动
echo "  等待机器人启动（最多60秒）..."
for i in $(seq 1 60); do
    if pgrep -f "tg_bot_service.py" >/dev/null 2>&1; then
        echo "  ✅ 机器人已启动（第${i}秒）"
        break
    fi
    sleep 1
done

# 6. 后台同步
echo "[6/7] 同步最新仓库（后台执行）..."
nohup bash "$SCRIPTS_DIR/repo_sync.sh" sync >> "$LOG_DIR/repo_sync.log" 2>&1 &
echo "  ✅ 同步已在后台执行"

# 7. 状态总览
echo "[7/7] 服务状态:"
echo "  机器人:   $(pgrep -f 'tg_bot_service.py' >/dev/null && echo '✅' || echo '❌')"
echo "  消息监听: $(pgrep -f 'chat_monitor.py' >/dev/null && echo '✅' || echo '❌')"
echo "  任务上传: $(pgrep -f 'push_tasks.sh daemon' >/dev/null && echo '✅' || echo '❌')"
echo "  仓库同步: $(pgrep -f 'repo_sync.sh daemon' >/dev/null && echo '✅' || echo '❌')"

echo ""
echo "✅ 全部完成！进入机器人面板..."
sleep 2
cd "$SCRIPTS_DIR" && python3 tui_panel.py
