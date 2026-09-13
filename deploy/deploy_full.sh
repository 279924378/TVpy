#!/bin/bash
# 段德机器人 - 一键部署+启动（完全免设置）
# 用法: curl -sL <部署脚本地址> | bash

set -e

PROJECT_DIR="$HOME/duande_bot"
ZIP_URL="https://github.com/jwarrenrzflynn/TVpy/raw/main/deploy/duande_full_deploy.zip"

echo "=========================================="
echo "  段德机器人 - 一键部署（免设置版）"
echo "=========================================="

# 如果已存在，先备份
if [ -d "$PROJECT_DIR" ]; then
    echo "检测到已有安装，备份为 ${PROJECT_DIR}.bak.$(date +%s)"
    mv "$PROJECT_DIR" "${PROJECT_DIR}.bak.$(date +%s)"
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

echo ""
echo "[1/4] 下载完整部署包（含配置+数据库）..."
if command -v wget &> /dev/null; then
    wget -q -O duande_full_deploy.zip "$ZIP_URL"
elif command -v curl &> /dev/null; then
    curl -sL -o duande_full_deploy.zip "$ZIP_URL"
else
    echo "❌ 未找到wget或curl"
    exit 1
fi

if [ ! -f duande_full_deploy.zip ]; then
    echo "❌ 下载失败"
    exit 1
fi
echo "✅ 下载完成 ($(du -h duande_full_deploy.zip | cut -f1))"

echo ""
echo "[2/4] 解压..."
unzip -o duande_full_deploy.zip -d . > /dev/null 2>&1
# 处理嵌套目录
if [ -d "duande_full_deploy" ]; then
    mv duande_full_deploy/* . 2>/dev/null || true
    rm -rf duande_full_deploy
fi
rm -f duande_full_deploy.zip
echo "✅ 解压完成"

echo ""
echo "[3/4] 检查环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

pip3 install requests pytelegrambotapi -q 2>/dev/null
echo "✅ 依赖已安装"

echo ""
echo "[4/4] 启动机器人..."
chmod +x start.sh
bash start.sh

echo ""
echo "=========================================="
echo "  ✅ 部署+启动完成！"
echo "=========================================="
echo "  项目目录: $PROJECT_DIR"
echo "  查看日志: tail -f $PROJECT_DIR/logs/bot.log"
echo "  停止机器人: pkill -f tg_bot_service.py"
echo "  重启机器人: cd $PROJECT_DIR && bash start.sh"
echo "=========================================="
