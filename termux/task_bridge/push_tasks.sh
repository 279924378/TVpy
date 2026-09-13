#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 段德机器人 - 任务上传到GitHub（供豆包AI拉取处理）
# ============================================================

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"
PENDING_FILE="$SCRIPTS_DIR/tg_pending_urls.json"
FEEDBACK_FILE="$SCRIPTS_DIR/tg_feedback.json"
UPLOAD_LOG="$LOG_DIR/task_upload.log"
CONFIG_FILE="$SCRIPTS_DIR/tg_config.json"

GITHUB_API="https://api.github.com/repos/jwarrenrzflynn/TVpy/contents"
TASKS_FILE="termux_tasks/pending_tasks.json"

mkdir -p "$LOG_DIR"

# 从配置文件读取GitHub Token
GITHUB_TOKEN=$(python3 -c "
import json
try:
    c = json.load(open('$CONFIG_FILE'))
    print(c.get('github_token', c.get('github', {}).get('token', '')))
except:
    print('')
" 2>/dev/null)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$UPLOAD_LOG"
}

read_pending_urls() {
    if [ -f "$PENDING_FILE" ]; then cat "$PENDING_FILE"; else echo "[]"; fi
}

read_feedback() {
    if [ -f "$FEEDBACK_FILE" ]; then cat "$FEEDBACK_FILE"; else echo "[]"; fi
}

upload_tasks() {
    if [ -z "$GITHUB_TOKEN" ]; then
        log "❌ 未配置GitHub Token，请在tg_config.json中添加github_token字段"
        return 1
    fi
    
    local urls=$(read_pending_urls)
    local feedback=$(read_feedback)
    
    local pending_count=$(echo "$urls" | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    print(sum(1 for x in data if x.get('status')=='pending'))
except: print(0)
" 2>/dev/null)
    
    local feedback_count=$(echo "$feedback" | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    print(sum(1 for x in data if x.get('status')=='pending'))
except: print(0)
" 2>/dev/null)
    
    if [ "$pending_count" = "0" ] && [ "$feedback_count" = "0" ]; then
        log "无待处理任务 (网址:$pending_count, 反馈:$feedback_count)"
        return 0
    fi
    
    log "发现待处理任务: 网址$pending_count个, 反馈$feedback_count条"
    
    local tasks_json=$(python3 -c "
import json
urls = json.loads('''$urls''')
feedback = json.loads('''$feedback''')
result = {
    'updated_at': '$(date '+%Y-%m-%d %H:%M:%S')',
    'pending_urls': [x for x in urls if x.get('status')=='pending'],
    'feedback': [x for x in feedback if x.get('status')=='pending'],
    'summary': {'url_count': sum(1 for x in urls if x.get('status')=='pending'), 'feedback_count': sum(1 for x in feedback if x.get('status')=='pending')}
}
print(json.dumps(result, ensure_ascii=False, indent=2))
" 2>/dev/null)
    
    if [ -z "$tasks_json" ]; then
        log "❌ 构建任务JSON失败"
        return 1
    fi
    
    local encoded=$(echo "$tasks_json" | base64 -w 0)
    
    local sha=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "$GITHUB_API/$TASKS_FILE?ref=main" 2>/dev/null | \
        python3 -c "import json,sys; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null)
    
    local payload="{\"message\":\"同步待处理任务: 网址$pending_count个, 反馈$feedback_count条\",\"content\":\"$encoded\",\"branch\":\"main\""
    if [ -n "$sha" ]; then payload="$payload,\"sha\":\"$sha\""; fi
    payload="$payload}"
    
    local result=$(curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" \
        -H "Content-Type: application/json" -d "$payload" \
        "$GITHUB_API/$TASKS_FILE" 2>/dev/null)
    
    if echo "$result" | grep -q '"commit"'; then
        log "✅ 任务已上传到GitHub (网址:$pending_count, 反馈:$feedback_count)"
        return 0
    else
        log "❌ 上传失败"
        return 1
    fi
}

case "${1:-}" in
    once) upload_tasks ;;
    daemon)
        log "===== 任务上传守护启动 (每2分钟) ====="
        while true; do upload_tasks; sleep 120; done
        ;;
    *) echo "用法: $0 {once|daemon}" ;;
esac
