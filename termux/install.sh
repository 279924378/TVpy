#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - Termux 在线一键部署
# 用法：curl -sL <此脚本地址> | bash
# ============================================================

set -e

PROJECT_DIR="$HOME/段德机器人项目"
ZIP_URL="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/duande_termux.zip"
ZIP_FILE="/tmp/duande_termux.zip"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - Termux 在线部署              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ========== 1. 安装基础依赖 ==========
echo "[1/5] 安装基础依赖..."
pkg update -y
pkg install -y python wget curl git unzip openssl-tool jq
echo "✅ 基础依赖安装完成"

# ========== 2. 下载项目包 ==========
echo ""
echo "[2/5] 下载项目包..."
wget -q --show-progress "$ZIP_URL" -O "$ZIP_FILE"
if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
    echo "❌ 下载失败，请检查网络"
    exit 1
fi
echo "✅ 下载完成: $(du -h "$ZIP_FILE" | cut -f1)"

# ========== 3. 解压到home ==========
echo ""
echo "[3/5] 解压到home目录..."
cd "$HOME"
# 备份旧项目
if [ -d "$PROJECT_DIR" ]; then
    mv "$PROJECT_DIR" "${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    echo "  旧项目已备份"
fi
unzip -q "$ZIP_FILE" -d "$HOME"
rm -f "$ZIP_FILE"
echo "✅ 解压完成"

# ========== 4. 加执行权限 ==========
echo ""
echo "[4/5] 配置脚本权限..."
cd "$PROJECT_DIR"
chmod +x termux_install.sh termux_start.sh termux_stop.sh github_upload.sh
echo "✅ 权限配置完成"

# ========== 5. 初始化Python ==========
echo ""
echo "[5/5] 初始化Python环境..."
python3 -m pip install --upgrade pip -q
echo "✅ Python环境初始化完成"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   部署完成！接下来：                         ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ 1. 编辑配置（必须）:                          ║"
echo "║    vi $PROJECT_DIR/scripts/tg_config.json  ║"
echo "║    填写 Bot Token、群ID、GitHub Token        ║"
echo "║                                              ║"
echo "║ 2. 启动机器人:                                ║"
echo "║    cd $PROJECT_DIR && bash termux_start.sh ║"
echo "║                                              ║"
echo "║ 3. 查看日志:                                  ║"
echo "║    tail -f $PROJECT_DIR/logs/bot.log       ║"
echo "║                                              ║"
echo "║ 💡 手机需开全局VPN才能访问Telegram            ║"
echo "╚══════════════════════════════════════════════╝"
