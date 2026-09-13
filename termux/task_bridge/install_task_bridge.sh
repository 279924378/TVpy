#!/data/data/com.termux/files/usr/bin/bash
# 一键安装任务上传桥（Termux → GitHub → 豆包AI）

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/task_bridge"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装任务上传桥                ║"
echo "║   (群里网址/反馈 → GitHub → 豆包AI自动处理)  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载任务上传脚本
echo "[1/3] 下载任务上传脚本..."
wget -q "$GITHUB_RAW/push_tasks.sh" -O "$SCRIPTS_DIR/push_tasks.sh"
chmod +x "$SCRIPTS_DIR/push_tasks.sh"
if [ -f "$SCRIPTS_DIR/push_tasks.sh" ]; then
    echo "  ✅ push_tasks.sh 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 2. 启动任务上传守护（每2分钟上传一次）
echo ""
echo "[2/3] 启动任务上传守护（每2分钟上传到GitHub）..."
pkill -f "push_tasks.sh daemon" 2>/dev/null
cd "$SCRIPTS_DIR"
nohup bash push_tasks.sh daemon >> "$PROJECT_DIR/logs/task_upload.log" 2>&1 &
sleep 2
if pgrep -f "push_tasks.sh daemon" > /dev/null; then
    echo "  ✅ 任务上传守护已启动"
else
    echo "  ⚠️  守护启动失败"
fi

# 3. 立即上传一次
echo ""
echo "[3/3] 立即上传一次当前任务..."
bash "$SCRIPTS_DIR/push_tasks.sh" once

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅ 任务上传桥安装完成！                     ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  工作流程:                                     ║"
echo "║  1. 群里发网址/反馈问题 → 机器人接收          ║"
echo "║  2. 每2分钟自动上传到GitHub任务文件           ║"
echo "║  3. 豆包AI定时检测并自动处理(爬虫/修复)       ║"
echo "║  4. 处理完成后py推送到GitHub                   ║"
echo "║  5. Termux自动同步拉取最新py并推群            ║"
echo "║                                                ║"
echo "║  常用命令:                                     ║"
echo "║  立即上传: bash push_tasks.sh once            ║"
echo "║  查看日志: tail -f logs/task_upload.log       ║"
echo "╚══════════════════════════════════════════════╝"
