#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - GitHub仓库自动同步监控
# 检测到仓库有新py/json就自动拉取更新并重启机器人
# ============================================================

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
TVBOX_DIR="$PROJECT_DIR/tvbox_subscribe"
PY_DIR="$TVBOX_DIR/py"
LOG_DIR="$PROJECT_DIR/logs"
STATE_FILE="$SCRIPTS_DIR/.repo_sync_state"
SYNC_LOG="$LOG_DIR/repo_sync.log"

GITHUB_API="https://api.github.com/repos/jwarrenrzflynn/TVpy/commits/main"
GITHUB_RAW="https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main"
TOKEN=""  # 公开仓库不需要token，留空即可

mkdir -p "$LOG_DIR" "$PY_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$SYNC_LOG"
}

# 获取远程最新commit SHA
get_remote_sha() {
    if [ -n "$TOKEN" ]; then
        curl -s -H "Authorization: token $TOKEN" "$GITHUB_API" 2>/dev/null | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4
    else
        curl -s "$GITHUB_API" 2>/dev/null | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4
    fi
}

# 获取本地记录的SHA
get_local_sha() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo "none"
    fi
}

# 保存本地SHA
save_local_sha() {
    echo "$1" > "$STATE_FILE"
}

# 下载最新的tvbox.json
sync_tvbox_json() {
    log "  下载 tvbox.json..."
    wget -q "$GITHUB_RAW/tvbox.json" -O "$TVBOX_DIR/tvbox.json" 2>/dev/null
    if [ -f "$TVBOX_DIR/tvbox.json" ] && [ -s "$TVBOX_DIR/tvbox.json" ]; then
        log "  ✅ tvbox.json 更新成功 ($(wc -c < "$TVBOX_DIR/tvbox.json") 字节)"
        return 0
    else
        log "  ❌ tvbox.json 下载失败"
        return 1
    fi
}

# 下载最新的py文件列表
sync_py_files() {
    log "  获取py文件列表..."
    # 通过GitHub API获取py目录下的文件列表
    local api_url="https://api.github.com/repos/jwarrenrzflynn/TVpy/contents/py"
    local files
    if [ -n "$TOKEN" ]; then
        files=$(curl -s -H "Authorization: token $TOKEN" "$api_url" 2>/dev/null | grep '"name": "[^"]*\.py"' | cut -d'"' -f4)
    else
        files=$(curl -s "$api_url" 2>/dev/null | grep '"name": "[^"]*\.py"' | cut -d'"' -f4)
    fi
    
    if [ -z "$files" ]; then
        log "  ⚠️  未获取到py文件列表，尝试直接下载已知文件"
        # 备用：直接下载已知的15个py
        local known_pys=(
            "18㊙️91波多.py" "18㊙️JavDB.py" "18㊙️傻傻视频.py" "18㊙️可乐影院.py"
            "18㊙️浪巢福地.py" "18㊙️潘金连.py" "18㊙️春心一动.py" "18㊙️淫荡女友.py"
            "18㊙️杏色影视.py" "18㊙️谢欲频道.py" "18㊙️Didi长视频.py" "18㊙️露思AV网.py"
            "18㊙️探索妹妹.py" "18㊙️51K看片.py" "18㊙️聚合影视.py"
        )
        files="${known_pys[*]}"
    fi
    
    local count=0
    local failed=0
    for fname in $files; do
        # URL编码中文文件名
        local encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$fname'))" 2>/dev/null || echo "$fname")
        wget -q "$GITHUB_RAW/py/$encoded" -O "$PY_DIR/$fname" 2>/dev/null
        if [ -f "$PY_DIR/$fname" ] && [ -s "$PY_DIR/$fname" ]; then
            count=$((count + 1))
        else
            failed=$((failed + 1))
            log "  ❌ 下载失败: $fname"
        fi
    done
    
    log "  ✅ py文件同步完成: 成功$count个, 失败$failed个"
    return 0
}

# 重启机器人服务
restart_bot() {
    log "  重启机器人服务..."
    # 停止旧进程
    pkill -f "tg_bot_service.py" 2>/dev/null
    pkill -f "xray run" 2>/dev/null
    sleep 2
    
    # 由watchdog自动拉起新进程
    log "  ✅ 已通知watchdog重启机器人"
}

# 主同步流程
do_sync() {
    local remote_sha=$(get_remote_sha)
    local local_sha=$(get_local_sha)
    
    if [ -z "$remote_sha" ]; then
        log "❌ 无法获取远程仓库状态（网络问题？）"
        return 1
    fi
    
    if [ "$remote_sha" = "$local_sha" ]; then
        log "✅ 仓库已是最新 (${remote_sha:0:8})"
        return 0
    fi
    
    log "🔄 发现更新: ${local_sha:0:8} -> ${remote_sha:0:8}"
    
    # 同步tvbox.json
    sync_tvbox_json
    
    # 同步py文件
    sync_py_files
    
    # 保存新的SHA
    save_local_sha "$remote_sha"
    
    # 重启机器人
    restart_bot
    
    log "🎉 同步完成！"
    return 0
}

# 命令行参数
case "${1:-}" in
    check)
        # 只检查不更新
        remote=$(get_remote_sha)
        local=$(get_local_sha)
        echo "远程: ${remote:0:8}"
        echo "本地: ${local:0:8}"
        if [ "$remote" = "$local" ]; then
            echo "✅ 已是最新"
        else
            echo "🔄 有更新可用，执行 sync 更新"
        fi
        ;;
    sync)
        # 强制同步一次
        log "===== 手动触发同步 ====="
        do_sync
        ;;
    daemon)
        # 后台守护模式：每5分钟检查一次
        log "===== 仓库同步守护启动 (每5分钟检查) ====="
        while true; do
            do_sync
            sleep 300  # 5分钟
        done
        ;;
    *)
        echo "用法: $0 {check|sync|daemon}"
        echo "  check  - 检查是否有更新"
        echo "  sync   - 立即同步一次"
        echo "  daemon - 后台守护，每5分钟自动检查"
        ;;
esac
