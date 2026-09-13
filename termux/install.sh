#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - Termux 在线一键部署（含真实配置+最新数据）
# 用法：curl -sL <此脚本地址> | bash
# ============================================================

set -e

PROJECT_DIR="$HOME/段德机器人项目"
ZIP_URL="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/duande_termux.zip"
ZIP_FILE="$HOME/duande_termux.zip"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - Termux 在线部署              ║"
echo "║   （含真实配置+15个py源+鉴权订阅）          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ========== 1. 安装基础依赖 ==========
echo "[1/4] 安装基础依赖..."
pkg update -y
pkg install -y python wget curl git unzip openssl-tool jq
echo "✅ 基础依赖安装完成"

# ========== 2. 下载项目包 ==========
echo ""
echo "[2/4] 下载项目包（含真实配置+15个py源）..."
rm -f "$ZIP_FILE"
wget -q --show-progress "$ZIP_URL" -O "$ZIP_FILE"
if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
    echo "❌ 下载失败，请检查网络"
    exit 1
fi
echo "✅ 下载完成: $(du -h "$ZIP_FILE" | cut -f1)"

# ========== 3. 解压到home ==========
echo ""
echo "[3/4] 解压到home目录..."
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
echo "[4/4] 配置脚本权限..."
cd "$PROJECT_DIR"
chmod +x termux_install.sh termux_start.sh termux_stop.sh github_upload.sh 2>/dev/null
echo "✅ 权限配置完成"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   部署完成！配置已预填，直接启动即可         ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ 启动机器人:                                    ║"
echo "║   cd ~/段德机器人项目 && bash termux_start.sh ║"
echo "║                                              ║"
echo "║ 查看日志:                                      ║"
echo "║   tail -f ~/段德机器人项目/logs/bot.log      ║"
echo "║                                              ║"
echo "║ 停止服务:                                      ║"
echo "║   bash ~/段德机器人项目/termux_stop.sh       ║"
echo "║                                              ║"
echo "║ 💡 手机需开全局VPN才能访问Telegram            ║"
echo "║ 💡 配置已预填（Bot Token/群ID/GitHub Token） ║"
echo "╚══════════════════════════════════════════════╝"
