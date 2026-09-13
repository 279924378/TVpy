#!/data/data/com.termux/files/usr/bin/bash
# 一键安装开机自启+守护进程

PROJECT_DIR="$HOME/段德机器人项目"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装开机自启+守护进程        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 安装Termux:Boot（如果没装）
echo "[1/4] 检查Termux:Boot插件..."
if [ ! -d "$HOME/.termux/boot" ]; then
    mkdir -p "$HOME/.termux/boot"
    echo "  ✅ 创建 ~/.termux/boot/ 目录"
else
    echo "  ✅ 目录已存在"
fi

# 2. 复制boot脚本
echo ""
echo "[2/4] 安装开机自启脚本..."
cp "$PROJECT_DIR/scripts/boot" "$HOME/.termux/boot/duande_bot"
chmod +x "$HOME/.termux/boot/duande_bot"
echo "  ✅ 开机自启脚本已安装: ~/.termux/boot/duande_bot"

# 3. 复制守护脚本
echo ""
echo "[3/4] 安装守护脚本..."
cp "$PROJECT_DIR/scripts/watchdog.sh" "$PROJECT_DIR/scripts/"
chmod +x "$PROJECT_DIR/scripts/watchdog.sh"
echo "  ✅ 守护脚本已安装: $PROJECT_DIR/scripts/watchdog.sh"

# 4. 启动守护进程
echo ""
echo "[4/4] 启动守护进程..."
pkill -f "watchdog.sh" 2>/dev/null || true
cd "$PROJECT_DIR"
nohup bash scripts/watchdog.sh >> logs/watchdog.log 2>&1 &
sleep 2
if pgrep -f "watchdog.sh" > /dev/null 2>&1; then
    echo "  ✅ 守护进程已启动"
else
    echo "  ⚠️  守护进程启动失败，请手动检查"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   安装完成！                                  ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ 1. 开机自启: 安装Termux:Boot插件后开机自动启动 ║"
echo "║ 2. 进程守护: 每30秒检查，挂了自动重启         ║"
echo "║ 3. 查看守护日志:                               ║"
echo "║    tail -f $PROJECT_DIR/logs/watchdog.log    ║"
echo "║                                              ║"
echo "║ ⚠️  重要: 必须从F-Droid安装Termux:Boot插件    ║"
echo "║    安装后打开一次Termux:Boot，然后重启手机    ║"
echo "╚══════════════════════════════════════════════╝"
