#!/data/data/com.termux/files/usr/bin/bash
# 段德机器人 Termux专用启动脚本（不用watchdog，直接启动）
PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "启动段德机器人..."

# 杀掉旧进程
pkill -f "watchdog.sh" 2>/dev/null
pkill -f "tg_bot_service.py" 2>/dev/null
pkill -f "push_tasks.sh daemon" 2>/dev/null
pkill -f "repo_sync.sh daemon" 2>/dev/null
pkill -f "xray run" 2>/dev/null
sleep 1

# 1. 直接启动机器人（不用watchdog）
cd "$PROJECT_DIR" && nohup python3 scripts/tg_bot_service.py --silent >> "$LOG_DIR/bot.log" 2>&1 &
echo "  ✅ 机器人已启动"

# 2. 启动任务上传桥
cd "$SCRIPTS_DIR" && nohup bash push_tasks.sh daemon >> "$LOG_DIR/task_upload.log" 2>&1 &
echo "  ✅ 任务上传已启动"

# 3. 启动仓库同步
cd "$SCRIPTS_DIR" && nohup bash repo_sync.sh daemon >> "$LOG_DIR/repo_sync.log" 2>&1 &
echo "  ✅ 仓库同步已启动"

# 等待机器人启动
sleep 5
if pgrep -f "tg_bot_service.py" >/dev/null 2>&1; then
    echo "✅ 所有服务启动成功！"
else
    echo "⚠️  机器人启动较慢，查看日志: tail -f $LOG_DIR/bot.log"
fi
