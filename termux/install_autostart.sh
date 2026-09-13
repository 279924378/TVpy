#!/data/data/com.termux/files/usr/bin/bash
# 段德机器人 - 一键安装开机自启+守护进程（修复版）

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装开机自启+守护进程        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 0. 创建必要目录
echo "[0/5] 创建必要目录..."
mkdir -p "$LOG_DIR"
mkdir -p "$HOME/.termux/boot"
echo "  ✅ 目录创建完成"

# 1. 下载boot脚本
echo ""
echo "[1/5] 下载开机自启脚本..."
wget -q "$GITHUB_RAW/boot" -O "$HOME/.termux/boot/duande_bot"
if [ -f "$HOME/.termux/boot/duande_bot" ]; then
    chmod +x "$HOME/.termux/boot/duande_bot"
    echo "  ✅ 开机自启脚本已安装: ~/.termux/boot/duande_bot"
else
    echo "  ❌ 下载失败，请检查网络"
fi

# 2. 下载watchdog守护脚本
echo ""
echo "[2/5] 下载守护脚本..."
wget -q "$GITHUB_RAW/watchdog.sh" -O "$SCRIPTS_DIR/watchdog.sh"
if [ -f "$SCRIPTS_DIR/watchdog.sh" ]; then
    chmod +x "$SCRIPTS_DIR/watchdog.sh"
    echo "  ✅ 守护脚本已安装: $SCRIPTS_DIR/watchdog.sh"
else
    echo "  ❌ 下载失败"
fi

# 3. 杀掉旧进程
echo ""
echo "[3/5] 清理旧进程..."
pkill -f "watchdog.sh" 2>/dev/null && echo "  旧守护进程已停止" || echo "  无旧进程"
sleep 1

# 4. 启动守护进程
echo ""
echo "[4/5] 启动守护进程..."
cd "$PROJECT_DIR"
nohup bash "$SCRIPTS_DIR/watchdog.sh" >> "$LOG_DIR/watchdog.log" 2>&1 &
sleep 3
if pgrep -f "watchdog.sh" > /dev/null 2>&1; then
    echo "  ✅ 守护进程已启动（PID: $(pgrep -f watchdog.sh | head -1)）"
else
    echo "  ⚠️  启动失败，查看日志: tail -f $LOG_DIR/watchdog.log"
fi

# 5. 验证
echo ""
echo "[5/5] 验证安装..."
echo "  开机自启脚本: $([ -f "$HOME/.termux/boot/duande_bot" ] && echo '✅' || echo '❌')"
echo "  守护脚本: $([ -f "$SCRIPTS_DIR/watchdog.sh" ] && echo '✅' || echo '❌')"
echo "  守护进程: $(pgrep -f watchdog.sh > /dev/null 2>&1 && echo '✅ 运行中' || echo '❌ 未运行')"
echo "  日志目录: $([ -d "$LOG_DIR" ] && echo '✅' || echo '❌')"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   安装完成！                                  ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ 🔄 进程守护: 每30秒检查，挂了自动重启         ║"
echo "║ 📱 开机自启: 装Termux:Boot后开机自动启动      ║"
echo "║                                              ║"
echo "║ 查看守护日志:                                  ║"
echo "║   tail -f $LOG_DIR/watchdog.log             ║"
echo "║                                              ║"
echo "║ ⚠️  必须从F-Droid装Termux:Boot插件            ║"
echo "║    装完打开一次，然后重启手机                  ║"
echo "╚══════════════════════════════════════════════╝"
