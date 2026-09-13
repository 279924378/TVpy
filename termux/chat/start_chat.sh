#!/data/data/com.termux/files/usr/bin/bash
# 启动群消息实时查看器

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"

echo "⚱️ 启动群消息实时查看器..."
cd "$SCRIPTS_DIR"
python3 chat_view.py
