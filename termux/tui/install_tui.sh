#!/data/data/com.termux/files/usr/bin/bash
# 一键安装段德机器人终端面板

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/tui"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装终端面板                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载TUI面板
echo "[1/4] 下载终端面板..."
wget -q "$GITHUB_RAW/tui_panel.py" -O "$SCRIPTS_DIR/tui_panel.py"
if [ -f "$SCRIPTS_DIR/tui_panel.py" ]; then
    echo "  ✅ tui_panel.py 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 2. 下载启动脚本
echo ""
echo "[2/4] 下载启动脚本..."
wget -q "$GITHUB_RAW/start_tui.sh" -O "$PROJECT_DIR/start_tui.sh"
chmod +x "$PROJECT_DIR/start_tui.sh"
echo "  ✅ start_tui.sh 下载完成"

# 3. 更新开机自启脚本
echo ""
echo "[3/4] 更新开机自启脚本..."
wget -q "$GITHUB_RAW/boot" -O ~/.termux/boot/duande_bot
chmod +x ~/.termux/boot/duande_bot
echo "  ✅ 开机自启脚本已更新（开机自动进入面板）"

# 4. 启动面板
echo ""
echo "[4/4] 启动终端面板..."
echo "  （面板启动后按 Ctrl+C 退出，后台服务仍运行）"
sleep 2
bash "$PROJECT_DIR/start_tui.sh"
