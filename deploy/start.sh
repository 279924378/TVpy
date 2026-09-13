#!/bin/bash
# 段德机器人 - 一键启动脚本（免设置）
# 用法: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  段德机器人 - 启动中..."
echo "=========================================="

# 创建日志目录
mkdir -p logs

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi

# 安装依赖（如果未安装）
pip3 install requests pytelegrambotapi -q 2>/dev/null

# 检查mihomo代理（可选，如果有就启动）
if [ -f "./mihomo_proxy" ] && [ -f "./mihomo_config.yaml" ]; then
    if ! ps aux | grep mihomo_proxy | grep -v grep > /dev/null; then
        echo "启动mihomo代理..."
        chmod +x ./mihomo_proxy
        nohup ./mihomo_proxy -f ./mihomo_config.yaml >> logs/mihomo.log 2>&1 &
        sleep 3
    fi
fi

# 检查是否已经在运行
if ps aux | grep tg_bot_service.py | grep -v grep > /dev/null; then
    echo "⚠️ 机器人已经在运行中"
    ps aux | grep tg_bot_service.py | grep -v grep
    echo ""
    echo "如需重启，请先执行: pkill -f tg_bot_service.py"
    exit 0
fi

# 启动机器人
echo "启动Telegram机器人..."
nohup python3 tg_bot_service.py >> logs/bot.log 2>&1 &
BOT_PID=$!

sleep 3

# 验证启动
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo "  ✅ 机器人启动成功！"
    echo "=========================================="
    echo "  PID: $BOT_PID"
    echo "  日志: tail -f logs/bot.log"
    echo "  停止: pkill -f tg_bot_service.py"
    echo "=========================================="
else
    echo "❌ 机器人启动失败，请查看日志:"
    tail -20 logs/bot.log
    exit 1
fi
