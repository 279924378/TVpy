#!/data/data/com.termux/files/usr/bin/bash
# 一键安装机器人管理面板

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/panel"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装管理面板                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载面板脚本
echo "[1/4] 下载面板脚本..."
wget -q "$GITHUB_RAW/bot_panel.py" -O "$SCRIPTS_DIR/bot_panel.py"
if [ -f "$SCRIPTS_DIR/bot_panel.py" ]; then
    echo "  ✅ bot_panel.py 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 2. 下载消息监听器
echo ""
echo "[2/4] 下载消息监听器..."
wget -q "$GITHUB_RAW/chat_monitor.py" -O "$SCRIPTS_DIR/chat_monitor.py"
if [ -f "$SCRIPTS_DIR/chat_monitor.py" ]; then
    echo "  ✅ chat_monitor.py 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 3. 下载启动脚本
echo ""
echo "[3/4] 下载启动脚本..."
wget -q "$GITHUB_RAW/start_panel.sh" -O "$PROJECT_DIR/start_panel.sh"
chmod +x "$PROJECT_DIR/start_panel.sh"
echo "  ✅ start_panel.sh 下载完成"

# 4. 启动
echo ""
echo "[4/4] 启动面板..."
bash "$PROJECT_DIR/start_panel.sh"

echo ""
echo "✅ 面板安装完成！以后启动执行: bash ~/段德机器人项目/start_panel.sh"
