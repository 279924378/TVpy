#!/data/data/com.termux/files/usr/bin/bash
# 一键安装自动更新功能

PROJECT_DIR="$HOME/段德机器人项目"
LOG_DIR="$PROJECT_DIR/logs"

echo "╔══════════════════════════════════════════════╗"
echo "║   段德机器人 - 安装自动更新功能              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 下载自动更新脚本
echo "[1/3] 下载自动更新脚本..."
wget -q "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/termux/auto_update.sh" \
  -O "$PROJECT_DIR/scripts/auto_update.sh"
chmod +x "$PROJECT_DIR/scripts/auto_update.sh"
echo "  ✅ 自动更新脚本已安装"

# 2. 杀掉旧的更新进程
echo ""
echo "[2/3] 启动自动更新守护进程..."
pkill -f "auto_update_loop" 2>/dev/null || true
pkill -f "auto_update.sh" 2>/dev/null || true

# 3. 创建循环守护（每5分钟检查一次）
cat > "$PROJECT_DIR/scripts/auto_update_loop.sh" << 'LOOP'
#!/data/data/com.termux/files/usr/bin/bash
while true; do
    bash ~/段德机器人项目/scripts/auto_update.sh
    sleep 300  # 5分钟检查一次
done
LOOP
chmod +x "$PROJECT_DIR/scripts/auto_update_loop.sh"

nohup bash "$PROJECT_DIR/scripts/auto_update_loop.sh" >> "$LOG_DIR/auto_update.log" 2>&1 &
sleep 2

if pgrep -f "auto_update_loop" > /dev/null 2>&1; then
    echo "  ✅ 自动更新守护进程已启动（每5分钟检查一次）"
else
    echo "  ⚠️  启动失败，请手动检查"
fi

echo ""
echo "[3/3] 立即执行一次更新检查..."
bash "$PROJECT_DIR/scripts/auto_update.sh"
echo "  ✅ 首次检查完成"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   安装完成！                                  ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ 自动更新内容:                                  ║"
echo "║   ✅ tvbox.json 订阅配置                      ║"
echo "║   ✅ 15个py源文件                             ║"
echo "║   ✅ 更新后自动重启机器人                      ║"
echo "║                                              ║"
echo "║ 查看更新日志:                                  ║"
echo "║   tail -f $LOG_DIR/auto_update.log          ║"
echo "║                                              ║"
echo "║ 手动立即更新:                                  ║"
echo "║   bash $PROJECT_DIR/scripts/auto_update.sh  ║"
echo "╚══════════════════════════════════════════════╝"
