#!/data/data/com.termux/files/usr/bin/bash
# 配置Termux打开自动进机器人面板 v2（不依赖外部脚本）
PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
BASHRC="$HOME/.bashrc"

echo "配置Termux开机自动进面板 v2..."

# 先确保必要文件存在
if [ ! -f "$SCRIPTS_DIR/tui_panel.py" ]; then
    echo "⚠️  tui_panel.py不存在，先下载..."
    wget -q "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/tui/tui_panel.py" -O "$SCRIPTS_DIR/tui_panel.py"
fi

if [ ! -f "$SCRIPTS_DIR/chat_monitor.py" ]; then
    echo "⚠️  chat_monitor.py不存在，先下载..."
    wget -q "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/panel/chat_monitor.py" -O "$SCRIPTS_DIR/chat_monitor.py"
fi

# 备份原bashrc
if [ -f "$BASHRC" ]; then
    cp "$BASHRC" "$BASHRC.bak.$(date +%s)"
fi

# 移除旧的自动启动配置
sed -i '/# ===== 段德机器人自动启动 =====/,/# ===== 段德机器人自动启动结束 =====/d' "$BASHRC"

# 添加新的自动启动配置（直接写命令，不依赖外部脚本）
cat >> "$BASHRC" << 'AUTOEOF'

# ===== 段德机器人自动启动 =====
# 只在交互式shell启动
if [[ $- == *i* ]] && [ -f "$HOME/段德机器人项目/scripts/tui_panel.py" ]; then
    echo ""
    echo "🚀 段德机器人自动启动中..."
    
    # 启动机器人（如果没在运行）
    if ! pgrep -f "tg_bot_service.py" >/dev/null 2>&1; then
        cd "$HOME/段德机器人项目" && nohup python3 scripts/tg_bot_service.py --silent >> logs/bot.log 2>&1 &
        echo "  ✅ 机器人已启动"
    else
        echo "  ✅ 机器人已在运行"
    fi
    
    # 启动消息监听器（如果没在运行）
    if ! pgrep -f "chat_monitor.py" >/dev/null 2>&1; then
        cd "$HOME/段德机器人项目/scripts" && nohup python3 chat_monitor.py >> ../logs/chat_monitor.log 2>&1 &
        echo "  ✅ 消息监听器已启动"
    fi
    
    # 启动任务上传和仓库同步
    if ! pgrep -f "push_tasks.sh" >/dev/null 2>&1; then
        cd "$HOME/段德机器人项目/scripts" && nohup bash push_tasks.sh daemon >> ../logs/task_upload.log 2>&1 &
    fi
    if ! pgrep -f "repo_sync.sh" >/dev/null 2>&1; then
        cd "$HOME/段德机器人项目/scripts" && nohup bash repo_sync.sh daemon >> ../logs/repo_sync.log 2>&1 &
    fi
    
    # 等2秒让服务启动
    sleep 2
    
    # 进入面板
    echo "  进入机器人面板..."
    echo ""
    cd "$HOME/段德机器人项目/scripts" && python3 tui_panel.py
fi
# ===== 段德机器人自动启动结束 =====
AUTOEOF

echo ""
echo "✅ 配置完成！"
echo "下次打开Termux会自动启动机器人并进面板"
echo "按Ctrl+C可退出面板执行其他命令"
echo "原.bashrc已备份"
