#!/data/data/com.termux/files/usr/bin/bash
# 段德机器人 - 增强守护脚本
# 每30秒检查一次，进程挂了自动重启

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$LOG_DIR/bot.pid"

mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 守护脚本启动" >> "$LOG_DIR/watchdog.log"

while true; do
    # 检查机器人进程
    if ! pgrep -f "tg_bot_service.py" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 机器人进程不存在，正在重启..." >> "$LOG_DIR/watchdog.log"
        
        cd "$SCRIPTS_DIR"
        nohup python3 tg_bot_service.py --silent >> "$LOG_DIR/bot.log" 2>&1 &
        echo $! > "$PID_FILE"
        
        sleep 5
        if pgrep -f "tg_bot_service.py" > /dev/null 2>&1; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 机器人重启成功" >> "$LOG_DIR/watchdog.log"
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 机器人重启失败，等待下一轮" >> "$LOG_DIR/watchdog.log"
        fi
    fi
    
    # 检查订阅服务器
    if ! pgrep -f "tvbox_subscribe_server" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 订阅服务器不存在，正在重启..." >> "$LOG_DIR/watchdog.log"
        
        cd "$SCRIPTS_DIR"
        nohup python3 tvbox_subscribe_server.py 8888 >> "$LOG_DIR/tvbox_subscribe.log" 2>&1 &
    fi
    
    sleep 30
done
