#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - 自动更新脚本
# 每5分钟检查GitHub仓库，有更新自动下载替换+重启
# ============================================================

PROJECT_DIR="$HOME/段德机器人项目"
SUBSCRIBE_DIR="$PROJECT_DIR/tvbox_subscribe"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
STATE_FILE="$LOG_DIR/update_state.json"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main"

mkdir -p "$LOG_DIR"

# 初始化状态文件
if [ ! -f "$STATE_FILE" ]; then
    echo '{"tvbox_json":"","py_files":{},"bot_script":"","last_check":""}' > "$STATE_FILE"
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/auto_update.log"
}

get_remote_hash() {
    # 获取远程文件的MD5（通过下载临时文件计算）
    local url="$1"
    local tmpfile="/tmp/remote_check_$$.tmp"
    if wget -q --timeout=10 "$url" -O "$tmpfile" 2>/dev/null; then
        md5sum "$tmpfile" | cut -d' ' -f1
        rm -f "$tmpfile"
    else
        rm -f "$tmpfile"
        echo ""
    fi
}

get_local_hash() {
    if [ -f "$1" ]; then
        md5sum "$1" | cut -d' ' -f1
    else
        echo ""
    fi
}

update_file() {
    local remote_url="$1"
    local local_path="$2"
    local name="$3"
    
    local remote_hash=$(get_remote_hash "$remote_url")
    if [ -z "$remote_hash" ]; then
        log "❌ $name 获取远程文件失败"
        return 1
    fi
    
    local local_hash=$(get_local_hash "$local_path")
    
    if [ "$remote_hash" != "$local_hash" ]; then
        log "🔄 $name 有更新，正在下载..."
        if wget -q --timeout=15 "$remote_url" -O "$local_path"; then
            log "✅ $name 更新成功"
            return 0
        else
            log "❌ $name 下载失败"
            return 1
        fi
    else
        return 2  # 无需更新
    fi
}

NEED_RESTART=false

# ========== 1. 检查tvbox.json更新 ==========
log "--- 开始检查更新 ---"
result=$(update_file "$GITHUB_RAW/tvbox.json" "$SUBSCRIBE_DIR/tvbox.json" "tvbox.json")
case $? in
    0) NEED_RESTART=true ;;
    1) log "❌ tvbox.json 更新失败" ;;
esac

# ========== 2. 检查15个py文件更新 ==========
PY_FILES=(
  "18㊙️51K看片.py"
  "18㊙️91波多.py"
  "18㊙️Didi长视频.py"
  "18㊙️JavDB.py"
  "18㊙️傻傻视频.py"
  "18㊙️可乐影院.py"
  "18㊙️探索妹妹.py"
  "18㊙️春心一动.py"
  "18㊙️杏色影视.py"
  "18㊙️浪巢福地.py"
  "18㊙️淫荡女友.py"
  "18㊙️潘金连.py"
  "18㊙️聚合影视.py"
  "18㊙️谢欲频道.py"
  "18㊙️露思AV网.py"
)

PY_UPDATED=0
for f in "${PY_FILES[@]}"; do
    ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$f'))")
    result=$(update_file "$GITHUB_RAW/py/$ENCODED" "$SUBSCRIBE_DIR/py/$f" "$f")
    if [ $? -eq 0 ]; then
        PY_UPDATED=$((PY_UPDATED+1))
    fi
done

if [ $PY_UPDATED -gt 0 ]; then
    log "📦 共更新 $PY_UPDATED 个py文件"
    NEED_RESTART=true
fi

# ========== 3. 检查机器人脚本更新（可选，默认关闭避免覆盖本地修改）==========
# update_file "$GITHUB_RAW/termux/tg_bot_service.py" "$SCRIPTS_DIR/tg_bot_service.py" "机器人脚本"

# ========== 4. 有更新则重启机器人 ==========
if [ "$NEED_RESTART" = true ]; then
    log "🔄 检测到更新，正在重启机器人..."
    pkill -f "tg_bot_service.py" 2>/dev/null || true
    sleep 2
    cd "$SCRIPTS_DIR"
    nohup python3 tg_bot_service.py --silent >> "$LOG_DIR/bot.log" 2>&1 &
    sleep 3
    if pgrep -f "tg_bot_service.py" > /dev/null 2>&1; then
        log "✅ 机器人重启成功"
    else
        log "❌ 机器人重启失败"
    fi
else
    log "✅ 所有文件已是最新，无需更新"
fi

# 更新最后检查时间
python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['last_check'] = '$(date '+%Y-%m-%d %H:%M:%S')'
json.dump(s, open('$STATE_FILE','w'), indent=2)
" 2>/dev/null

log "--- 检查完成 ---"
