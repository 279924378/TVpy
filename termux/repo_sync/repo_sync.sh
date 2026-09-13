#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - GitHub仓库自动同步（国内加速版）
# ============================================================

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
TVBOX_DIR="$PROJECT_DIR/tvbox_subscribe"
PY_DIR="$TVBOX_DIR/py"
LOG_DIR="$PROJECT_DIR/logs"
STATE_FILE="$SCRIPTS_DIR/.repo_sync_state"
SYNC_LOG="$LOG_DIR/repo_sync.log"

GITHUB_API="https://api.github.com/repos/jwarrenrzflynn/TVpy/commits/main"
# 国内加速镜像（按优先级尝试）
MIRRORS=(
    "https://ghfast.top/https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main"
    "https://ghproxy.net/https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main"
    "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main"
)

mkdir -p "$LOG_DIR" "$PY_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$SYNC_LOG"
}

# 带重试的下载函数（自动尝试多个镜像）
download_file() {
    local remote_path="$1"
    local local_file="$2"
    local timeout="${3:-15}"
    
    for mirror in "${MIRRORS[@]}"; do
        for retry in 1 2 3; do
            if wget -q --timeout="$timeout" --tries=1 "$mirror/$remote_path" -O "$local_file" 2>/dev/null; then
                if [ -s "$local_file" ]; then
                    return 0
                fi
            fi
            sleep 1
        done
    done
    return 1
}

get_remote_sha() {
    # API也尝试多个方式
    local sha=$(curl -s --connect-timeout 10 --max-time 15 "$GITHUB_API" 2>/dev/null | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$sha" ]; then
        # 备用：通过镜像获取最新commit
        sha=$(curl -s --connect-timeout 10 --max-time 15 "https://ghfast.top/https://api.github.com/repos/jwarrenrzflynn/TVpy/commits/main" 2>/dev/null | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4)
    fi
    echo "$sha"
}

get_local_sha() {
    if [ -f "$STATE_FILE" ]; then cat "$STATE_FILE"; else echo "none"; fi
}

save_local_sha() { echo "$1" > "$STATE_FILE"; }

sync_tvbox_json() {
    log "  下载 tvbox.json..."
    if download_file "tvbox.json" "$TVBOX_DIR/tvbox.json" 20; then
        log "  ✅ tvbox.json 更新成功 ($(wc -c < "$TVBOX_DIR/tvbox.json") 字节)"
        return 0
    else
        log "  ❌ tvbox.json 下载失败（所有镜像均超时）"
        return 1
    fi
}

sync_py_files() {
    log "  获取py文件列表..."
    # 通过API获取文件列表（尝试多个镜像）
    local api_urls=(
        "https://api.github.com/repos/jwarrenrzflynn/TVpy/contents/py"
        "https://ghfast.top/https://api.github.com/repos/jwarrenrzflynn/TVpy/contents/py"
    )
    
    local files=""
    for api_url in "${api_urls[@]}"; do
        files=$(curl -s --connect-timeout 10 --max-time 15 "$api_url" 2>/dev/null | grep '"name": "[^"]*\.py"' | cut -d'"' -f4)
        if [ -n "$files" ]; then break; fi
        sleep 1
    done
    
    if [ -z "$files" ]; then
        log "  ⚠️  未获取到py文件列表，跳过"
        return 1
    fi
    
    local count=0
    local failed=0
    for fname in $files; do
        # URL编码中文文件名
        local encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$fname'''))" 2>/dev/null || echo "$fname")
        if download_file "py/$encoded" "$PY_DIR/$fname" 20; then
            count=$((count + 1))
        else
            failed=$((failed + 1))
            log "  ❌ 下载失败: $fname"
        fi
    done
    
    log "  ✅ py文件同步: 成功$count个, 失败$failed个"
    return 0
}

restart_bot() {
    log "  通知watchdog重启机器人..."
    pkill -f "tg_bot_service.py" 2>/dev/null
    pkill -f "xray run" 2>/dev/null
    sleep 2
}

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
    
    sync_tvbox_json
    sync_py_files
    save_local_sha "$remote_sha"
    restart_bot
    
    log "🎉 同步完成！"
    return 0
}

case "${1:-}" in
    check)
        remote=$(get_remote_sha)
        local=$(get_local_sha)
        echo "远程: ${remote:0:8}"
        echo "本地: ${local:0:8}"
        [ "$remote" = "$local" ] && echo "✅ 已是最新" || echo "🔄 有更新可用"
        ;;
    sync)
        log "===== 手动触发同步 ====="
        do_sync
        ;;
    daemon)
        log "===== 仓库同步守护启动 (每5分钟) ====="
        while true; do
            do_sync
            sleep 300
        done
        ;;
    *)
        echo "用法: $0 {check|sync|daemon}"
        ;;
esac
