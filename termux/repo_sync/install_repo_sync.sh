#!/data/data/com.termux/files/usr/bin/bash
# 一键安装GitHub仓库自动同步监控

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/repo_sync"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装仓库自动同步              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载同步脚本
echo "[1/3] 下载仓库同步脚本..."
wget -q "$GITHUB_RAW/repo_sync.sh" -O "$SCRIPTS_DIR/repo_sync.sh"
chmod +x "$SCRIPTS_DIR/repo_sync.sh"
if [ -f "$SCRIPTS_DIR/repo_sync.sh" ]; then
    echo "  ✅ repo_sync.sh 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 2. 启动同步守护（后台）
echo ""
echo "[2/3] 启动仓库同步守护（每5分钟自动检查）..."
pkill -f "repo_sync.sh daemon" 2>/dev/null
cd "$SCRIPTS_DIR"
nohup bash repo_sync.sh daemon >> "$PROJECT_DIR/logs/repo_sync.log" 2>&1 &
sleep 2
if pgrep -f "repo_sync.sh daemon" > /dev/null; then
    echo "  ✅ 同步守护已启动"
else
    echo "  ⚠️  守护启动失败，可手动执行: bash $SCRIPTS_DIR/repo_sync.sh daemon"
fi

# 3. 立即同步一次
echo ""
echo "[3/3] 立即同步一次最新仓库内容..."
bash "$SCRIPTS_DIR/repo_sync.sh" sync

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅ 仓库自动同步安装完成！                   ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  功能:                                         ║"
echo "║  • 每5分钟自动检查GitHub仓库更新              ║"
echo "║  • 发现新py/json自动下载更新                  ║"
echo "║  • 更新后自动重启机器人                        ║"
echo "║                                                ║"
echo "║  常用命令:                                     ║"
echo "║  检查更新: bash repo_sync.sh check            ║"
echo "║  立即同步: bash repo_sync.sh sync             ║"
echo "║  查看日志: tail -f logs/repo_sync.log        ║"
echo "╚══════════════════════════════════════════════╝"
