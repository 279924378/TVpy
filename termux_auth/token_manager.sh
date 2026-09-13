#!/data/data/com.termux/files/usr/bin/bash
# 段德机器人 TVBox订阅token管理
# 生成/删除/列出token，同步到GitHub

PROJECT_DIR="$HOME/段德机器人项目"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
TOKEN_FILE="$SCRIPTS_DIR/.tvbox_tokens.json"
GITHUB_API="https://api.github.com/repos/jwarrenrzflynn/TVpy/contents/termux_auth/tokens.json"

# 从配置读取GitHub Token
GITHUB_TOKEN=$(python3 -c "
import json, os
f=os.path.expanduser('~/段德机器人项目/scripts/tg_config.json')
c=json.load(open(f))
print(c.get('github_token',''))
" 2>/dev/null)

mkdir -p "$SCRIPTS_DIR"

# 初始化token文件
init_tokens() {
    if [ ! -f "$TOKEN_FILE" ]; then
        echo '{"tokens":[],"updated_at":""}' > "$TOKEN_FILE"
    fi
}

# 生成随机token
gen_token() {
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -1
}

# 同步token到GitHub
sync_to_github() {
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "❌ 未配置GitHub Token"
        return 1
    fi
    
    local content=$(base64 -w 0 "$TOKEN_FILE")
    local sha=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$GITHUB_API?ref=main" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null)
    
    local payload="{\"message\":\"更新订阅token\",\"content\":\"$content\",\"branch\":\"main\""
    if [ -n "$sha" ]; then payload="$payload,\"sha\":\"$sha\""; fi
    payload="$payload}"
    
    local result=$(curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" -H "Content-Type: application/json" -d "$payload" "$GITHUB_API" 2>/dev/null)
    if echo "$result" | grep -q '"commit"'; then
        return 0
    else
        echo "❌ 同步失败"
        return 1
    fi
}

# 生成token
generate() {
    local user="$1"
    local user_id="$2"
    local days="${3:-7}"
    
    init_tokens
    local token=$(gen_token)
    local expire_at=$(date -d "+$days days" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -v+${days}d '+%Y-%m-%d %H:%M:%S')
    
    python3 -c "
import json
with open('$TOKEN_FILE') as f: data = json.load(f)
data['tokens'].append({
    'token': '$token',
    'user': '$user',
    'user_id': '$user_id',
    'status': 'active',
    'created_at': '$(date '+%Y-%m-%d %H:%M:%S')',
    'expire_at': '$expire_at'
})
data['updated_at'] = '$(date '+%Y-%m-%d %H:%M:%S')'
json.dump(data, open('$TOKEN_FILE','w'), ensure_ascii=False, indent=2)
"
    
    if sync_to_github; then
        echo "$token"
    else
        echo "FAILED"
    fi
}

# 撤销token
revoke() {
    local token="$1"
    init_tokens
    python3 -c "
import json
with open('$TOKEN_FILE') as f: data = json.load(f)
for t in data['tokens']:
    if t['token'] == '$token':
        t['status'] = 'revoked'
data['updated_at'] = '$(date '+%Y-%m-%d %H:%M:%S')'
json.dump(data, open('$TOKEN_FILE','w'), ensure_ascii=False, indent=2)
"
    sync_to_github && echo "✅ 已撤销" || echo "❌ 撤销失败"
}

# 列出所有token
list() {
    init_tokens
    python3 -c "
import json
with open('$TOKEN_FILE') as f: data = json.load(f)
print(f'共 {len(data[\"tokens\"])} 个token:')
for t in data['tokens']:
    status = '✅有效' if t['status']=='active' else '❌已撤销'
    print(f'  {status} | {t[\"user\"]} | {t[\"token\"][:16]}... | 过期:{t[\"expire_at\"]}')
"
}

case "${1:-}" in
    generate) generate "$2" "$3" "$4" ;;
    revoke) revoke "$2" ;;
    list) list ;;
    sync) init_tokens && sync_to_github && echo "✅ 已同步" ;;
    *) echo "用法: $0 {generate|revoke|list|sync}" ;;
esac
