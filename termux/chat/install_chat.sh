#!/data/data/com.termux/files/usr/bin/bash
# 一键安装群消息实时查看器

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/chat"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装群消息查看器              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载消息查看器
echo "[1/2] 下载消息查看器..."
wget -q "$GITHUB_RAW/chat_view.py" -O "$SCRIPTS_DIR/chat_view.py"
if [ -f "$SCRIPTS_DIR/chat_view.py" ]; then
    echo "  ✅ chat_view.py 下载完成"
else
    echo "  ❌ 下载失败"
    exit 1
fi

# 2. 下载启动脚本
echo ""
echo "[2/2] 下载启动脚本..."
wget -q "$GITHUB_RAW/start_chat.sh" -O "$PROJECT_DIR/start_chat.sh"
chmod +x "$PROJECT_DIR/start_chat.sh"
echo "  ✅ start_chat.sh 下载完成"

echo ""
echo "✅ 安装完成！"
echo ""
echo "启动命令: bash ~/段德机器人项目/start_chat.sh"
echo ""
echo "效果: 实时滚动显示群消息，格式 [消息] 用户名(ID): 内容"
echo "按 Ctrl+C 退出查看器，后台机器人仍在运行"
echo ""

# 自动启动
sleep 2
bash "$PROJECT_DIR/start_chat.sh"
