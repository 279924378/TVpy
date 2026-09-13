#!/data/data/com.termux/files/usr/bin/env python3
# ============================================================
# 段德机器人 - Web管理面板
# 实时查看群消息、任务队列、积分排行、机器人状态
# 访问: http://手机IP:8080
# ============================================================

import json, os, sys, time, sqlite3, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# 配置
PANEL_PORT = 8080
PROJECT_DIR = os.path.expanduser("~/段德机器人项目")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
DB_FILE = os.path.join(SCRIPTS_DIR, "user_points.db")
CONFIG_FILE = os.path.join(SCRIPTS_DIR, "tg_config.json")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat_log.json")
PENDING_FILE = os.path.join(SCRIPTS_DIR, "tg_pending_urls.json")

# 确保目录存在
os.makedirs(LOG_DIR, exist_ok=True)

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def get_bot_status():
    """获取机器人运行状态"""
    try:
        result = subprocess.run(["pgrep", "-f", "tg_bot_service.py"], capture_output=True, text=True)
        bot_running = bool(result.stdout.strip())
    except:
        bot_running = False
    
    try:
        result = subprocess.run(["pgrep", "-f", "watchdog.sh"], capture_output=True, text=True)
        watchdog_running = bool(result.stdout.strip())
    except:
        watchdog_running = False
    
    # 运行时长
    uptime = "未知"
    try:
        result = subprocess.run(["ps", "-o", "etime=", "-p", result.stdout.strip().split()[0] if result.stdout.strip() else "1"], capture_output=True, text=True)
        if result.stdout.strip():
            uptime = result.stdout.strip()
    except:
        pass
    
    return {
        "bot_running": bot_running,
        "watchdog_running": watchdog_running,
        "uptime": uptime,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_chat_messages(limit=50):
    """获取最新群消息"""
    messages = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    messages = data[-limit:]
        except:
            pass
    return messages

def get_points_ranking(limit=20):
    """获取积分排行榜"""
    ranking = []
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, nickname, points FROM user_points ORDER BY points DESC LIMIT ?", (limit,))
            for row in cursor.fetchall():
                ranking.append({"user_id": row[0], "nickname": row[1] or "未知", "points": row[2] or 0})
            conn.close()
        except Exception as e:
            ranking = [{"error": str(e)}]
    return ranking

def get_pending_tasks():
    """获取待处理任务队列"""
    tasks = []
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    tasks = [t for t in data if t.get("status") == "pending"]
        except:
            pass
    return tasks

def get_system_info():
    """获取系统信息"""
    info = {}
    try:
        result = subprocess.run(["uptime"], capture_output=True, text=True)
        info["uptime"] = result.stdout.strip()
    except:
        info["uptime"] = "未知"
    
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            info["memory"] = f"已用 {parts[2]} / 总计 {parts[1]}"
    except:
        info["memory"] = "未知"
    
    try:
        result = subprocess.run(["df", "-h", "/data"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            info["disk"] = f"已用 {parts[2]} / 总计 {parts[1]} ({parts[4]})"
    except:
        info["disk"] = "未知"
    
    return info

# HTML面板
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>段德机器人 - 管理面板</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #c9d1d9; padding: 10px; }
.header { text-align: center; padding: 15px; background: linear-gradient(135deg, #1a0a0e, #2a1018); border-radius: 10px; margin-bottom: 15px; }
.header h1 { color: #ff2d55; font-size: 22px; margin-bottom: 5px; }
.header .status { font-size: 13px; color: #999; }
.status-online { color: #3fb950; }
.status-offline { color: #f85149; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
.card h2 { font-size: 15px; color: #ff2d55; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
.status-item { display: flex; justify-content: space-between; padding: 5px 0; font-size: 13px; }
.status-item .label { color: #8b949e; }
.status-item .value { color: #c9d1d9; font-weight: 500; }
.msg-list { max-height: 400px; overflow-y: auto; }
.msg-item { padding: 8px; border-bottom: 1px solid #21262d; font-size: 13px; }
.msg-item .sender { color: #58a6ff; font-weight: 500; }
.msg-item .time { color: #6e7681; font-size: 11px; margin-left: 8px; }
.msg-item .content { color: #c9d1d9; margin-top: 3px; word-break: break-all; }
.rank-list { list-style: none; }
.rank-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 13px; }
.rank-item .rank { color: #ffb800; width: 25px; }
.rank-item .name { flex: 1; color: #c9d1d9; }
.rank-item .points { color: #3fb950; font-weight: 500; }
.task-item { padding: 8px; background: #1c2128; border-radius: 6px; margin-bottom: 6px; font-size: 13px; }
.task-item .url { color: #58a6ff; word-break: break-all; }
.task-item .meta { color: #6e7681; font-size: 11px; margin-top: 3px; }
.empty { text-align: center; color: #6e7681; padding: 20px; font-size: 13px; }
.refresh-bar { text-align: center; padding: 10px; font-size: 12px; color: #6e7681; }
.refresh-bar button { background: #ff2d55; color: white; border: none; padding: 6px 15px; border-radius: 6px; cursor: pointer; font-size: 13px; }
</style>
</head>
<body>
<div class="header">
    <h1>⚱️ 段德机器人管理面板</h1>
    <div class="status" id="headerStatus">加载中...</div>
</div>

<div class="grid">
    <div class="card">
        <h2>🤖 运行状态</h2>
        <div id="botStatus"><div class="empty">加载中...</div></div>
    </div>
    <div class="card">
        <h2>📊 系统信息</h2>
        <div id="sysInfo"><div class="empty">加载中...</div></div>
    </div>
</div>

<div class="grid">
    <div class="card">
        <h2>💬 最新群消息</h2>
        <div class="msg-list" id="chatMessages"><div class="empty">加载中...</div></div>
    </div>
    <div class="card">
        <h2>🏆 积分排行榜</h2>
        <ul class="rank-list" id="pointsRanking"><li class="empty">加载中...</li></ul>
    </div>
</div>

<div class="card" style="margin-bottom: 15px;">
    <h2>📋 待处理任务队列</h2>
    <div id="pendingTasks"><div class="empty">加载中...</div></div>
</div>

<div class="refresh-bar">
    <button onclick="loadAll()">🔄 立即刷新</button>
    <span id="lastRefresh" style="margin-left: 10px;"></span>
</div>

<script>
function loadAll() {
    fetch('/api/status').then(r => r.json()).then(data => {
        const botEl = document.getElementById('botStatus');
        botEl.innerHTML = `
            <div class="status-item"><span class="label">机器人</span><span class="value ${data.bot_running ? 'status-online' : 'status-offline'}">${data.bot_running ? '● 运行中' : '○ 已停止'}</span></div>
            <div class="status-item"><span class="label">守护进程</span><span class="value ${data.watchdog_running ? 'status-online' : 'status-offline'}">${data.watchdog_running ? '● 运行中' : '○ 已停止'}</span></div>
            <div class="status-item"><span class="label">运行时长</span><span class="value">${data.uptime}</span></div>
            <div class="status-item"><span class="label">面板时间</span><span class="value">${data.time}</span></div>
        `;
        document.getElementById('headerStatus').textContent = 
            `机器人: ${data.bot_running ? '在线' : '离线'} | 守护: ${data.watchdog_running ? '正常' : '异常'} | ${data.time}`;
    });
    
    fetch('/api/system').then(r => r.json()).then(data => {
        document.getElementById('sysInfo').innerHTML = `
            <div class="status-item"><span class="label">系统运行</span><span class="value">${data.uptime || '未知'}</span></div>
            <div class="status-item"><span class="label">内存</span><span class="value">${data.memory || '未知'}</span></div>
            <div class="status-item"><span class="label">存储</span><span class="value">${data.disk || '未知'}</span></div>
        `;
    });
    
    fetch('/api/messages').then(r => r.json()).then(data => {
        const el = document.getElementById('chatMessages');
        if (data.length === 0) {
            el.innerHTML = '<div class="empty">暂无消息</div>';
        } else {
            el.innerHTML = data.slice().reverse().map(m => `
                <div class="msg-item">
                    <span class="sender">${m.sender || '未知'}</span>
                    <span class="time">${m.time || ''}</span>
                    <div class="content">${m.content || ''}</div>
                </div>
            `).join('');
        }
    });
    
    fetch('/api/ranking').then(r => r.json()).then(data => {
        const el = document.getElementById('pointsRanking');
        if (data.length === 0 || data[0].error) {
            el.innerHTML = '<li class="empty">暂无数据</li>';
        } else {
            el.innerHTML = data.map((u, i) => `
                <li class="rank-item">
                    <span class="rank">${i+1}</span>
                    <span class="name">${u.nickname}</span>
                    <span class="points">${u.points} 分</span>
                </li>
            `).join('');
        }
    });
    
    fetch('/api/tasks').then(r => r.json()).then(data => {
        const el = document.getElementById('pendingTasks');
        if (data.length === 0) {
            el.innerHTML = '<div class="empty">队列为空，往群里扔个网址试试</div>';
        } else {
            el.innerHTML = data.map(t => `
                <div class="task-item">
                    <div class="url">${t.url}</div>
                    <div class="meta">投递者: ${t.from_user || '未知'} | 时间: ${t.time || '未知'}</div>
                </div>
            `).join('');
        }
    });
    
    document.getElementById('lastRefresh').textContent = '最后刷新: ' + new Date().toLocaleTimeString();
}

loadAll();
setInterval(loadAll, 5000);
</script>
</body>
</html>"""

class PanelHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path == '/api/status':
            self._json_response(get_bot_status())
        elif self.path == '/api/system':
            self._json_response(get_system_info())
        elif self.path == '/api/messages':
            self._json_response(get_chat_messages())
        elif self.path == '/api/ranking':
            self._json_response(get_points_ranking())
        elif self.path == '/api/tasks':
            self._json_response(get_pending_tasks())
        else:
            self.send_response(404)
            self.end_headers()
    
    def _json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # 静默日志

def main():
    print(f"⚱️ 段德机器人管理面板启动中...")
    print(f"📱 访问地址: http://<手机IP>:{PANEL_PORT}")
    print(f"📂 项目目录: {PROJECT_DIR}")
    
    # 获取手机IP
    try:
        result = subprocess.run(["ifconfig", "wlan0"], capture_output=True, text=True)
        import re
        match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
        if match:
            print(f"🌐 你的IP: http://{match.group(1)}:{PANEL_PORT}")
    except:
        pass
    
    server = HTTPServer(('0.0.0.0', PANEL_PORT), PanelHandler)
    print(f"✅ 面板已启动，按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 面板已停止")
        server.server_close()

if __name__ == '__main__':
    main()
