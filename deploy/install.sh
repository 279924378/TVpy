#!/bin/bash
# 段德机器人项目 - 一键部署脚本
# 用法: curl -sL https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/deploy/install.sh | bash

set -e

echo "=========================================="
echo "  段德机器人项目 - 一键部署"
echo "=========================================="

PROJECT_DIR="$HOME/duande_bot"
ZIP_URL="https://github.com/jwarrenrzflynn/TVpy/raw/main/deploy/duande_bot_deploy.zip"

echo ""
echo "[1/5] 创建项目目录..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

echo "[2/5] 下载部署包..."
if command -v wget &> /dev/null; then
    wget -q -O duande_bot_deploy.zip "$ZIP_URL"
elif command -v curl &> /dev/null; then
    curl -sL -o duande_bot_deploy.zip "$ZIP_URL"
else
    echo "❌ 未找到wget或curl，请先安装"
    exit 1
fi

if [ ! -f duande_bot_deploy.zip ]; then
    echo "❌ 下载失败"
    exit 1
fi
echo "✅ 部署包下载完成 ($(du -h duande_bot_deploy.zip | cut -f1))"

echo "[3/5] 解压部署包..."
unzip -o duande_bot_deploy.zip -d . > /dev/null 2>&1
# 如果解压后有duande_deploy目录，移动文件出来
if [ -d "duande_deploy" ]; then
    mv duande_deploy/* . 2>/dev/null || true
    rm -rf duande_deploy
fi
rm -f duande_bot_deploy.zip
echo "✅ 解压完成"

echo "[4/5] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi
echo "✅ Python版本: $(python3 --version)"

echo "[5/5] 安装依赖..."
pip3 install requests pytelegrambotapi 2>/dev/null || echo "⚠️ 依赖安装失败，请手动安装: pip3 install requests pytelegrambotapi"

# 创建日志目录
mkdir -p scripts/logs

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "项目目录: $PROJECT_DIR"
echo "文件列表:"
ls -1 "$PROJECT_DIR" | head -20
echo ""
echo "⚠️ 重要：首次使用请配置"
echo "  1. 编辑 tg_config.json 填入你的Bot Token等配置"
echo "  2. 如果没有tg_config.json，复制 tg_config.json.template 为 tg_config.json"
echo ""
echo "启动命令:"
echo "  cd $PROJECT_DIR"
echo "  python3 tg_bot_service.py"
echo ""
echo "后台启动:"
echo "  nohup python3 tg_bot_service.py >> scripts/logs/bot.log 2>&1 &"
echo "=========================================="
