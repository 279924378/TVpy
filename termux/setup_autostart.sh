#!/data/data/com.termux/files/usr/bin/bash
# 配置Termux打开自动进机器人面板
PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
BASHRC="$HOME/.bashrc"

echo "配置Termux开机自动进面板..."

# 备份原bashrc
if [ -f "$BASHRC" ] && ! grep -q "段德机器人自动启动" "$BASHRC"; then
    cp "$BASHRC" "$BASHRC.bak"
fi

# 移除旧的自动启动配置（如果有）
sed -i '/# ===== 段德机器人自动启动 =====/,/# ===== 段德机器人自动启动结束 =====/d' "$BASHRC"

# 添加新的自动启动配置
cat >> "$BASHRC" << 'EOF'

# ===== 段德机器人自动启动 =====
# 打开Termux自动启动服务并进面板（按Ctrl+C可退出面板执行命令）
if [ -f "$HOME/段德机器人项目/scripts/start_all.sh" ]; then
    # 只在交互式shell启动（避免scp等非交互场景）
    if [[ $- == *i* ]]; then
        echo "🚀 段德机器人自动启动中..."
        bash "$HOME/段德机器人项目/scripts/start_all.sh"
        sleep 3
        if [ -f "$HOME/段德机器人项目/scripts/tui_panel.py" ]; then
            cd "$HOME/段德机器人项目/scripts" && python3 tui_panel.py
        fi
    fi
fi
# ===== 段德机器人自动启动结束 =====
EOF

echo "✅ 配置完成！"
echo "下次打开Termux会自动启动机器人并进面板"
echo "按Ctrl+C可退出面板执行其他命令"
echo "原.bashrc已备份为 .bashrc.bak"
