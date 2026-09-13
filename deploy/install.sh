#!/bin/bash
# 段德机器人项目 - 一键部署脚本
# 用法: bash install.sh

set -e

echo "=========================================="
echo "  段德机器人项目 - 一键部署"
echo "=========================================="

# 配置变量
PROJECT_DIR="$HOME/duande_bot"
PYTHON_BIN="python3"
PIP_BIN="pip3"

echo ""
echo "[1/6] 创建项目目录..."
mkdir -p "$PROJECT_DIR/scripts"
mkdir -p "$PROJECT_DIR/scripts/logs"
mkdir -p "$PROJECT_DIR/output"

echo "[2/6] 复制项目文件..."
cp -f *.py "$PROJECT_DIR/" 2>/dev/null || true
cp -f *.js "$PROJECT_DIR/" 2>/dev/null || true
cp -f *.yaml "$PROJECT_DIR/" 2>/dev/null || true
cp -f SKILL.md "$PROJECT_DIR/" 2>/dev/null || true

# 如果是从GitHub克隆的，文件已经在当前目录
if [ -f "tg_bot_service.py" ]; then
    cp -f *.py "$PROJECT_DIR/" 2>/dev/null || true
fi

echo "[3/6] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi
echo "✅ Python版本: $(python3 --version)"

echo "[4/6] 安装依赖..."
$PIP_BIN install requests pytelegrambotapi python-dotenv 2>/dev/null || echo "⚠️ 部分依赖安装失败，请手动安装"

echo "[5/6] 配置文件..."
if [ ! -f "$PROJECT_DIR/tg_config.json" ]; then
    if [ -f "tg_config.json.template" ]; then
        cp tg_config.json.template "$PROJECT_DIR/tg_config.json"
        echo "⚠️ 请编辑 $PROJECT_DIR/tg_config.json 填入你的配置"
    fi
fi

echo "[6/6] 下载mihomo代理（可选）..."
read -p "是否下载mihomo代理？(y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "下载mihomo代理..."
    # 这里可以添加mihomo下载逻辑
    echo "⚠️ 请手动下载mihomo代理到 $PROJECT_DIR/"
fi

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "项目目录: $PROJECT_DIR"
echo ""
echo "启动命令:"
echo "  cd $PROJECT_DIR"
echo "  python3 tg_bot_service.py"
echo ""
echo "后台启动:"
echo "  nohup python3 tg_bot_service.py >> scripts/logs/bot.log 2>&1 &"
echo ""
echo "⚠️ 首次使用请先编辑 tg_config.json 填入配置"
echo "=========================================="
