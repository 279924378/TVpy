#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 口令服务（持续监听群消息·代理池自动切换）
- 持续轮询 getUpdates，处理群内口令
- 口令：/py 列py文件、/zip 列小程序、/list 列所有存货、/sites 列站点、/help 帮助、/clean 撤回
- 收到网址自动记录并提示（需在豆包对话中触发四步流水线）
- 代理池自动切换，xray本地代理

用法:
  python3 tg_bot_service.py              # 启动口令服务（前台运行）
  python3 tg_bot_service.py --debug      # 调试模式（打印每条消息）
  nohup python3 tg_bot_service.py &      # 后台运行
"""
import os
import sys
import json
import time
import random
import subprocess
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "tg_config.json")
DEFAULT_PROXY_POOL = os.path.join(SCRIPT_DIR, "..", "assets", "tg_proxy_pool.json")
DEFAULT_HISTORY = os.path.join(SCRIPT_DIR, "tg_push_history.json")

# ============ 积分系统配置 ============
USER_POINTS_FILE = os.path.join(SCRIPT_DIR, "user_points.json")
SIGN_REWARD = 5          # 每日签到奖励积分
CRAWL_COST = 10          # 每个网址消耗积分
ADMIN_FREE = True        # 管理员免费

# 网址正则（http/https开头）
URL_PATTERN = re.compile(r'https?://[^\s]+', re.IGNORECASE)

# 反馈修复脚本路径（duande-baoxue-announcer 技能）
FEEDBACK_REPAIR_SCRIPT = os.path.join(SCRIPT_DIR, "..", "duande-baoxue-announcer", "scripts", "feedback_repair.py")

# 遮天霸气语录库（段德风格，按场景分类，随机轮换）
BOLD_QUOTES = {
    "welcome": [
        "无量天尊！贫道段德，盗墓的祖宗，挖坟的行家，今日重出江湖，诸位道友有宝穴尽管扔来！",
        "贫道这一脉，从荒古挖到今古，从星空挖到坟冢，什么大阵仗没见过？诸位有宝穴尽管招呼！",
        "你祖宗的坟贫道都挖过，你算什么东西？有宝穴赶紧扔群里，贫道给你掘个底朝天！",
        "我为盗墓祖，当掘尽世间一切宝穴！无量天尊，诸位有穴尽管扔来！",
        "仙路尽头谁为峰，一见段德坟成空！贫道掘冢无数，今日再开坛，宝穴何在？",
        "天道无始亦无终，贫道盗墓永无穷！宝穴何在？扔来便是！",
        "贫道有一锅，可煮山河日月，可炼宝穴明器！诸位有穴尽管扔，贫道来者不拒！",
        "不为成仙，只为在这红尘中等你扔来宝穴！无量天尊！",
    ],
    "url_queued": [
        "此宝穴与贫道有缘！已入待掘队列，待贫道择日掘开，造化可期！",
        "道友请留步！此宝穴贫道记下了，入队列待掘，跑字一到即刻开坛！",
        "造化！大造化啊！又一座宝穴入队，贫道这手又痒了，且等号令！",
        "这买卖划算！宝穴已入队列，待群主一声令下，贫道掘它个鸡犬不宁！",
        "贫道盗墓无数，此穴气息不凡，已入待掘队列，且看贫道手段！",
        "宝穴已入队列，贫道这一脉最是讲理，说掘就掘，绝不食言！",
        "此穴与贫道有大因果，已入待掘队列，跑字一到，因果了结！",
        "无量天尊！又一宝穴入队，贫道这洛阳铲已经饥渴难耐了！",
    ],
    "push_done": [
        "宝穴已掘开明器！源术+微阁已奉上，诸位道友验货！",
        "贫道出手，必是精品！宝穴已掘，明器已出，诸位请看这造化！",
        "掘冢寻宝，贫道祖宗！此穴已被贫道翻了个底朝天，明器在此，验货吧！",
        "我为盗墓祖，掘穴如探囊！宝穴已破，明器已出，诸位收好！",
        "此宝穴与贫道有缘，今日缘法已了，明器奉上，诸位且看这手段！",
        "无量天尊！又一座宝穴被贫道拿下，源术微阁已推送，诸位验货！",
        "贫道掘冢无数，此穴最是不凡，明器已出，诸位请看这大造化！",
        "宝穴已破，明器已出，贫道这一脉从不空手而归，验货吧诸位！",
    ],
    "queue_empty": [
        "待掘队列为空，诸位道友赶紧往群里扔宝穴，贫道这手都痒了！",
        "贫道掘冢无数，今日竟无宝可掘？诸位赶紧扔宝穴来，莫让贫道闲着！",
        "宝穴何在？贫道这一锅都烧热了，就等宝穴下锅了！诸位赶紧扔！",
        "无量天尊！队列空空，诸位道友有宝穴尽管扔来，贫道来者不拒！",
        "贫道这洛阳铲都磨亮了，就等宝穴了！诸位赶紧往群里扔！",
        "队列为空，贫道这盗墓祖宗竟无宝可掘？诸位道友给力点，扔宝穴来！",
    ],
    "clean_done": [
        "旧的不去，新的不来！此宝穴旧消息已被贫道清理，静待新明器！",
        "贫道掘冢讲究干净利落，旧消息已撤，队列已清，且待新造化！",
        "此穴因果已了，旧迹已消，贫道去也！无量天尊！",
        "贫道这一脉最是讲理，说清就清，旧消息已撤，诸位且看新明器！",
    ],
}


def pick_quote(scene):
    """随机选一条霸气语录"""
    quotes = BOLD_QUOTES.get(scene, [])
    if not quotes:
        return ""
    return random.choice(quotes)


# ==================== 积分系统 ====================

def load_user_points():
    if not os.path.isfile(USER_POINTS_FILE):
        return {}
    try:
        with open(USER_POINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_points(data):
    try:
        with open(USER_POINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 积分数据写入失败: {e}")


def get_user_points(user_id):
    data = load_user_points()
    return data.get(str(user_id), {}).get("points", 0)


def add_user_points(user_id, from_user, points, reason=""):
    data = load_user_points()
    key = str(user_id)
    if key not in data:
        data[key] = {"points": 0, "from_user": from_user, "last_sign": "", "total_sign": 0}
    data[key]["points"] = data[key].get("points", 0) + points
    data[key]["from_user"] = from_user
    if reason:
        data[key]["last_reason"] = reason
    save_user_points(data)
    return data[key]["points"]


def consume_user_points(user_id, points):
    data = load_user_points()
    key = str(user_id)
    current = data.get(key, {}).get("points", 0)
    if current < points:
        return False
    data[key]["points"] = current - points
    save_user_points(data)
    return True


def handle_sign(user_id, from_user):
    """处理签到，带文件锁防止并发重复签到"""
    import fcntl
    key = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")

    # 使用文件锁确保原子性，防止并发重复签到
    lock_file = USER_POINTS_FILE + ".lock"
    with open(lock_file, "w") as lock_f:
        try:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
        except Exception:
            pass  # 非Linux系统降级为无锁

        # 加锁后重新读取最新数据
        data = load_user_points()
        if key not in data:
            data[key] = {"points": 0, "from_user": from_user, "last_sign": "", "total_sign": 0}

        # 二次检查：确认今天未签到
        if data[key].get("last_sign") == today:
            current = data[key].get("points", 0)
            try:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
            except Exception:
                pass
            return (
                f"📜 无量天尊！{from_user} 道友今日已然签到过了！\n\n"
                f"💰 当前积分：{current} 分\n"
                f"📅 累计签到：{data[key].get('total_sign', 0)} 天\n\n"
                f"⏰ 签到每日仅可一次，明日请早！\n\n"
                f"—— 摸金校尉·无良道士段德"
            )

        # 执行签到
        data[key]["last_sign"] = today
        data[key]["total_sign"] = data[key].get("total_sign", 0) + 1
        data[key]["points"] = data[key].get("points", 0) + SIGN_REWARD
        data[key]["from_user"] = from_user
        save_user_points(data)

        try:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
        except Exception:
            pass

    return (
        f"✅ 无量天尊！{from_user} 道友签到成功！\n\n"
        f"💰 获得积分：+{SIGN_REWARD} 分\n"
        f"📊 当前积分：{data[key]['points']} 分\n"
        f"📅 累计签到：{data[key]['total_sign']} 天\n\n"
        f"⚡ 积分用途：提交「爬虫+网址」掘穴，每座消耗 {CRAWL_COST} 分\n"
        f"💡 每日签到可得 {SIGN_REWARD} 分，积少成多！\n\n"
        f"—— 摸金校尉·无良道士段德"
    )


def cmd_points(user_id, from_user):
    current = get_user_points(user_id)
    data = load_user_points()
    total_sign = data.get(str(user_id), {}).get("total_sign", 0)
    return (
        f"💰 无量天尊！{from_user} 道友的积分簿：\n\n"
        f"📊 当前积分：{current} 分\n"
        f"📅 累计签到：{total_sign} 天\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📥 积分获取方式：\n"
        f"   • 每日签到：+{SIGN_REWARD} 分/天\n"
        f"   • 提交网址：+2 分/座（纯网址收录即得）\n"
        f"   • 群主赏赐：群主可额外发放积分\n\n"
        f"📤 积分消耗方式：\n"
        f"   • 立即掘穴：-{CRAWL_COST} 分/座（发「爬虫+网址」）\n"
        f"   • 竞价押注：最低5分，最高100分（价高者得）\n"
        f"   • 重复/困难网址：-1 分\n\n"
        f"🎩 拍卖行竞价规则：\n"
        f"   • 发「押积分 网址 积分数」参与竞价\n"
        f"   • 1分钟押注倒计时，时间到价高者得\n"
        f"   • 每日仅掘5座，超出者积分原路退还\n"
        f"   • 群主宝穴👑不可被顶，管理员可参与竞价\n"
        f"   • 发「竞价榜」查看当前排名\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 积分不足时，道友可每日签到累积，或多提交网址赚积分！\n\n"
        f"—— 摸金校尉·无良道士段德"
    )


def build_main_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "📜 每日签到", "callback_data": "sign"},
                {"text": "💰 我的积分", "callback_data": "points"},
            ],
            [
                {"text": "🔗 提交爬虫", "callback_data": "crawl_help"},
                {"text": "📋 待掘队列", "callback_data": "queue"},
            ],
            [
                {"text": "📁 115网盘登录", "callback_data": "115_login"},
                {"text": "📚 口令簿", "callback_data": "help"},
            ],
        ]
    }


def handle_callback(callback_data, user_id, from_user, chat_id, pending_path, token=None, local_port=None):
    data = callback_data or ""
    if data == "sign":
        return handle_sign(user_id, from_user), None
    elif data == "points":
        return cmd_points(user_id, from_user), None
    elif data == "crawl_help":
        return (
            f"🔗 无量天尊！提交爬虫之法：\n\n"
            f"直接发送：爬虫 https://网址.com\n\n"
            f"💰 每座宝穴消耗 {CRAWL_COST} 积分\n"
            f"📜 积分不足时请先签到累积\n"
            f"👑 群主/管理员免费掘穴\n\n"
            f"—— 摸金校尉·无良道士段德"
        ), None
    elif data == "queue":
        return cmd_queue(pending_path), None
    elif data == "help":
        return cmd_help(None, chat_id), None
    elif data == "115_login":
        # 115网盘扫码登录（先检查是否已登录且有效，已登录则提示不重复发码）
        if token and local_port:
            # 检查该用户的Cookie是否存在且有效
            cookie_path = os.path.join(SCRIPT_DIR, f"115_cookies_{user_id}.json")
            cookie_valid = False
            user_name_115 = ""
            if os.path.exists(cookie_path):
                try:
                    import json as _json
                    import requests as _req
                    with open(cookie_path, "r", encoding="utf-8") as f:
                        cfg = _json.load(f)
                    cookies = cfg.get("cookies", {})
                    if cookies:
                        test_session = _req.Session()
                        test_session.cookies.update(cookies)
                        test_session.headers.update({
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": "https://115.com/",
                        })
                        resp = test_session.get("https://115.com/?ct=user&ac=user&op=info", timeout=10)
                        data_resp = resp.json()
                        if data_resp.get("state"):
                            cookie_valid = True
                            user_name_115 = data_resp.get("data", {}).get("user_name", "?")
                except Exception:
                    cookie_valid = False

            if cookie_valid:
                # 已登录且有效，提示不重复发码
                return (
                    f"✅ 无量天尊！{from_user} 道友，您的115网盘已登录，目前有效！\n\n"
                    f"👤 账号: {user_name_115}\n"
                    f"📦 群里任何人发的磁力/迅雷链接都会自动提交到您的115网盘。\n\n"
                    f"—— 摸金校尉·无良道士段德"
                ), None
            else:
                # 未登录或已失效，发二维码
                handle_115_qrcode(user_id, from_user, chat_id, token, local_port)
                return (
                    f"📁 无量天尊！{from_user} 道友，115网盘登录二维码已私发给您！\n\n"
                    f"请查看私聊消息，用115手机APP扫码登录。\n"
                    f"登录成功后，群里任何人发的磁力/迅雷链接都会自动提交到您的115网盘。\n\n"
                    f"—— 摸金校尉·无良道士段德"
                ), None
        else:
            return "❌ 115登录功能暂不可用，请直接发「二维码」指令。", None
    return None, None


def load_config(path):
    if not os.path.isfile(path):
        print(f"[错误] 配置文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_proxy_pool(path):
    if not os.path.isfile(path):
        return {"nodes": [], "base_local_port": 10900}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history(path):
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def gen_xray_config(node, local_port):
    return {
        "log": {"loglevel": "error"},
        "inbounds": [{"tag": "http_in", "port": local_port, "listen": "127.0.0.1", "protocol": "http"}],
        "outbounds": [{
            "tag": "proxy_out", "protocol": "vless",
            "settings": {"vnext": [{"address": node["server"], "port": node["port"],
                "users": [{"id": node["uuid"], "encryption": "none", "flow": node.get("flow", "xtls-rprx-vision")}]}]},
            "streamSettings": {"network": "tcp", "security": "tls",
                "tlsSettings": {"serverName": node["server_name"], "allowInsecure": node.get("insecure", True), "fingerprint": "chrome"}}
        }]
    }


def start_xray(xray_bin, node, local_port):
    config = gen_xray_config(node, local_port)
    fd, config_path = tempfile.mkstemp(suffix=".json", prefix="xray_bot_")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)
    try:
        proc = subprocess.Popen([xray_bin, "run", "-c", config_path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if proc.poll() is not None:
            return None, config_path
        return proc, config_path
    except Exception:
        return None, config_path


def stop_xray(proc, config_path):
    try:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        try: proc.kill()
        except Exception: pass
    try: os.unlink(config_path)
    except Exception: pass


def build_opener(local_port_or_url):
    """构建代理opener，支持本地端口(int)或直接HTTP代理URL(str)；None时直连"""
    if local_port_or_url is None:
        return urllib.request.build_opener()  # 直连，不使用代理
    if isinstance(local_port_or_url, int):
        proxy_url = f"http://127.0.0.1:{local_port_or_url}"
    else:
        proxy_url = local_port_or_url  # 如 http://user:pass@host:port
    proxy_handler = urllib.request.ProxyHandler({
        "http": proxy_url,
        "https": proxy_url
    })
    return urllib.request.build_opener(proxy_handler)


def test_proxy(local_port_or_url, timeout=15, token=None):
    """测试代理连通性：用实际的Bot API getMe请求，比HEAD根路径更可靠"""
    opener = build_opener(local_port_or_url)
    try:
        if token:
            url = f"https://api.telegram.org/bot{token}/getMe"
        else:
            url = "https://api.telegram.org"
        req = urllib.request.Request(url, method="GET")
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        if token:
            return data.get("ok", False)
        return resp.status == 200
    except Exception:
        return False


def api_get_updates(token, offset, local_port, timeout=30):
    """长轮询获取消息更新"""
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=25"
    opener = build_opener(local_port)
    try:
        resp = opener.open(url, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "description": str(e)}


def api_send_message(token, chat_id, text, local_port, timeout=15, parse_mode=None, reply_markup=None):
    """发送消息（支持parse_mode用于@用户等HTML/Markdown格式，支持inline keyboard）"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    data = urllib.parse.urlencode(payload).encode("utf-8")
    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "description": str(e)}


def api_delete_message(token, chat_id, message_id, local_port, timeout=15):
    """撤回消息"""
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "message_id": message_id}).encode("utf-8")
    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "description": str(e)}


# ============ 口令处理 ============

def cmd_help(history, chat_id):
    """显示所有口令帮助"""
    return """⚱️ 无良道士段德·口令簿

无量天尊！道友可用以下口令差遣贫道：

🎮 【按钮菜单】
  /menu 或 菜单 / 主菜单 / 按钮
     → 呼出功能按钮（签到/积分/提交爬虫/队列/口令簿）

💰 【积分系统】
  /sign 或 签到 / 每日签到 / 打卡
     → 每日签到，+5积分

  /points 或 积分 / 我的积分 / 查积分
     → 查询当前积分和累计签到天数

  ⚡ 积分规则：
     每日签到 +5 积分
     提交网址 +2 积分（每座，纯网址收录即得）
     立即掘穴 每座消耗 10 积分（发「爬虫+网址」）
     重复/困难网址 -1 积分
     群主/管理员 免费掘穴（仍可获得投穴奖励）

  🎩 拍卖行竞价：
     /bid 或 押积分 网址 积分数
        → 参与竞价，价高者得，1分钟押注倒计时
     /bidlist 或 竞价榜 / 拍卖行
        → 查看当前竞价排名
     规则：最低5分，最高100分，每日仅掘5座，超出者积分退还
     群主宝穴👑不可被顶，管理员可参与竞价

📜 【查询口令】
  /py 或 py / 源术 / py脚本
     → 列出所有已推送的四壳Spider源术

  /zip 或 小程序 / 微阁 / app
     → 列出所有已推送的蚂蚁小程序

  /list 或 列表 / 存货 / 所有
     → 列出所有宝穴及其全部明器

  /sites 或 站点 / 宝穴 / 目录
     → 列出所有已掘开的宝穴名称

🧹 【管理口令】
  /clean <宝穴名> 或 撤回 <宝穴名>
     → 撤回指定宝穴的所有旧消息

  /restart 或 重启 / 重启服务 / 重启所有服务
     → 重启全部服务（Bot/中央处理器/监控/排队/延迟调度）
     ⚠️ 仅限群主或管理员使用

📝 【问题反馈】
  直接发：<站点名> <问题描述>（如「lusi_av 无法获取分类」）
  引用推送消息 + 问题描述（如引用成品消息回复「播放失败」）
     → 自动收集问题点，下次任务触发时给AI修复
     （任何问题都收集，不限于预设关键词）

🔗 【网址触发·全自动待掘队列】
  群里发任何网址 → 自动加入待掘队列（@提出者确认，消耗10积分）
  /queue 或 队列/待处理/待掘
     → 列出所有待处理网址

  ⚠️ 主队列上限：2组（10座），满了暂存备用队列
  ⚠️ 每人每日：最多3个网址（管理员可豁免，联系群主添加）
  ⚠️ 全局每日：最多10个新站（铁律，满了等明天零点更新）
  ⚠️ 积分消耗：每座10积分（管理员免费）
  ℹ️ 修复任务不计入每日额度

  ⚡ 连接器全自动执行：每10分钟自动唤起会话，
     按队列顺序逐组施展四步流水线，
     掘开明器后自动上传坚果云并推送回本群，
     完成或失败都会@提交者告知结果，
     道友静候佳音即可，无需任何操作。

❓ /help 或 帮助 / 口令 / 指令
     → 调出本口令簿

—— 摸金校尉·无良道士段德"""


def cmd_py(history, chat_id):
    """列出所有py文件"""
    lines = [f"🔮 {pick_quote('push_done')}", ""]
    found = False
    for site, rec in sorted(history.items()):
        msg_ids = rec.get("message_ids", {})
        if "py" in msg_ids or "text" in msg_ids:
            found = True
            push_time = rec.get("last_push_time", "?")
            lines.append(f"📜 {site}")
            lines.append(f"   推送时辰: {push_time}")
            lines.append(f"   消息ID: {msg_ids.get('py', '未记录')}")
            lines.append("")
    if not found:
        lines.append("（暂无源术入库，待贫道掘开宝穴后自然有货）")
    lines.append("—— 段德 敬上")
    return "\n".join(lines)


def cmd_zip(history, chat_id):
    """列出所有小程序zip"""
    lines = [f"🗃️ {pick_quote('push_done')}", ""]
    found = False
    for site, rec in sorted(history.items()):
        msg_ids = rec.get("message_ids", {})
        if "zip" in msg_ids:
            found = True
            push_time = rec.get("last_push_time", "?")
            lines.append(f"🏯 {site}")
            lines.append(f"   推送时辰: {push_time}")
            lines.append(f"   消息ID: {msg_ids.get('zip', '未记录')}")
            lines.append("")
    if not found:
        lines.append("（暂无微阁入库）")
    lines.append("—— 段德 敬上")
    return "\n".join(lines)


def cmd_list(history, chat_id):
    """列出所有站点及其全部文件"""
    lines = [f"📦 {pick_quote('push_done')}", ""]
    if not history:
        lines.append("（库房空空如也，待贫道掘冢寻宝）")
    else:
        for site, rec in sorted(history.items()):
            msg_ids = rec.get("message_ids", {})
            push_time = rec.get("last_push_time", "?")
            files = []
            if "py" in msg_ids: files.append("🔮Spider源术")
            if "zip" in msg_ids: files.append("🗃️微阁洞天")
            if "text" in msg_ids: files.append("📜入库告示")
            lines.append(f"⚱️ {site}")
            lines.append(f"   时辰: {push_time}")
            lines.append(f"   明器: {'、'.join(files) if files else '无'}")
            lines.append("")
    lines.append(f"共计 {len(history)} 座宝穴")
    lines.append("—— 段德 敬上")
    return "\n".join(lines)


def cmd_sites(history, chat_id):
    """列出所有站点名"""
    lines = [f"🗺️ {pick_quote('push_done')}", ""]
    if not history:
        lines.append("（尚未掘开任何宝穴）")
    else:
        for i, (site, rec) in enumerate(sorted(history.items()), 1):
            push_time = rec.get("last_push_time", "?")
            lines.append(f"  {i}. ⚱️ {site}（{push_time}）")
    lines.append("")
    lines.append(f"共 {len(history)} 座宝穴")
    lines.append("—— 段德 敬上")
    return "\n".join(lines)


def cmd_clean(token, chat_id, text, local_port, history, history_path):
    """撤回指定站点的旧消息"""
    # 提取站点名（/clean 后面的内容，或"撤回"后面的内容）
    site_name = ""
    if text.startswith("/clean"):
        site_name = text[len("/clean"):].strip()
    elif "撤回" in text:
        idx = text.find("撤回")
        site_name = text[idx+2:].strip()

    if not site_name:
        return "⚠️ 请指定宝穴名，如：/clean 色花堂视频"

    if site_name not in history:
        return f"⚠️ 宝穴「{site_name}」无推送记录，无需撤回"

    rec = history[site_name]
    msg_ids = rec.get("message_ids", {})
    if not msg_ids:
        del history[site_name]
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return f"宝穴「{site_name}」历史记录为空，已清除"

    success = 0
    failed = 0
    for key, mid in msg_ids.items():
        r = api_delete_message(token, chat_id, mid, local_port)
        if r.get("ok"):
            success += 1
        else:
            failed += 1

    del history[site_name]
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return f"🧹 {pick_quote('clean_done')}\n宝穴「{site_name}」旧消息已撤回\n成功: {success}条, 失败: {failed}条\n历史记录已清除"


def load_pending(pending_path):
    """加载待处理网址队列"""
    if not os.path.isfile(pending_path):
        return []
    try:
        with open(pending_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_pending(pending_path, pending):
    """保存待处理网址队列"""
    try:
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 待处理队列保存失败: {e}")


# ==================== 队列上限 & 每日爬取额度（铁律） ====================
MAX_GROUPS = 2          # 主队列最多2组
GROUP_SIZE = 5          # 每组5个网址
MAX_QUEUE_SIZE = MAX_GROUPS * GROUP_SIZE  # 主队列最多10个待掘网址
MAX_DAILY_CRAWL = 5    # 每天最多爬取5个新网站（铁律，所有人包括群主都受此限制；修复任务不计入；达到上限后token告急暂停掘穴）
MAX_PER_USER_PER_DAY = 3  # 普通用户每人每天最多3个网址（管理员/群主豁免此限制，但仍受全局5个铁律限制）

DAILY_COUNT_FILE = os.path.join(SCRIPT_DIR, "daily_crawl_count.json")
USER_DAILY_QUOTA_FILE = os.path.join(SCRIPT_DIR, "user_daily_quota.json")  # 每人每日提交计数
URL_SUBMITTER_MAP = os.path.join(SCRIPT_DIR, "url_submitter_map.json")
BACKUP_QUEUE_FILE = os.path.join(SCRIPT_DIR, "tg_backup_queue.json")  # 备用队列（主队列满了暂存这里）
PROCESSED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "tg_processed_history.json")  # 处理历史（成功+失败，防重复）

# 管理员权限缓存（内存，避免每次入队都调TG API）
_admin_cache = {}
_ADMIN_CACHE_TTL = 3600  # 缓存1小时


def is_admin_cached(user_id, token, chat_id, local_port):
    """检查用户是否为群主/管理员（带缓存）"""
    if not user_id:
        return False
    import time as _time
    now_ts = _time.time()
    cache_key = str(user_id)
    if cache_key in _admin_cache:
        ts, result = _admin_cache[cache_key]
        if now_ts - ts < _ADMIN_CACHE_TTL:
            return result
    result = is_chat_admin(token, chat_id, user_id, local_port)
    _admin_cache[cache_key] = (now_ts, result)
    return result


def load_daily_count():
    """加载今日已爬取数量"""
    if not os.path.isfile(DAILY_COUNT_FILE):
        return {"date": "", "count": 0, "urls": []}
    try:
        with open(DAILY_COUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            today = datetime.now().strftime("%Y-%m-%d")
            if data.get("date") != today:
                return {"date": today, "count": 0, "urls": []}
            return data
    except Exception:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0, "urls": []}


def save_daily_count(data):
    """保存今日爬取计数"""
    try:
        with open(DAILY_COUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 每日计数文件写入失败: {e}")


def increment_daily_count(urls):
    """增加今日爬取计数"""
    data = load_daily_count()
    today = datetime.now().strftime("%Y-%m-%d")
    if data.get("date") != today:
        data = {"date": today, "count": 0, "urls": []}
    for url in urls:
        if url not in data.get("urls", []):
            data["urls"].append(url)
            data["count"] = data.get("count", 0) + 1
    save_daily_count(data)
    return data["count"]


def load_url_submitter_map():
    """加载网址→提交者映射"""
    if not os.path.isfile(URL_SUBMITTER_MAP):
        return {}
    try:
        with open(URL_SUBMITTER_MAP, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_url_submitter_map(mapping):
    """保存网址→提交者映射"""
    try:
        with open(URL_SUBMITTER_MAP, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 提交者映射文件写入失败: {e}")


def record_url_submitter(url, user_id, from_user):
    """记录网址的提交者（用于任务完成/失败时@通知）"""
    mapping = load_url_submitter_map()
    mapping[url] = {
        "user_id": str(user_id) if user_id else None,
        "from_user": from_user,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_url_submitter_map(mapping)


def load_backup_queue():
    """加载备用队列"""
    if not os.path.isfile(BACKUP_QUEUE_FILE):
        return []
    try:
        with open(BACKUP_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_backup_queue(queue):
    """保存备用队列"""
    try:
        with open(BACKUP_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 备用队列写入失败: {e}")


def add_to_backup(url, from_user, user_id):
    """将网址加入备用队列（FIFO）"""
    queue = load_backup_queue()
    # 去重
    if any(item.get("url") == url for item in queue):
        return False
    queue.append({
        "url": url,
        "from_user": from_user,
        "user_id": str(user_id) if user_id else None,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_backup_queue(queue)
    return True


def move_backup_to_main(bot_sync_path, available_slots):
    """
    将备用队列中的网址移到主队列（Bot同步文件）。
    返回移动的数量和移动的网址列表。
    """
    if available_slots <= 0:
        return 0, []
    backup = load_backup_queue()
    if not backup:
        return 0, []

    # 读取当前同步文件
    try:
        if os.path.isfile(bot_sync_path):
            with open(bot_sync_path, "r", encoding="utf-8") as f:
                sync_list = json.load(f)
        else:
            sync_list = []
    except Exception:
        sync_list = []

    moved = []
    to_move = min(available_slots, len(backup))
    for i in range(to_move):
        item = backup.pop(0)  # FIFO
        url = item["url"]
        if not any(s.get("url") == url for s in sync_list):
            sync_list.append({
                "url": url,
                "from_user": item.get("from_user", "unknown"),
                "user_id": item.get("user_id"),
                "time": item.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            })
            moved.append(url)

    try:
        with open(bot_sync_path, "w", encoding="utf-8") as f:
            json.dump(sync_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 同步文件写入失败: {e}")

    save_backup_queue(backup)
    return len(moved), moved


def build_user_mention(user_id, from_user):
    """构建@用户的HTML链接（用于消息中@提出者）"""
    if user_id:
        return f'<a href="tg://user?id={user_id}">{from_user}</a>'
    return from_user


# ==================== 处理历史（防重复）& 困难站点预检 ====================

def load_processed_history():
    if not os.path.isfile(PROCESSED_HISTORY_FILE):
        return {"success": {}, "failed": {}}
    try:
        with open(PROCESSED_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("success", {})
            data.setdefault("failed", {})
            return data
    except Exception:
        return {"success": {}, "failed": {}}


def save_processed_history(data):
    try:
        with open(PROCESSED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 处理历史写入失败: {e}")


def check_url_processed(url):
    history = load_processed_history()
    if url in history["success"]:
        info = history["success"][url]
        return True, "success", info.get("reason", "已掘开"), info.get("site_name", "")
    if url in history["failed"]:
        info = history["failed"][url]
        return True, "failed", info.get("reason", "掘穴失败"), info.get("site_name", "")
    url_norm = url.rstrip("/").lower().replace("www.", "")
    for stored_url, info in history["success"].items():
        if stored_url.rstrip("/").lower().replace("www.", "") == url_norm:
            return True, "success", info.get("reason", "已掘开"), info.get("site_name", "")
    for stored_url, info in history["failed"].items():
        if stored_url.rstrip("/").lower().replace("www.", "") == url_norm:
            return True, "failed", info.get("reason", "掘穴失败"), info.get("site_name", "")
    return False, None, None, None


# 已知CF盾/高防站点（入队直接拒绝）
KNOWN_CF_SITES = ["missav", "freepornvideos"]
# 已知导航/目录站
KNOWN_NAV_SITES = ["shturl.cc", "shturl"]


def precheck_hard_site(url):
    url_lower = url.lower()
    for cf in KNOWN_CF_SITES:
        if cf in url_lower:
            return True, f"此宝穴布有Cloudflare天盾（{cf}级别，与missav同级），贫道一时破不开，道友另寻他穴"
    for nav in KNOWN_NAV_SITES:
        if nav in url_lower:
            return True, "此乃导航/目录站，只列外部站点链接，无自有视频分类与播放地址，无法开发四壳Spider"
    import re as _re_hard
    if _re_hard.search(r'(for sale|domain for sale|此域名出售|域名停放|parked domain)', url_lower):
        return True, "此域名尚在停放售卖，无实质内容，无法掘穴"
    if _re_hard.search(r'(daohang|mulu|/nav|/directory|/links|网址导航|导航站|目录站)', url_lower):
        return True, "此乃导航/目录站，只列外部链接，无自有视频，无法开发四壳Spider"
    return False, None


def build_processed_rejection(url, status, reason, site_name, mention):
    if status == "success":
        site_display = site_name or url[:50]
        return (
            f"🔔 无量天尊！{mention} 道友，此宝穴已然掘开过了！\n\n"
            f"⚱️ 宝穴：{site_display}\n"
            f"🔗 网址：{url}\n"
            f"✅ 状态：已掘开，明器已推送入群\n\n"
            f"无需重复掘穴，道友可往群文件中寻此明器。\n"
            f"若明器有瑕疵，可直接反馈问题，贫道重炼便是！\n\n"
            f"—— 摸金校尉·无良道士段德"
        )
    else:
        reason_lower = (reason or "").lower()
        if "cloudflare" in reason_lower or "cf" in reason_lower or "盾" in reason:
            detail = "此宝穴布有Cloudflare天盾，与missav同级，贫道一时破不开"
        elif "导航" in reason or "目录" in reason or "nav" in reason_lower:
            detail = "此乃导航/目录站，只列外部链接，无自有视频，无法开发四壳Spider"
        elif "停放" in reason or "售卖" in reason or "sale" in reason_lower:
            detail = "此域名尚在停放售卖，无实质内容，无法掘穴"
        elif "超时" in reason or "连接" in reason or "timeout" in reason_lower:
            detail = "此宝穴已然坍塌，连接不通，无法掘开"
        else:
            detail = reason or "此前掘穴失败，原因不明"
        return (
            f"⚠️ 无量天尊！{mention} 道友，此宝穴此前掘过，折戟了！\n\n"
            f"⚱️ 宝穴：{url[:60]}\n"
            f"❌ 失败原因：{detail}\n\n"
            f"此等难处之穴，贫道不再重复掘取，道友另寻他穴罢！\n"
            f"若确有把握，可@群主说明，由群主定夺是否破格再试。\n\n"
            f"—— 摸金校尉·无良道士段德"
        )


def load_user_daily_quota():
    """加载每人每日配额记录"""
    if not os.path.isfile(USER_DAILY_QUOTA_FILE):
        return {}
    try:
        with open(USER_DAILY_QUOTA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_daily_quota(data):
    """保存每人每日配额记录"""
    try:
        with open(USER_DAILY_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 用户配额文件写入失败: {e}")


def get_user_today_count(user_id):
    """获取某用户今天已提交的新站数量"""
    if not user_id:
        return 0
    data = load_user_daily_quota()
    today = datetime.now().strftime("%Y-%m-%d")
    record = data.get(str(user_id), {})
    if record.get("date") == today:
        return record.get("count", 0)
    return 0


def increment_user_daily_count(user_id, from_user, count=1):
    """增加某用户今天的新站提交计数"""
    if not user_id:
        return 0
    data = load_user_daily_quota()
    today = datetime.now().strftime("%Y-%m-%d")
    key = str(user_id)
    record = data.get(key, {})
    if record.get("date") != today:
        record = {"date": today, "count": 0, "from_user": from_user}
    record["count"] = record.get("count", 0) + count
    record["from_user"] = from_user
    data[key] = record
    save_user_daily_quota(data)
    return record["count"]


# ==================== 本地智能问答（不调用豆包AI，纯关键词匹配，仅群主可触发） ====================
SMART_QA_FILE = os.path.join(SCRIPT_DIR, "smart_qa.json")

def load_smart_qa():
    """加载智能问答库"""
    try:
        with open(SMART_QA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"qa_pairs": []}

def save_smart_qa(data):
    """保存智能问答库"""
    try:
        with open(SMART_QA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[警告] 智能问答库保存失败: {e}")
        return False

def match_smart_qa(text):
    """关键词匹配智能问答，返回最佳匹配的答案（匹配度最高的）。
    匹配规则：消息中包含任意一个关键词即匹配，匹配关键词数量越多优先级越高"""
    if not text:
        return None
    qa_data = load_smart_qa()
    qa_pairs = qa_data.get("qa_pairs", [])
    if not qa_pairs:
        return None

    text_lower = text.strip().lower()
    best_match = None
    best_score = 0

    for qa in qa_pairs:
        keywords = qa.get("keywords", [])
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_match = qa

    if best_match and best_score > 0:
        return best_match.get("answer")
    return None

def handle_smart_qa_command(text, user_id, token, chat_id, local_port):
    """处理群主的智能问答管理口令：/qa_add /qa_del /qa_list /qa
    返回(回复文本, 是否处理了)"""
    text_lower = text.strip().lower()
    text_stripped = text.strip()

    # /qa_list 列出所有问答
    if text_lower in ("/qa_list", "问答列表", "问答库", "所有问答") or text_lower.startswith("/qa_list"):
        qa_data = load_smart_qa()
        qa_pairs = qa_data.get("qa_pairs", [])
        if not qa_pairs:
            return ("📭 智能问答库为空，群主可用 /qa_add 添加问答。", True)
        lines = [f"📚 智能问答库（共{len(qa_pairs)}条，仅群主可触发）", ""]
        for qa in qa_pairs:
            qid = qa.get("id", "?")
            kws = "、".join(qa.get("keywords", [])[:3])
            lines.append(f"  [{qid}] 关键词: {kws}")
        lines.append("")
        lines.append("管理口令：")
        lines.append("  /qa_add 关键词1,关键词2|答案内容")
        lines.append("  /qa_del 编号")
        return ("\n".join(lines), True)

    # /qa_add 添加问答
    if text_lower.startswith("/qa_add") or text_stripped.startswith("添加问答"):
        # 格式：/qa_add 关键词1,关键词2|答案内容
        content = text_stripped[len("/qa_add"):].strip() if text_lower.startswith("/qa_add") else text_stripped[len("添加问答"):].strip()
        if "|" not in content:
            return ("⚠️ 格式错误！正确格式：\n/qa_add 关键词1,关键词2|答案内容", True)
        parts = content.split("|", 1)
        keywords_str = parts[0].strip()
        answer = parts[1].strip()
        if not keywords_str or not answer:
            return ("⚠️ 关键词和答案都不能为空！", True)
        keywords = [k.strip() for k in keywords_str.replace("，", ",").split(",") if k.strip()]

        qa_data = load_smart_qa()
        qa_pairs = qa_data.get("qa_pairs", [])
        new_id = max([qa.get("id", 0) for qa in qa_pairs], default=0) + 1
        qa_pairs.append({
            "id": new_id,
            "keywords": keywords,
            "answer": answer
        })
        qa_data["qa_pairs"] = qa_pairs
        if save_smart_qa(qa_data):
            return (f"✅ 已添加问答 [{new_id}]\n关键词: {'、'.join(keywords)}\n答案: {answer[:50]}...", True)
        else:
            return ("❌ 保存失败，请检查文件权限。", True)

    # /qa_del 删除问答
    if text_lower.startswith("/qa_del") or text_stripped.startswith("删除问答"):
        content = text_stripped[len("/qa_del"):].strip() if text_lower.startswith("/qa_del") else text_stripped[len("删除问答"):].strip()
        try:
            del_id = int(content)
        except ValueError:
            return ("⚠️ 请指定要删除的问答编号，如：/qa_del 1", True)

        qa_data = load_smart_qa()
        qa_pairs = qa_data.get("qa_pairs", [])
        new_pairs = [qa for qa in qa_pairs if qa.get("id") != del_id]
        if len(new_pairs) == len(qa_pairs):
            return (f"⚠️ 未找到编号为 {del_id} 的问答。", True)
        qa_data["qa_pairs"] = new_pairs
        if save_smart_qa(qa_data):
            return (f"✅ 已删除问答 [{del_id}]", True)
        else:
            return ("❌ 保存失败。", True)

    return (None, False)


# ==================== 摇骰子排号（token告急时群员可摇骰子排号，次日按序号优先掘穴） ====================
ROLL_RANK_FILE = os.path.join(SCRIPT_DIR, "roll_rank.json")

def load_roll_rank():
    """加载摇骰子排名（自动按日期重置）"""
    try:
        with open(ROLL_RANK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") != today:
            # 日期不对，重置
            return {"date": today, "rankings": []}
        return data
    except Exception:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "rankings": []}

def save_roll_rank(data):
    """保存摇骰子排名"""
    try:
        with open(ROLL_RANK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[警告] 摇骰子排名保存失败: {e}")
        return False

def handle_roll(user_id, from_user):
    """处理摇骰子排号：生成1-100随机数，序号小的优先掘穴。每人每天只能摇一次。"""
    data = load_roll_rank()
    rankings = data.get("rankings", [])

    # 检查是否已摇过
    existing = next((r for r in rankings if r.get("user_id") == str(user_id)), None)
    if existing:
        return (
            f"🎲 {build_user_mention(user_id, from_user)} 道友今日已摇过骰子！\n\n"
            f"🎯 道友的序号：{existing['roll']} 号\n"
            f"📊 当前排名：第 {get_roll_position(user_id, rankings)} 位\n\n"
            f"⏰ 每日零点重置，明日可再摇！\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

    # 生成1-100随机数
    import random as _random
    roll_num = _random.randint(1, 100)

    rankings.append({
        "user_id": str(user_id),
        "from_user": from_user,
        "roll": roll_num,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    # 按序号从小到大排序
    rankings.sort(key=lambda x: x["roll"])
    data["rankings"] = rankings
    save_roll_rank(data)

    position = get_roll_position(user_id, rankings)

    return (
        f"🎲 无量天尊！{build_user_mention(user_id, from_user)} 道友掷骰问天命——\n\n"
        f"🎯 骰子翻滚，落定：**{roll_num}** 号！\n"
        f"📊 当前排名：第 {position} 位（共 {len(rankings)} 人参与排号）\n\n"
        f"⚡ 明日令牌重置后，贫道按序号从小到大依次掘穴\n"
        f"   序号越小，优先级越高！\n\n"
        f"⏰ 每人每日限摇一次，零点重置\n\n"
        f"—— 摸金校尉·无良道士段德"
    )

def get_roll_position(user_id, rankings):
    """获取用户在排名中的位置（从1开始）"""
    for i, r in enumerate(rankings):
        if r.get("user_id") == str(user_id):
            return i + 1
    return len(rankings) + 1

def get_roll_rank_text():
    """获取当前摇骰子排名文本"""
    data = load_roll_rank()
    rankings = data.get("rankings", [])
    if not rankings:
        return "📭 今日暂无道友摇骰子排号。\n\n发送「摇骰子」即可参与排号，明日按序号优先掘穴！"

    lines = [f"🎲 今日摇骰子排号榜（共 {len(rankings)} 人参与）", ""]
    lines.append("（序号越小，明日掘穴优先级越高）")
    lines.append("")
    for i, r in enumerate(rankings[:20]):  # 最多显示前20名
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"  {i+1}."
        lines.append(f"{medal} {r.get('from_user', '?')} — {r['roll']}号")
    if len(rankings) > 20:
        lines.append(f"  ... 等共 {len(rankings)} 人")
    lines.append("")
    lines.append("发送「摇骰子」参与排号，每日零点重置")
    return "\n".join(lines)


# ==================== 积分竞价系统（拍卖行模式，价高者得，段德人设） ====================
BID_QUEUE_FILE = os.path.join(SCRIPT_DIR, "bid_queue.json")
MAX_BID_POINTS = 100  # 单次最高押注100积分
MIN_BID_POINTS = 5    # 最低押注5积分

def load_bid_queue():
    """加载竞价队列"""
    try:
        with open(BID_QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") != today:
            return {"date": today, "bids": []}
        return data
    except Exception:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "bids": []}

def save_bid_queue(data):
    """保存竞价队列"""
    try:
        with open(BID_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[警告] 竞价队列保存失败: {e}")
        return False

def get_bid_for_url(url):
    """获取某个网址的竞价信息"""
    data = load_bid_queue()
    for bid in data.get("bids", []):
        if bid.get("url") == url:
            return bid
    return None

def place_bid(url, user_id, from_user, bid_points, is_owner=False):
    """押积分竞价（拍卖行模式，价高者得）
    返回(是否成功, 消息文本)"""
    # 检查积分
    user_points = get_user_points(user_id)
    if user_points < bid_points:
        return (False, (
            f"⚠️ 无量天尊！{build_user_mention(user_id, from_user)} 道友且慢——\n\n"
            f"💰 道友当前积分：{user_points} 分\n"
            f"🎯 道友欲押：{bid_points} 分\n\n"
            f"💸 积分不足，此宝穴贫道不能替道友押下！\n"
            f"   道友可先签到得5分，或提交网址得2分，积少成多！\n\n"
            f"—— 摸金校尉·无良道士段德"
        ))

    data = load_bid_queue()
    bids = data.get("bids", [])

    # 检查是否已存在该网址的竞价
    existing = next((b for b in bids if b.get("url") == url), None)
    if existing:
        old_bid = existing.get("bid", 0)
        if bid_points <= old_bid:
            return (False, (
                f"⚠️ 无量天尊！{build_user_mention(user_id, from_user)} 道友且慢——\n\n"
                f"🎯 此宝穴当前已押：{old_bid} 分\n"
                f"💰 道友欲押：{bid_points} 分\n\n"
                f"📜 拍卖行规矩，价高者得！\n"
                f"   道友若要加价，需押高于 {old_bid} 分方可！\n\n"
                f"—— 摸金校尉·无良道士段德"
            ))
        # 加价：退还旧积分，扣除新积分
        add_user_points(user_id, from_user, old_bid, reason=f"竞价加价退还旧押注x{old_bid}")
        consume_user_points(user_id, bid_points)
        existing["bid"] = bid_points
        existing["bid_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing["from_user"] = from_user
        deadline = existing.get("bid_deadline")
        save_bid_queue(data)
        return (True, build_bid_success_text(url, from_user, bid_points, old_bid, is_owner, is_increase=True, deadline=deadline))
    else:
        # 新竞价：设置1分钟押注截止时间
        from datetime import timedelta as _td
        deadline = (datetime.now() + _td(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        consume_user_points(user_id, bid_points)
        bids.append({
            "url": url,
            "user_id": str(user_id),
            "from_user": from_user,
            "bid": bid_points,
            "bid_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bid_deadline": deadline,
            "is_owner": is_owner
        })
        data["bids"] = bids
        save_bid_queue(data)
        return (True, build_bid_success_text(url, from_user, bid_points, 0, is_owner, is_increase=False, deadline=deadline))

def build_bid_success_text(url, from_user, bid_points, old_bid, is_owner, is_increase=False, deadline=None):
    """构建押积分成功的段德风格话术（拍卖行模式，1分钟押注倒计时）"""
    mention = build_user_mention(None, from_user)
    if is_increase:
        action_text = f"💰 加价成功！{old_bid}分 → {bid_points}分"
    else:
        action_text = f"💰 押注成功！{bid_points}分"

    # 计算剩余押注时间
    countdown_text = ""
    if deadline:
        try:
            deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            remaining = (deadline_dt - datetime.now()).total_seconds()
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                countdown_text = f"\n⏳ 押注倒计时：{mins}分{secs}秒（时间到价高者得）\n"
            else:
                countdown_text = "\n⏰ 押注时间已到，价高者得！\n"
        except Exception:
            pass

    # 获取当前竞价排名
    rank_text = get_bid_rank_text_for_url(url)

    return (
        f"🎩 无量天尊！{mention} 道友一掷千金，贫道这便记下！\n\n"
        f"⛏️ 宝穴：{url}\n"
        f"{action_text}\n"
        f"{countdown_text}\n"
        f"📜 拍卖行规矩，价高者得！\n"
        f"   道友押的积分越高，掘穴优先级越靠前！\n"
        f"   每日仅掘5座，超出者积分原路退还。\n\n"
        f"{rank_text}\n"
        f"⚡ 道友且宽心坐等，价高者先得！\n\n"
        f"—— 摸金校尉·无良道士段德"
    )

def get_bid_rank_text_for_url(url):
    """获取某个网址在竞价队列中的排名文本"""
    data = load_bid_queue()
    bids = data.get("bids", [])
    if not bids:
        return ""

    # 按押积分从高到低排序，相同积分按时间早的优先
    sorted_bids = sorted(bids, key=lambda x: (-x.get("bid", 0), x.get("bid_time", "")))

    # 找到当前网址的排名
    rank = 0
    for i, b in enumerate(sorted_bids):
        if b.get("url") == url:
            rank = i + 1
            break

    if rank == 0:
        return ""

    total = len(sorted_bids)
    if rank <= 5:
        status = "🔥 当前排名前5，今日必掘！"
    else:
        status = f"📊 当前排名第{rank}/{total}，每日仅掘5座，道友可继续加价！"

    # 显示前5名
    lines = [f"🏆 当前竞价榜（前5名）："]
    for i, b in enumerate(sorted_bids[:5]):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"  {i+1}."
        marker = " 👑" if b.get("is_owner") else ""
        lines.append(f"{medal} {b.get('from_user', '?')}{marker} — {b.get('bid', 0)}分")
    lines.append("")
    lines.append(status)
    return "\n".join(lines)

def get_bid_rank_text():
    """获取完整竞价排名文本（用于/竞价榜口令）"""
    data = load_bid_queue()
    bids = data.get("bids", [])
    if not bids:
        return (
            f"📭 今日暂无道友参与竞价！\n\n"
            f"🎩 拍卖行已开张，道友若有中意之宝穴，\n"
            f"   发「押积分 网址 积分数」即可参与竞价！\n"
            f"   价高者得，每日仅掘5座！\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

    sorted_bids = sorted(bids, key=lambda x: (-x.get("bid", 0), x.get("bid_time", "")))

    lines = [f"🎩 今日竞价拍卖行（共 {len(sorted_bids)} 件宝穴上拍）", ""]
    lines.append("（价高者得，每日仅掘5座，超出者积分退还）")
    lines.append("")
    for i, b in enumerate(sorted_bids[:15]):
        if i < 5:
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔥"
            status = "✅今日必掘"
        else:
            medal = f"  {i+1}."
            status = "⏳待加价"
        marker = "👑" if b.get("is_owner") else ""
        lines.append(f"{medal} {b.get('from_user', '?')}{marker} — {b.get('bid', 0)}分 [{status}]")
        lines.append(f"     {b.get('url', '')[:50]}")
    if len(sorted_bids) > 15:
        lines.append(f"  ... 等共 {len(sorted_bids)} 件")
    lines.append("")
    lines.append("发「押积分 网址 积分数」参与竞价，最低5分，最高100分")
    return "\n".join(lines)

def handle_bid_command(text, user_id, from_user, token, chat_id, local_port):
    """处理押积分口令：押积分 网址 积分数 / /bid 网址 积分数"""
    text_stripped = text.strip()

    # 解析格式：押积分 网址 积分数
    import re as _re
    pattern = _re.compile(r'^(?:押积分|竞价|/bid|出价)\s+(https?://\S+)\s+(\d+)', _re.IGNORECASE)
    match = pattern.search(text_stripped)
    if not match:
        return (
            f"⚠️ 无量天尊！道友格式有误！\n\n"
            f"🎩 正确格式：押积分 网址 积分数\n"
            f"   示例：押积分 https://example.com 20\n\n"
            f"📜 拍卖行规矩：\n"
            f"   • 最低押注5分，最高100分\n"
            f"   • 价高者得，每日仅掘5座\n"
            f"   • 超出者积分原路退还\n"
            f"   • 群主宝穴不可被顶（👑标记）\n\n"
            f"发「竞价榜」查看当前排名\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

    url = match.group(1)
    try:
        bid_points = int(match.group(2))
    except ValueError:
        return ("⚠️ 积分数必须是数字！", None)

    if bid_points < MIN_BID_POINTS:
        return (f"⚠️ 最低押注 {MIN_BID_POINTS} 分！", None)
    if bid_points > MAX_BID_POINTS:
        return (f"⚠️ 最高押注 {MAX_BID_POINTS} 分！", None)

    # 检查是否群主
    is_owner = False
    if token and local_port and user_id:
        try:
            is_owner = is_owner_cached(user_id, token, chat_id, local_port)
        except Exception:
            is_owner = False

    success, msg = place_bid(url, user_id, from_user, bid_points, is_owner=is_owner)
    return msg


def handle_115_qrcode(user_id, from_user, chat_id, token, local_port):
    """115网盘扫码登录：生成二维码图片私发给用户，后台等待扫码保存Cookie
    Cookie长期有效，已登录时提示不需要重新扫码"""
    import threading
    import tempfile
    import json
    import requests

    # 先检查Cookie是否存在且有效（多用户：按user_id独立保存）
    cookie_path = os.path.join(SCRIPT_DIR, f"115_cookies_{user_id}.json")
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cookies = cfg.get("cookies", {})
            login_time = cfg.get("login_time", "?")

            if cookies:
                # 验证Cookie是否有效
                session = requests.Session()
                session.cookies.update(cookies)
                session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://115.com/",
                })
                try:
                    resp = session.get("https://115.com/?ct=user&ac=user&op=info", timeout=10)
                    data = resp.json()
                    if data.get("state"):
                        user_info = data.get("data", {})
                        user_name = user_info.get("user_name", "?")
                        mobile = user_info.get("mobile", "?")
                        print(f"[115] Cookie有效，用户已登录: {user_name}")
                        # Cookie有效，提示不需要重新扫码
                        try:
                            api_send_message(token, user_id,
                                f"✅ 无量天尊！{from_user} 道友，115网盘已登录！\n\n"
                                f"👤 账号: {user_name} ({mobile})\n"
                                f"📅 登录时间: {login_time}\n"
                                f"🔑 Cookie长期有效，无需重复扫码。\n\n"
                                f"现在可以直接转发磁力链接给我，自动离线下载到115网盘。\n\n"
                                f"—— 摸金校尉·无良道士段德",
                                local_port)
                        except Exception as e:
                            print(f"[115] 发送已登录提示失败: {e}")
                        return
                except Exception as e:
                    print(f"[115] Cookie验证异常，重新扫码: {e}")
        except Exception as e:
            print(f"[115] 读取Cookie异常，重新扫码: {e}")

    def _send_115_message(text):
        """内部函数：发送文字消息到用户私聊"""
        try:
            api_send_message(token, user_id, text, local_port)  # 私发给用户
        except Exception as e:
            print(f"[115] 发送消息失败: {e}")

    def _wait_for_scan(token_data):
        """后台线程：等待用户扫码，扫码成功后保存Cookie
        token_data: 完整的扫码数据（包含uid、time、sign）"""
        try:
            from p115qrcode import qrcode_status, qrcode_result
            import time

            uid = token_data.get("uid", "")
            print(f"[115] 开始等待扫码，uid={uid[:20]}...")
            print(f"[115] 完整扫码数据已保存: uid={uid[:16]}... time={token_data.get('time')} sign={token_data.get('sign','')[:16]}...")
            start_time = time.time()
            error_count = 0

            while time.time() - start_time < 120:  # 最多等2分钟
                try:
                    # qrcode_status需要完整的payload（uid+time+sign），不能只传uid
                    status_data = qrcode_status(token_data)
                    # qrcode_status返回dict
                    if isinstance(status_data, dict):
                        # 检查是否过期/无效
                        if not status_data.get("state", True) or status_data.get("code") == 40199002:
                            print(f"[115] 二维码已过期/无效，退出轮询: {status_data.get('message', '')}")
                            return
                        status = status_data.get("status", 0)
                    else:
                        status = 0

                    error_count = 0  # 成功请求，重置错误计数

                    # status: 0=等待扫码, 1=已扫码待确认, 2=确认成功
                    if status == 1:
                        print("[115] 已扫码，等待确认...")
                    elif status == 2:
                        # 扫码确认成功，获取Cookie（需要uid和app参数）
                        print("[115] 扫码确认成功，获取Cookie...")
                        
                        # 尝试多种app参数获取Cookie
                        cookies = {}
                        result = None
                        for try_app in ['web', 'android', 'alipaymini', 'desktop']:
                            try:
                                print(f"[115] 尝试 qrcode_result app={try_app}...")
                                result = qrcode_result(uid, app=try_app)
                                print(f"[115] qrcode_result({try_app}) 返回: {str(result)[:300]}")
                                
                                # 从多种位置提取cookies
                                if isinstance(result, dict):
                                    # 方式1: 直接cookies字段（复数）
                                    if result.get("cookies"):
                                        cookies = result["cookies"]
                                        print(f"[115] 从result.cookies获取到Cookie: {len(cookies)}个")
                                        break
                                    # 方式2: cookie字段（单数，115实际返回的字段名）
                                    if result.get("cookie"):
                                        cookies = result["cookie"]
                                        print(f"[115] 从result.cookie获取到Cookie: {len(cookies)}个")
                                        break
                                    # 方式3: data.cookies
                                    data = result.get("data", {})
                                    if isinstance(data, dict) and data.get("cookies"):
                                        cookies = data["cookies"]
                                        print(f"[115] 从result.data.cookies获取到Cookie: {len(cookies)}个")
                                        break
                                    # 方式4: data.cookie（单数）
                                    if isinstance(data, dict) and data.get("cookie"):
                                        cookies = data["cookie"]
                                        print(f"[115] 从result.data.cookie获取到Cookie: {len(cookies)}个")
                                        break
                                    # 方式5: 整个返回就是cookies
                                    if all(isinstance(v, str) for v in result.values()) and len(result) > 2:
                                        cookies = result
                                        print(f"[115] 整个返回就是Cookie: {len(cookies)}个")
                                        break
                            except Exception as e:
                                print(f"[115] qrcode_result({try_app}) 异常: {str(e)[:200]}")
                                continue
                        
                        if cookies:
                            # 保存Cookie
                            config = {
                                "cookies": cookies,
                                "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "user": from_user,
                                "token_data": token_data  # 保存完整扫码数据
                            }
                            config_path = os.path.join(SCRIPT_DIR, f"115_cookies_{user_id}.json")
                            with open(config_path, "w", encoding="utf-8") as f:
                                json.dump(config, f, ensure_ascii=False, indent=2)
                            print(f"[115] Cookie已保存到 {config_path}")
                            print(f"[115] Cookie数量: {len(cookies)}")
                            _send_115_message(
                                f"✅ 无量天尊！{from_user} 道友，115网盘登录成功！\n\n"
                                f"📦 Cookie已保存，现在可以使用磁力离线下载功能了。\n"
                                f"   转发含磁力链接的消息给我，即可自动离线下载到115网盘。\n\n"
                                f"—— 摸金校尉·无良道士段德"
                            )
                            return
                        else:
                            # 打印最后一次result帮助调试
                            if result:
                                print(f"[115] 最终返回值: {json.dumps(result, ensure_ascii=False)[:500]}")
                            _send_115_message("❌ 扫码成功但未获取到Cookie，请重试。")
                            return
                except Exception as e:
                    error_count += 1
                    err_str = str(e)
                    # 检测二维码过期/无效，立即退出
                    if "key invalid" in err_str or "40199002" in err_str or "过期" in err_str:
                        print(f"[115] 二维码已过期，退出轮询: {err_str[:80]}")
                        return
                    print(f"[115] 轮询异常({error_count}/5): {err_str[:100]}")
                    if error_count >= 5:
                        print("[115] 连续错误5次，退出轮询")
                        return
                time.sleep(2)

            # 超时
            print("[115] 扫码超时")
            _send_115_message("⏰ 二维码已过期，请重新发「二维码」生成新的二维码。")

        except Exception as e:
            print(f"[115] 等待扫码线程异常: {e}")
            try:
                _send_115_message(f"❌ 扫码登录异常: {e}")
            except Exception:
                pass

    # 主流程：生成二维码
    try:
        print(f"[115] 用户 {from_user}({user_id}) 请求扫码登录")

        # 先发送文字提示
        _send_115_message(
            f"🎫 无量天尊！{from_user} 道友，115网盘扫码登录：\n\n"
            f"正在生成二维码，请稍候..."
        )

        # 生成二维码token（用web网页版，115手机APP扫码登录）
        from p115qrcode import qrcode_token
        token_data = qrcode_token(app='web')
        uid = token_data.get("uid", "")
        # 使用115官方扫码协议链接（https://115.com/scan/dg-xxx），而不是二维码图片URL
        qr_content = token_data.get("qrcode", "") or f"https://115.com/scan/dg-{uid}"

        if not uid or not qr_content:
            _send_115_message("❌ 生成二维码失败，请重试。")
            return

        print(f"[115] 二维码内容: {qr_content[:60]}...")

        # 用115扫码协议链接生成二维码图片
        import qrcode
        qr_img = qrcode.make(qr_content)
        qr_file = os.path.join(tempfile.gettempdir(), f"115_qrcode_{uid[:8]}.png")
        qr_img.save(qr_file)
        print(f"[115] 二维码图片已生成: {qr_file}")

        # 私发二维码图片给用户
        caption = (
            f"🎫 115网盘扫码登录\n\n"
            f"请用115手机APP扫描上方二维码\n"
            f"扫码后在手机上确认登录\n\n"
            f"⏰ 二维码有效期2分钟\n"
            f"如过期请重新发「二维码」\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

        # 用TG API发送图片
        import requests as _req
        # local_port可能是完整代理URL(http://127.0.0.1:10809)或纯端口号(10809)
        if local_port:
            if str(local_port).startswith("http"):
                _proxy_url = str(local_port)
            else:
                _proxy_url = f"http://127.0.0.1:{local_port}"
            proxies = {"http": _proxy_url, "https": _proxy_url}
        else:
            proxies = None

        # 发送二维码图片，最多重试3次
        send_ok = False
        for retry in range(3):
            try:
                with open(qr_file, "rb") as f:
                    resp = _req.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": user_id, "caption": caption},
                        files={"photo": f},
                        proxies=proxies,
                        timeout=30,
                        verify=False  # 跳过SSL验证，避免代理SSL错误
                    )
                result = resp.json()
                if result.get("ok"):
                    print(f"[115] 二维码已私发给用户 {user_id} (第{retry+1}次尝试)")
                    send_ok = True
                    break
                else:
                    print(f"[115] 发送二维码失败(第{retry+1}次): {result.get('description')}")
            except Exception as e:
                print(f"[115] 发送二维码异常(第{retry+1}次): {str(e)[:100]}")
            import time as _t
            _t.sleep(2)

        if not send_ok:
            _send_115_message("❌ 发送二维码失败，请重试。")
            return

        # 清理临时文件
        try:
            os.remove(qr_file)
        except Exception:
            pass

        # 启动后台线程等待扫码（传入完整token_data，包含uid+time+sign）
        t = threading.Thread(target=_wait_for_scan, args=(token_data,), daemon=True)
        t.start()
        print("[115] 后台等待扫码线程已启动")

    except Exception as e:
        print(f"[115] 生成二维码异常: {e}")
        import traceback
        traceback.print_exc()
        _send_115_message(f"❌ 生成二维码异常: {e}")


def handle_magnet_115(text, user_id, from_user, token, chat_id, local_port):
    """115网盘磁力离线下载（广播模式）：提取磁力/迅雷链接，提交到所有已登录用户的115网盘"""
    import re
    import json
    import requests
    import glob
    import base64

    # 先去掉换行和空格，拼接被分割的链接
    text_clean = re.sub(r'[\r\n]+', '', text)
    text_clean = re.sub(r'\s+', '', text_clean)

    # 优先提取磁力链接的info_hash（40位十六进制）
    hash_pattern = re.compile(r'magnet:\?xt=urn:btih:([a-zA-Z0-9]{40})', re.IGNORECASE)
    hash_match = hash_pattern.search(text_clean)

    download_url = None
    link_type = None

    if hash_match:
        # 磁力链接
        info_hash = hash_match.group(1).upper()
        download_url = f"magnet:?xt=urn:btih:{info_hash}"
        link_type = "磁力"
        print(f"[115] 检测到磁力链接，info_hash={info_hash[:16]}...，发送者={from_user}")
    else:
        # 尝试提取迅雷链接（thunder://），Base64解码得到真实URL
        thunder_pattern = re.compile(r'thunder://([a-zA-Z0-9+/=]+)', re.IGNORECASE)
        thunder_match = thunder_pattern.search(text_clean)
        if thunder_match:
            try:
                encoded = thunder_match.group(1)
                # Base64解码
                decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
                # 迅雷链接格式：AA + 真实URL + ZZ
                if decoded.startswith('AA') and decoded.endswith('ZZ'):
                    real_url = decoded[2:-2]
                else:
                    real_url = decoded
                if real_url.startswith('http') or real_url.startswith('ftp') or real_url.startswith('magnet'):
                    download_url = real_url
                    link_type = "迅雷"
                    print(f"[115] 检测到迅雷链接，解码后: {real_url[:60]}...，发送者={from_user}")
                else:
                    print(f"[115] 迅雷链接解码后不是有效URL: {real_url[:50]}")
            except Exception as e:
                print(f"[115] 迅雷链接解码失败: {e}")

    if not download_url:
        return None  # 没有磁力或迅雷链接，不处理

    # 扫描所有已登录用户的Cookie文件
    cookie_files = glob.glob(os.path.join(SCRIPT_DIR, "115_cookies_*.json"))
    print(f"[115] 找到 {len(cookie_files)} 个已登录用户")

    if not cookie_files:
        # 没有任何用户登录，自动给发送者发二维码
        print(f"[115] 无已登录用户，给发送者发登录二维码")
        try:
            api_send_message(token, user_id,
                f"⚠️ 无量天尊！{from_user} 道友，目前还没有人登录115网盘。\n\n"
                f"正在为您生成登录二维码，请用115手机APP扫码登录。\n"
                f"登录成功后，大家发的磁力链接都会自动提交到每个人的115网盘。\n\n"
                f"—— 摸金校尉·无良道士段德",
                local_port)
        except Exception as e:
            print(f"[115] 发送提示失败: {e}")
        handle_115_qrcode(user_id, from_user, chat_id, token, local_port)
        return None

    # 遍历所有已登录用户，提交磁力链接
    success_users = []
    fail_users = []
    skip_users = []

    for cookie_file in cookie_files:
        # 从文件名提取用户ID
        basename = os.path.basename(cookie_file)
        uid_match = re.search(r'115_cookies_(\d+)\.json', basename)
        if not uid_match:
            continue
        target_user_id = uid_match.group(1)

        # 读取该用户的Cookie
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cookies = cfg.get("cookies", {})
            target_user_name = cfg.get("user", f"用户{target_user_id}")
        except Exception as e:
            print(f"[115] 读取用户{target_user_id} Cookie失败: {e}")
            fail_users.append(f"❌ {target_user_name} - 读取Cookie失败")
            continue

        if not cookies:
            fail_users.append(f"❌ {target_user_name} - Cookie为空")
            continue

        # 检查该用户的历史记录（是否已提交过）
        user_history_path = os.path.join(SCRIPT_DIR, f"115_magnet_history_{target_user_id}.json")
        user_history = {}
        if os.path.exists(user_history_path):
            try:
                with open(user_history_path, "r", encoding="utf-8") as f:
                    user_history = json.load(f)
            except Exception:
                user_history = {}

        # 用URL的MD5作为历史记录key（兼容磁力和迅雷链接）
        import hashlib
        history_key = hashlib.md5(download_url.encode()).hexdigest()[:16]

        if history_key in user_history:
            old_record = user_history[history_key]
            skip_users.append(f"⏭️ {target_user_name} - 已于 {old_record.get('submit_time', '?')} 提交")
            print(f"[115] 用户{target_user_name}已提交过，跳过")
            continue

        # 创建会话，提交磁力链接
        session = requests.Session()
        session.cookies.update(cookies)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://115.com/web/lixian/",
            "Origin": "https://115.com",
        })

        try:
            resp = session.post(
                "https://115.com/web/lixian/?ct=lixian&ac=add_task_url",
                data={"url": download_url},
                timeout=15
            )
            result = resp.json()
            if result.get("state"):
                success_users.append(f"✅ {target_user_name}")
                print(f"[115] 用户{target_user_name}提交成功")
                # 记录到该用户的历史（用URL的MD5作为key，兼容磁力和迅雷链接）
                import hashlib
                history_key = hashlib.md5(download_url.encode()).hexdigest()[:16]
                user_history[history_key] = {
                    "submit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "from_user": from_user,
                    "url": download_url,
                    "link_type": link_type
                }
                try:
                    with open(user_history_path, "w", encoding="utf-8") as f:
                        json.dump(user_history, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"[115] 保存用户{target_user_name}历史失败: {e}")
            else:
                fail_msg = result.get("error", "未知错误")
                fail_users.append(f"❌ {target_user_name} - {fail_msg}")
                print(f"[115] 用户{target_user_name}提交失败: {fail_msg}")
        except Exception as e:
            fail_users.append(f"❌ {target_user_name} - 请求异常")
            print(f"[115] 用户{target_user_name}请求异常: {e}")

    # 如果发送者自己不在已登录用户中，提示发送者登录
    sender_cookie_path = os.path.join(SCRIPT_DIR, f"115_cookies_{user_id}.json")
    sender_logged_in = os.path.exists(sender_cookie_path)

    # 构建结果消息
    result_lines = [
        f"📦 无量天尊！{from_user} 道友分享的{link_type}链接已广播离线下载！\n",
        f"🔗 链接: {download_url[:50]}...\n"
    ]

    if success_users:
        result_lines.append(f"✅ 成功提交到 {len(success_users)} 人的115网盘：")
        result_lines.extend(success_users)
        result_lines.append("")

    if skip_users:
        result_lines.append(f"⏭️ 已提交过（自动跳过） {len(skip_users)} 人：")
        result_lines.extend(skip_users)
        result_lines.append("")

    if fail_users:
        result_lines.append(f"❌ 提交失败 {len(fail_users)} 人：")
        result_lines.extend(fail_users)
        result_lines.append("")

    if not sender_logged_in:
        result_lines.append(f"⚠️ {from_user} 道友，您还未登录115网盘，发「二维码」扫码登录后也能自动接收磁力链接。")

    result_lines.append("\n—— 摸金校尉·无良道士段德")

    return "\n".join(result_lines)


def handle_url(text, history, chat_id, from_user, pending_path, user_id=None, token=None, local_port=None, trigger_crawl=False):
    """处理收到的网址：写入Bot同步文件，由监控总控分发到路由队列
    铁律：全局每天最多10个新站（满了不再收集，等明天）；普通用户每人每天最多3个（管理员豁免）
    主队列最多2组(10个)，满了但额度没用完时超出的进备用队列
    记录提交者user_id，入队时@提出者，任务完成/失败时@通知
    trigger_crawl=True: 用户发「爬虫+网址」主动触发，扣CRAWL_COST积分，标记triggered立即执行
    trigger_crawl=False: 纯网址收录，只+1积分不扣费，等待用户主动触发或定时调度"""
    urls = URL_PATTERN.findall(text)
    if not urls:
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mention = build_user_mention(user_id, from_user)

    # ---------- 检查0：判断权限（群主=creator免费+破格+豁免；管理员=administrator受限制+消耗积分） ----------
    is_owner = False
    is_admin_only = False
    if token and local_port and user_id:
        is_owner = is_owner_cached(user_id, token, chat_id, local_port)
        if not is_owner:
            is_admin_only = is_admin_only_cached(user_id, token, chat_id, local_port)
    # 兼容变量：is_privileged 表示群主（有破格/免费/豁免权）
    is_privileged = is_owner

    # ---------- 检查-2：已处理过的网址（成功/失败）不再接受（仅群主可破格，其他人扣1分） ----------
    for url in urls[:]:
        is_processed, status, reason, site_name = check_url_processed(url)
        if is_processed and not is_privileged:
            # 扣1分（重复提交惩罚）
            consume_user_points(user_id, 1)
            current_pts = get_user_points(user_id)
            rejection = build_processed_rejection(url, status, reason, site_name, mention)
            return rejection + f"\n\n💸 重复提交，扣除1积分，当前剩余 {current_pts} 分"
        if is_processed and is_privileged:
            print(f"[破格] 群主提交已处理网址: {url} ({status})")

    # ---------- 检查-1：困难站点预检（CF盾/导航站/域名停放等，直接拒绝，仅群主可破格，其他人扣1分） ----------
    for url in urls[:]:
        is_hard, hard_reason = precheck_hard_site(url)
        if is_hard and not is_privileged:
            # 扣1分（困难站点惩罚）
            consume_user_points(user_id, 1)
            current_pts = get_user_points(user_id)
            return (
                f"⚠️ 无量天尊！{mention} 道友，此宝穴难处，贫道不收！\n\n"
                f"⚱️ 宝穴：{url[:60]}\n"
                f"❌ 原因：{hard_reason}\n\n"
                f"此等难处之穴，入了也是折戟，贫道不接。\n"
                f"道友另寻他穴罢，若确有把握可@群主定夺。\n\n"
                f"💸 困难站点，扣除1积分，当前剩余 {current_pts} 分\n\n"
                f"—— 摸金校尉·无良道士段德"
            )
        if is_hard and is_privileged:
            print(f"[破格] 群主提交困难站点: {url} ({hard_reason})")

    # ---------- 检查1：全局每日爬取额度（铁律，达到上限后暂停掘穴但队列继续收集网址） ----------
    daily_data = load_daily_count()
    today_count = daily_data.get("count", 0)
    remaining_daily = MAX_DAILY_CRAWL - today_count

    if remaining_daily <= 0:
        # 达到上限：如果是主动触发掘穴，拒绝并告知token告急；如果是纯网址收录，继续收集
        if trigger_crawl:
            return (
                f"⚠️ 无量天尊！{mention} 道友且慢——今日掘穴令牌已然告急！\n\n"
                f"📊 今日已掘：{today_count}/{MAX_DAILY_CRAWL} 座宝穴（铁律上限）\n"
                f"🔌 Token告急，贫道分身乏力，今日暂封掘穴之术\n\n"
                f"📥 网址仍可继续投递收录（+1积分），存入待掘名册\n"
                f"🎲 道友可发「摇骰子」排号，明日令牌重置后按序号优先掘穴\n"
                f"⏰ 令牌每日零点自动重置，道友明日请早！\n\n"
                f"—— 摸金校尉·无良道士段德"
            )
        # 纯网址收录：继续收集，不触发掘穴
        # 继续执行后续收录逻辑，但trigger_crawl强制为False
        trigger_crawl = False

    # 全局额度不足时只接受剩余数量
    if len(urls) > remaining_daily:
        urls = urls[:remaining_daily]

    # ---------- 检查2：每人每天最多3个（仅群主豁免，管理员和普通用户都受此限制） ----------
    if not is_privileged:
        user_today = get_user_today_count(user_id)
        user_remaining = MAX_PER_USER_PER_DAY - user_today
        if user_remaining <= 0:
            return (
                f"⚠️ 无量天尊！{mention} 道友今日投穴之数已达上限！\n\n"
                f"📊 道友今日已投：{user_today}/{MAX_PER_USER_PER_DAY} 座宝穴\n"
                f"👑 若需追加额度，请知会群主，彼可破格添录。\n"
                f"⏰ 每人额度每日零点自动重置，道友明日请早！\n\n"
                f"—— 摸金校尉·无良道士段德"
            )
        if len(urls) > user_remaining:
            urls = urls[:user_remaining]

    # ---------- 检查2.5：积分检查（仅群主免费；trigger_crawl=True时管理员和普通用户每座消耗CRAWL_COST积分；纯网址收录不扣费） ----------
    points_after = None
    total_cost = 0
    if trigger_crawl and not is_privileged:
        user_points = get_user_points(user_id)
        total_cost = len(urls) * CRAWL_COST
        if user_points < total_cost:
            can_afford = user_points // CRAWL_COST
            if can_afford <= 0:
                return (
                    f"⚠️ 无量天尊！{mention} 道友积分不足，此宝穴贫道暂不能掘！\n\n"
                    f"💰 道友当前积分：{user_points} 分\n"
                    f"⚡ 掘穴消耗：每座 {CRAWL_COST} 分，本次需 {total_cost} 分\n\n"
                    f"📜 道友可每日签到得 {SIGN_REWARD} 分，提交网址得1分，积少成多！\n"
                    f"   发送「签到」或点击下方按钮即可签到。\n"
                    f"👑 若急需掘穴，可请群主赏赐积分或破格免费。\n\n"
                    f"—— 摸金校尉·无良道士段德"
                )
            # 积分只够部分网址
            urls = urls[:can_afford]
            total_cost = len(urls) * CRAWL_COST
        # 扣除积分
        consume_user_points(user_id, total_cost)
        points_after = get_user_points(user_id)
    elif not trigger_crawl:
        # 纯网址收录模式：不扣积分，只记录
        pass

    # ---------- 检查3：主队列最多2组(10个)，满了但额度没用完时超出的进备用队列 ----------
    bot_sync_path = os.path.join(SCRIPT_DIR, "tg_bot_sync.json")
    try:
        if os.path.isfile(bot_sync_path):
            with open(bot_sync_path, "r", encoding="utf-8") as f:
                sync_list = json.load(f)
        else:
            sync_list = []
    except Exception:
        sync_list = []

    pending = load_pending(pending_path)
    current_pending = len([p for p in pending if p.get("status") == "pending"]) + len(sync_list)
    available_slots = MAX_QUEUE_SIZE - current_pending

    # 先尝试从备用队列移网址到主队列（如果有空位）
    backup_moved = 0
    if available_slots > 0:
        backup_moved, _ = move_backup_to_main(bot_sync_path, available_slots)
        if backup_moved > 0:
            # 重新计算可用空位
            try:
                with open(bot_sync_path, "r", encoding="utf-8") as f:
                    sync_list = json.load(f)
            except Exception:
                sync_list = []
            current_pending = len([p for p in pending if p.get("status") == "pending"]) + len(sync_list)
            available_slots = MAX_QUEUE_SIZE - current_pending

    # 分流：能进主队列的进主队列，超出的进备用队列
    main_urls = urls[:available_slots] if available_slots > 0 else []
    backup_urls = urls[available_slots:] if available_slots < len(urls) else []

    # ---------- 写入主队列（Bot同步文件） + 记录提交者 ----------
    added = 0
    updated = 0
    for url in main_urls:
        existing = next((s for s in sync_list if s.get("url") == url), None)
        if not existing:
            # 新网址，添加到队列
            entry = {
                "url": url,
                "from_user": from_user,
                "user_id": str(user_id) if user_id else None,
                "time": now
            }
            if trigger_crawl:
                entry["status"] = "triggered"
                entry["trigger_time"] = now
                entry["trigger_by"] = str(user_id) if user_id else from_user
            sync_list.append(entry)
            record_url_submitter(url, user_id, from_user)
            added += 1
        elif trigger_crawl and existing.get("status") != "triggered":
            # 已存在的网址，用户主动触发掘穴，更新为triggered状态
            existing["status"] = "triggered"
            existing["trigger_time"] = now
            existing["trigger_by"] = str(user_id) if user_id else from_user
            existing["from_user"] = from_user  # 更新提交者为当前触发者
            existing["user_id"] = str(user_id) if user_id else existing.get("user_id")
            updated += 1
            print(f"[触发] 已将已有网址更新为triggered: {url}")

    try:
        with open(bot_sync_path, "w", encoding="utf-8") as f:
            json.dump(sync_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] Bot同步文件写入失败: {e}")

    # ---------- 同步到AI待处理队列（关键修复：网址必须写入tg_pending_urls.json，AI定时任务才能检测到） ----------
    try:
        pending = load_pending(pending_path)
        synced_count = 0
        for url in main_urls:
            # 检查是否已存在于pending队列
            exists = any(p.get("url") == url for p in pending)
            if not exists:
                pending.append({
                    "url": url,
                    "status": "pending",
                    "from_user": from_user,
                    "user_id": str(user_id) if user_id else None,
                    "time": now,
                    "source": "tg_bot_auto_sync"
                })
                synced_count += 1
                print(f"[同步] 网址已写入AI待处理队列: {url}")
            else:
                # 已存在但状态不是pending的，重置为pending（用户重新提交）
                for p in pending:
                    if p.get("url") == url and p.get("status") not in ("pending", "processing"):
                        p["status"] = "pending"
                        p["time"] = now
                        p["from_user"] = from_user
                        synced_count += 1
                        print(f"[同步] 已有网址重置为pending: {url}")
                        break
        if synced_count > 0:
            save_pending(pending_path, pending)
            print(f"[同步] 共同步 {synced_count} 个网址到AI待处理队列")
    except Exception as e:
        print(f"[警告] 同步到AI待处理队列失败: {e}")

    # ---------- 写入备用队列 ----------
    backup_added = 0
    for url in backup_urls:
        if add_to_backup(url, from_user, user_id):
            record_url_submitter(url, user_id, from_user)
            backup_added += 1

    # 增加每日爬取计数（主队列+备用队列都算今日提交，triggered更新也算）
    total_new = added + updated + backup_added
    if total_new > 0:
        new_daily_count = increment_daily_count(main_urls + backup_urls)
        if not is_privileged:
            increment_user_daily_count(user_id, from_user, total_new)
    else:
        new_daily_count = today_count

    # ---------- 积分奖励：每成功提交一个网址+2积分（全员适用，含管理员） ----------
    submit_bonus = 0
    if total_new > 0:
        submit_bonus = total_new * 2  # 每个网址2积分
        add_user_points(user_id, from_user, submit_bonus, reason=f"提交网址奖励x{total_new}")
        # 重新计算当前积分（消耗后+奖励）
        if not is_privileged:
            points_after = get_user_points(user_id)

    # 计算队列总数
    total_pending = len([p for p in pending if p.get("status") == "pending"]) + len(sync_list)
    total_groups = (total_pending + GROUP_SIZE - 1) // GROUP_SIZE
    backup_count = len(load_backup_queue())

    # ---------- 构建回复（@提出者，段德口吻美化话术） ----------
    if trigger_crawl:
        lines = [f"⚡ 无量天尊！{mention} 道友号令掘穴，贫道接令，这便开坛！", ""]
    else:
        lines = [f"🔗 无量天尊！{mention} 道友投来宝穴，贫道已然记下，收入待掘名册！", ""]

    if main_urls:
        if trigger_crawl:
            lines.append("⛏️ 已排入立即掘穴队列：")
        else:
            lines.append("📜 已入主待掘名册：")
        for i, url in enumerate(main_urls, 1):
            lines.append(f"   {i}. {url}")

    if backup_urls:
        lines.append("")
        lines.append("📦 主名册已满，暂存后备暗格：")
        for i, url in enumerate(backup_urls, 1):
            lines.append(f"   {i}. {url}")
        lines.append("   （主名册腾出空位后，自会按先来后到之序移入）")

    lines.append("")
    status_parts = [f"主名册 {total_pending}/{MAX_QUEUE_SIZE} 座（{total_groups}/{MAX_GROUPS}组）"]
    if backup_count > 0:
        status_parts.append(f"后备暗格 {backup_count} 座")
    lines.append(f"📊 {' ｜ '.join(status_parts)}")

    if is_owner:
        lines.append(f"👑 道友身负群主之职，不受每人每日{MAX_PER_USER_PER_DAY}座之限，掘穴免费")
        if submit_bonus > 0:
            owner_points = get_user_points(user_id)
            lines.append(f"💰 投穴奖励：+{submit_bonus} 分，当前 {owner_points} 分")
    elif trigger_crawl and points_after is not None:
        user_now = get_user_today_count(user_id)
        role_label = "管理员" if is_admin_only else "道友"
        lines.append(f"📊 {role_label}今日已投：{user_now}/{MAX_PER_USER_PER_DAY} 座")
        lines.append(f"💰 积分：-{total_cost} 掘穴费 +{submit_bonus} 投穴奖励 = 剩余 {points_after} 分")
    else:
        # 纯网址收录模式：不扣费
        user_now = get_user_today_count(user_id)
        current_pts = get_user_points(user_id)
        lines.append(f"📊 道友今日已投：{user_now}/{MAX_PER_USER_PER_DAY} 座")
        lines.append(f"💰 收录免费！投穴奖励：+{submit_bonus} 分，当前 {current_pts} 分")

    lines.append(f"🔥 今日全局掘穴额度：{new_daily_count}/{MAX_DAILY_CRAWL} 座（此乃铁律，逾额不候）")
    lines.append("")

    if trigger_crawl:
        lines.append("⚡ 立即掘穴模式：")
        lines.append("   此宝穴已标记为「立即掘穴」，")
        lines.append("   贫道分身按队列次序一个一个施展四壳源术，")
        lines.append("   掘开明器后自动推回本群，")
        lines.append("   功成或折戟，贫道都会@道友知会一声。")
        lines.append("")
        lines.append("🎩 拍卖行竞价已开启：")
        lines.append("   道友若想让此宝穴优先掘开，可发「押积分 网址 积分数」加价！")
        lines.append("   价高者得，1分钟押注倒计时，每日仅掘5座！")
        lines.append("   发「竞价榜」查看当前排名。")
    else:
        lines.append("📜 待掘名册模式：")
        lines.append("   此宝穴已收入待掘名册，暂不掘开。")
        lines.append("   道友如需立即掘穴，请发「爬虫+网址」号令，")
        lines.append("   消耗10积分即可排入立即掘穴队列，一个一个排队执行。")
        lines.append("   还可发「押积分 网址 积分数」参与竞价，价高者得！")
        lines.append("   或等贫道定时调度，按名册次序逐组掘开。")

    lines.append("   道友且宽心坐等，无需操劳。")
    lines.append("")
    lines.append("—— 摸金校尉·无良道士段德")
    return "\n".join(lines)


def extract_site_from_reply(reply_msg):
    """
    从用户引用的机器人推送消息中提取站点名。
    机器人推送消息格式包含：🔮 {site_name}·四壳源术 / 🗃️ {site_name}·微阁洞天
    文件推送的caption可能是：{site_name}.py / {site_name}_小程序.zip
    """
    if not reply_msg:
        return ""

    # 从文本消息中提取
    text = reply_msg.get("text", "") or reply_msg.get("caption", "")
    if text:
        # 匹配 🔮 xxx·四壳源术 或 🗃️ xxx·微阁洞天
        import re as _re
        m = _re.search(r'[🔮🗃️]\s*(.+?)[·•]', text)
        if m:
            return m.group(1).strip()
        # 匹配文件名样式：xxx.py 或 xxx_小程序.zip
        m = _re.search(r'([\w\u4e00-\u9fa5]+)(?:\.py|_小程序)', text)
        if m:
            return m.group(1).strip()

    # 从文件附件的文件名中提取
    doc = reply_msg.get("document", {})
    if doc:
        fname = doc.get("file_name", "")
        import re as _re
        m = _re.match(r'(.+?)(?:\.py|_小程序\.zip)$', fname)
        if m:
            return m.group(1).strip()
        return fname.replace(".py", "").replace("_小程序.zip", "")

    return ""


def handle_feedback(text, from_user, chat_id, reply_to_message=None):
    """
    处理用户反馈消息：识别站点名+问题描述，收集到反馈队列（不立即触发）
    支持两种方式：
      1. 直接发：站点名/URL + 问题描述（如 "lusi_av 无法获取分类"）
      2. 引用机器人推送消息 + 问题描述（如引用推送消息后说 "无法播放"）
    返回回复消息文本，非反馈返回 None
    """
    if not os.path.isfile(FEEDBACK_REPAIR_SCRIPT):
        return None

    site_keyword = ""
    problem_text = text.strip()

    # 方式1：直接消息中包含站点名+问题
    try:
        result = subprocess.run(
            [sys.executable, FEEDBACK_REPAIR_SCRIPT, "detect", text],
            capture_output=True, text=True, timeout=15
        )
        detect_output = result.stdout.strip()
    except Exception as e:
        print(f"[反馈检测] 调用失败: {e}")
        detect_output = ""

    if "不是反馈消息" not in detect_output:
        # 直接消息识别为反馈，提取站点关键词
        for line in detect_output.split("\n"):
            if "站点关键词" in line:
                site_keyword = line.split(":", 1)[1].strip()
                break

    # 方式2：引用消息 + 任何描述（直接消息没识别到站点名时）
    # 收集所有问题：只要引用了机器人推送消息，且有任何描述文字，即视为反馈
    if not site_keyword and reply_to_message:
        replied_site = extract_site_from_reply(reply_to_message)
        if replied_site:
            # 排除纯正面/中性评价
            positive_words = ["不错", "挺好", "很好", "好棒", "太棒了", "赞", "喜欢", "好用",
                              "可以用", "正常", "没问题", "谢谢", "感谢", "辛苦了", "牛", "厉害",
                              "完美", "优秀", "满意", "ok", "OK", "666"]
            text_lower = text.lower()
            is_positive = any(pw in text_lower for pw in positive_words) and len(text) < 30
            # 排除命令和纯网址
            is_command = text.startswith("/")
            is_pure_url = bool(re.match(r'^https?://\S+$', text.strip()))

            # 有描述文字且不是正面评价/命令/纯网址 → 视为反馈（收集所有问题）
            if text.strip() and not is_positive and not is_command and not is_pure_url:
                site_keyword = replied_site
                problem_text = f"{replied_site} {text}".strip()

    if not site_keyword:
        return None

    # 调用 collect 收集反馈（不立即触发，等下次任务触发时派发）
    try:
        result = subprocess.run(
            [sys.executable, FEEDBACK_REPAIR_SCRIPT, "collect", site_keyword, problem_text,
             "--from-user", from_user],
            capture_output=True, text=True, timeout=30
        )
        collect_output = (result.stdout + result.stderr).strip()
        collect_returncode = result.returncode
    except Exception as e:
        print(f"[反馈收集] 调用失败: {e}")
        return "🔧 无量天尊！收到道友反馈，但贫道记录时出了点差错，请稍后再试。"

    # 站点无推送记录 → 拒绝修复（是新站）
    if collect_returncode != 0 and ("无推送记录" in collect_output or "拒绝修复" in collect_output):
        return (
            f"⚠️ 无量天尊！此宝穴尚未掘开，贫道不收修复之请！\n\n"
            f"⚱️ 宝穴：{site_keyword}\n\n"
            f"📜 此宝穴尚无推送记录，是未掘之新穴。\n"
            f"   修复只针对已推送过成品的宝穴。\n"
            f"   道友若欲掘此新穴，请直接将网址发群里入队，\n"
            f"   待首次掘开推送成品后，再反馈问题不迟！\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

    # 解析收集结果
    url_resolved = "未解析" not in collect_output
    feedback_id = ""
    import re as _re
    m = _re.search(r"\[(fb_\d+)\]", collect_output)
    if m:
        feedback_id = m.group(1)

    # 回复话术：已收集问题点，下次任务触发给AI处理修复
    if url_resolved:
        return (
            f"📝 无量天尊！道友的问题点贫道已收录！\n\n"
            f"⚱️ 宝穴：{site_keyword}\n"
            f"📝 问题：{text[:80]}\n"
            f"🆔 反馈编号：{feedback_id}\n\n"
            f"⚡ 已收集问题点，下次任务触发时给AI处理修复。\n"
            f"   修复完成后自动推送新版本到本群。\n"
            f"   道友静候佳音即可！\n\n"
            f"—— 摸金校尉·无良道士段德"
        )
    else:
        return (
            f"📝 无量天尊！道友的问题点贫道已收录！\n\n"
            f"⚱️ 宝穴：{site_keyword}\n"
            f"📝 问题：{text[:80]}\n"
            f"🆔 反馈编号：{feedback_id}\n\n"
            f"⚠️ 此宝穴网址暂缺，道友若方便可将网址发群里，\n"
            f"   贫道补全后下次任务触发时一并修复。\n\n"
            f"—— 摸金校尉·无良道士段德"
        )


# 重启所有服务脚本路径（duande-baoxue-announcer 技能）
RESTART_ALL_SCRIPT = os.path.join(SCRIPT_DIR, "..", "duande-baoxue-announcer", "scripts", "restart_all.sh")


def is_chat_admin(token, chat_id, user_id, local_port):
    """
    检查用户是否为群主或管理员（通过TG API getChatMember）
    只有群主(creator)和管理员(administrator)有权限执行重启等敏感操作
    """
    url = f"https://api.telegram.org/bot{token}/getChatMember"
    data = urllib.parse.urlencode({"chat_id": chat_id, "user_id": user_id}).encode("utf-8")
    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        resp = opener.open(req, timeout=15)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            status = result.get("result", {}).get("status", "")
            return status in ("creator", "administrator")
        return False
    except Exception as e:
        print(f"[权限检查] 失败: {e}")
        return False


def get_chat_member_status(token, chat_id, user_id, local_port):
    """获取用户在群中的状态：creator/administrator/member/restricted/left/kicked"""
    url = f"https://api.telegram.org/bot{token}/getChatMember"
    data = urllib.parse.urlencode({"chat_id": chat_id, "user_id": user_id}).encode("utf-8")
    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        resp = opener.open(req, timeout=15)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            return result.get("result", {}).get("status", "member")
    except Exception as e:
        print(f"[状态检查] 失败: {e}")
    return "member"


# 权限缓存（避免每次消息都调API）
_admin_cache = {}
_owner_cache = {}


def is_owner_cached(user_id, token, chat_id, local_port):
    """检查是否为群主（creator），带缓存"""
    key = f"{chat_id}:{user_id}"
    if key in _owner_cache:
        return _owner_cache[key]
    status = get_chat_member_status(token, chat_id, user_id, local_port)
    result = (status == "creator")
    _owner_cache[key] = result
    return result


def is_admin_only_cached(user_id, token, chat_id, local_port):
    """检查是否为管理员但非群主（administrator，不含creator），带缓存"""
    key = f"{chat_id}:{user_id}"
    if key in _admin_cache:
        return _admin_cache[key]
    status = get_chat_member_status(token, chat_id, user_id, local_port)
    result = (status == "administrator")
    _admin_cache[key] = result
    return result


def handle_restart(token, chat_id, user_id, local_port, from_user):
    """
    处理重启所有服务的指令（仅群主/管理员可用）
    调用 restart_all.sh 重启所有服务，包括Bot自身
    """
    # 权限检查
    if not is_chat_admin(token, chat_id, user_id, local_port):
        return (
            f"⚠️ 无量天尊！重启全服务乃高危操作，唯有群主或管理员可号令。\n"
            f"   道友「{from_user}」权限不足，此令贫道不敢接。\n\n"
            f"—— 摸金校尉·无良道士段德"
        )

    # 先回复确认（因为重启后Bot会断开，这条消息要先发出去）
    confirm_msg = (
        f"🔄 无量天尊！群主有令，贫道这便重启全服务！\n\n"
        f"⚙️ 正在重启：TG Bot / 中央处理器 / 顶端监控 / 排队监控 / 延迟调度\n"
        f"   约10秒后全部上线，Bot会重新发上线通知。\n"
        f"   道友稍候片刻！\n\n"
        f"—— 摸金校尉·无良道士段德"
    )

    # 发送确认消息
    try:
        api_send_message(token, chat_id, confirm_msg, local_port)
    except Exception:
        pass

    # 延迟1秒让消息发出去，再执行重启
    time.sleep(1)

    # 后台执行重启脚本（它会杀掉当前Bot进程并重启所有服务）
    if os.path.isfile(RESTART_ALL_SCRIPT):
        subprocess.Popen(
            ["bash", RESTART_ALL_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print("[重启] 已触发全服务重启脚本")
    else:
        print(f"[重启] 脚本不存在: {RESTART_ALL_SCRIPT}")

    # 返回None（不回复，因为确认消息已经发了，而且进程即将被重启）
    return None


def cmd_queue(pending_path):
    """列出待处理网址队列"""
    pending = load_pending(pending_path)
    pending_items = [p for p in pending if p["status"] == "pending"]
    lines = [f"📋 {pick_quote('queue_empty') if not pending_items else '待掘宝穴队列，且看贫道记录！'}", ""]
    if not pending_items:
        lines.append("（队列空空，道友往群里扔个网址试试）")
    else:
        for i, p in enumerate(pending_items, 1):
            lines.append(f"  {i}. {p['url']}")
            lines.append(f"     投递者: {p['from_user']} | 时辰: {p['time']}")
        lines.append("")
        lines.append(f"共 {len(pending_items)} 座待掘")
    lines.append("")
    lines.append("⚡ 全自动执行中，连接器定时唤起会话逐组掘开，道友静候佳音")
    lines.append("—— 段德 敬上")
    return "\n".join(lines)


def process_message(token, chat_id, text, from_user, local_port, history, history_path, pending_path, reply_to_message=None, user_id=None, debug=False):
    """处理一条群消息，返回回复文本（None表示不回复）"""
    if not text:
        return None

    # ========== 群白名单铁律：蚂蚁影视群只推送文件，不响应任何口令 ==========
    # 从配置读取蚂蚁群chat_id，Bot在该群中静默，只通过tg_pusher推送小程序zip
    try:
        with open(os.path.join(SCRIPT_DIR, "tg_config.json"), encoding="utf-8") as f:
            _cfg = json.load(f)
        _miniapp_cfg = _cfg.get("miniapp_push", {})
        _miniapp_chat_id = str(_miniapp_cfg.get("chat_id", "")) if _miniapp_cfg.get("enabled") else ""
        if _miniapp_chat_id and str(chat_id) == _miniapp_chat_id:
            if debug:
                print(f"[群白名单] 消息来自蚂蚁影视群(chat_id={chat_id})，静默不响应")
            return None
    except Exception:
        pass  # 配置读取失败时不拦截，保持原有行为

    text_lower = text.strip().lower()
    text_stripped = text.strip()

    if debug:
        print(f"[DEBUG] 收到消息: {text[:80]}")

    # ========== 本地智能问答（仅群主可触发，不调用豆包AI，纯关键词匹配） ==========
    # 先检查是否为群主
    _is_owner = False
    if token and local_port and user_id:
        try:
            _is_owner = is_owner_cached(user_id, token, chat_id, local_port)
        except Exception:
            _is_owner = False

    # 0.0 115网盘磁力/迅雷离线下载（最高优先级，检测到magnet或thunder链接时自动提交，支持换行分割）
    import re as _re_magnet
    _text_no_newline = _re_magnet.sub(r'[\r\n\s]+', '', text)
    if _re_magnet.search(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}', _text_no_newline, _re_magnet.IGNORECASE) or \
       _re_magnet.search(r'thunder://[a-zA-Z0-9+/=]+', _text_no_newline, _re_magnet.IGNORECASE):
        magnet_result = handle_magnet_115(text, user_id, from_user, token, chat_id, local_port)
        if magnet_result:
            return magnet_result

    if _is_owner:
        # 群主智能问答管理口令（最高优先级，在其他口令之前）
        qa_reply, qa_handled = handle_smart_qa_command(text, user_id, token, chat_id, local_port)
        if qa_handled:
            print(f"[智能问答] 群主管理口令: {text[:50]}")
            return qa_reply

        # 群主普通问题自动匹配（排除纯网址和爬虫触发等指令性消息）
        if not URL_PATTERN.search(text) and not text_lower.startswith(("/", "爬虫", "掘穴", "挖坟", "跑", "签到", "积分", "队列", "重启")):
            qa_answer = match_smart_qa(text)
            if qa_answer:
                print(f"[智能问答] 群主问题匹配成功: {text[:50]}")
                return qa_answer

    # 0. 重启所有服务（仅群主/管理员，最高优先级）
    if text_lower in ("/restart", "重启", "重启服务", "重启所有服务", "全部重启", "重启全部") or text_lower.startswith("/restart"):
        return handle_restart(token, chat_id, user_id, local_port, from_user)

    # 0.5 签到（积分系统，全员可用）
    if text_lower in ("/sign", "签到", "每日签到", "打卡", "每日打卡", "签个到") or text_lower.startswith("/sign"):
        return handle_sign(user_id, from_user)

    # 0.6 积分查询
    if text_lower in ("/points", "积分", "我的积分", "查积分", "积分查询", "多少积分", "余额") or text_lower.startswith("/points"):
        return cmd_points(user_id, from_user)

    # 0.7 摇骰子排号（全员可用，token告急时排号，次日按序号优先掘穴）
    if text_lower in ("摇骰子", "/roll", "掷骰子", "排号", "摇色子", "抽签") or text_lower.startswith("/roll"):
        return handle_roll(user_id, from_user)

    # 0.8 查看摇骰子排名
    if text_lower in ("排名", "排号榜", "/rank", "骰子排名", "摇骰子排名") or text_lower.startswith("/rank"):
        return get_roll_rank_text()

    # 0.9 押积分竞价（拍卖行模式，价高者得，1分钟押注倒计时）
    if text_lower.startswith("押积分") or text_lower.startswith("/bid") or text_lower.startswith("竞价") or text_lower.startswith("出价"):
        # 排除纯"竞价榜"口令
        if text_lower not in ("竞价榜", "拍卖行", "/bidlist", "竞价排名"):
            return handle_bid_command(text, user_id, from_user, token, chat_id, local_port)

    # 0.10 查看竞价榜
    if text_lower in ("竞价榜", "拍卖行", "/bidlist", "竞价排名", "押积分榜") or text_lower.startswith("/bidlist"):
        return get_bid_rank_text()

    # 0.11 115网盘扫码登录（生成二维码私发给用户）
    if text_lower in ("二维码", "扫码", "115扫码", "115登录", "/115login") or text_lower.startswith("/115"):
        handle_115_qrcode(user_id, from_user, chat_id, token, local_port)
        return None  # 函数内部已发送图片，不返回文字消息

    # 0.7 菜单按钮（显示inline keyboard）
    if text_lower in ("/menu", "菜单", "主菜单", "按钮", "功能", "功能表") or text_lower.startswith("/menu"):
        return ("📜 无量天尊！诸位道友，贫道的功能都在下方按钮中，轻点即可差遣！\n\n—— 摸金校尉·无良道士段德", build_main_keyboard())

    # 1. 反馈修复识别（优先于网址检测，"URL+问题描述"识别为反馈；支持引用消息）
    feedback_reply = handle_feedback(text, from_user, chat_id, reply_to_message)
    if feedback_reply:
        return feedback_reply

    # 1.5 「爬虫+网址」主动触发掘穴（扣CRAWL_COST积分，标记triggered立即执行，排队一个一个）
    crawl_trigger_pattern = re.compile(r'^(?:爬虫|掘穴|挖坟|开掘|立即掘穴|掘开|跑|掘冢)\s*[+：: ]?\s*(https?://\S+)', re.IGNORECASE)
    crawl_match = crawl_trigger_pattern.search(text_stripped)
    if crawl_match and URL_PATTERN.search(text):
        # 提取触发词和网址
        trigger_word = crawl_match.group(0).split(crawl_match.group(1))[0].strip(' +：:')
        crawl_url = crawl_match.group(1)
        print(f"[触发] 爬虫+网址模式: 触发词='{trigger_word}', 网址={crawl_url}")
        return handle_url(text, history, chat_id, from_user, pending_path,
                         user_id=user_id, token=token, local_port=local_port, trigger_crawl=True)

    # 2. 网址检测（纯网址入队，只收录+1积分，不扣掘穴费）
    if URL_PATTERN.search(text):
        return handle_url(text, history, chat_id, from_user, pending_path, user_id=user_id, token=token, local_port=local_port, trigger_crawl=False)

    # 2. 口令匹配
    # /help 或 帮助/口令/指令
    if text_lower in ("/help", "帮助", "口令", "指令", "/start") or text_lower.startswith("/help"):
        return cmd_help(history, chat_id)

    # /queue 或 队列/待处理/待掘
    if text_lower in ("/queue", "队列", "待处理", "待掘", "排队", "存货队列") or text_lower.startswith("/queue"):
        return cmd_queue(pending_path)

    # /py 或 py/源术/py脚本
    if text_lower in ("/py", "py", "源术", "py脚本", "spider", "爬虫") or text_lower.startswith("/py"):
        return cmd_py(history, chat_id)

    # /zip 或 小程序/微阁/app
    if text_lower in ("/zip", "小程序", "微阁", "app", "软件", "适配") or text_lower.startswith("/zip"):
        return cmd_zip(history, chat_id)

    # /list 或 列表/存货/所有
    if text_lower in ("/list", "列表", "存货", "所有", "全部", "总览") or text_lower.startswith("/list"):
        return cmd_list(history, chat_id)

    # /sites 或 站点/宝穴/目录
    if text_lower in ("/sites", "站点", "宝穴", "目录", "名录") or text_lower.startswith("/sites"):
        return cmd_sites(history, chat_id)

    # /clean 或 撤回
    if text_lower.startswith("/clean") or "撤回" in text_stripped:
        return cmd_clean(token, chat_id, text_stripped, local_port, history, history_path)

    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Bot口令服务")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    config = load_config(args.config)
    token = config["bot"]["token"]
    chat_id = config["bot"]["chat_id"]
    proxy_pool_path = config.get("proxy_pool", DEFAULT_PROXY_POOL)
    proxy_pool = load_proxy_pool(proxy_pool_path)
    history_path = config.get("history_file", DEFAULT_HISTORY)
    pending_path = os.path.join(SCRIPT_DIR, "tg_pending_urls.json")
    xray_bin = config.get("xray_binary", os.path.join(SCRIPT_DIR, "xray"))
    if not os.path.isfile(xray_bin):
        xray_bin = "xray"

    # HTTP/HTTPS IP代理（优先于VLESS+xray）
    # 配置格式: "http://user:pass@host:port" 或 "http://host:port"
    http_proxy_url = config.get("http_proxy", "") or os.environ.get("TG_HTTP_PROXY", "")

    nodes = proxy_pool.get("nodes", [])
    direct_mode = False
    if not nodes and not http_proxy_url:
        print("[警告] 代理池为空且未配置http_proxy，使用直连模式")
        direct_mode = True

    print("=" * 50)
    print("⚱️ 段德Bot口令服务启动")
    print(f"目标群: {chat_id}")
    if http_proxy_url:
        # 隐藏密码显示
        display_proxy = http_proxy_url
        if "@" in display_proxy:
            parts = display_proxy.split("@")
            display_proxy = "http://***:***@" + parts[-1]
        print(f"HTTP代理: {display_proxy}（优先使用，不启动xray）")
    else:
        print(f"代理池: {len(nodes)} 个节点")
    print(f"调试模式: {'开' if args.debug else '关'}")
    print("=" * 50)

    # 如果配置了HTTP代理，直接使用，跳过xray
    if http_proxy_url:
        local_port = http_proxy_url  # build_opener支持字符串URL
        use_http_proxy = True
        print(f"[代理] 使用HTTP代理: {display_proxy}")
        # 测试连通性
        if test_proxy(http_proxy_url, timeout=15, token=token):
            print("[代理] HTTP代理连通成功")
        else:
            print("[警告] HTTP代理连通测试失败，但继续运行（可能间歇性可用）")
    else:
        use_http_proxy = False
        # 启动代理（优先使用常驻代理10809，所有会话共享，不启动临时xray）
        PERMANENT_PROXY_PORT = 10809
        current_node_idx = 0
        local_port = 10950
        proc = None
        config_path = None
        use_permanent_proxy = False

    def switch_proxy():
        nonlocal current_node_idx, proc, config_path, local_port, use_permanent_proxy
        # 优先尝试常驻代理（重试3次，间歇性超时）
        for _perm_retry in range(3):
            if test_proxy(PERMANENT_PROXY_PORT, timeout=20, token=token):
                if proc:
                    stop_xray(proc, config_path)
                    proc = None
                local_port = PERMANENT_PROXY_PORT
                use_permanent_proxy = True
                print(f"[代理] 使用常驻共享代理 127.0.0.1:{PERMANENT_PROXY_PORT}（所有会话共享，不启动临时xray）")
                return True
            time.sleep(2)
        use_permanent_proxy = False
        # 常驻代理不可用，启动临时xray
        if proc:
            stop_xray(proc, config_path)
        for attempt in range(len(nodes)):
            node = nodes[current_node_idx % len(nodes)]
            current_node_idx += 1
            local_port = 10950 + (current_node_idx % 10)
            print(f"[代理] 切换到: {node.get('name','?')} (端口 {local_port})")
            proc, config_path = start_xray(xray_bin, node, local_port)
            # 每个节点测试4次（VLESS隧道建立较慢，间歇性超时）
            connected = False
            for retry in range(4):
                if proc and test_proxy(local_port, timeout=20, token=token):
                    connected = True
                    break
                if retry < 3:
                    time.sleep(3)
            if connected:
                print(f"[代理] 连通成功")
                return True
            print(f"[代理] 连通失败，尝试下一个")
        return False

    if not use_http_proxy and not direct_mode:
        if not switch_proxy():
            print("[警告] 代理连通性检测全部失败，但不退出——直接使用第一个节点进入主循环，主循环会自动切换代理")
            node = nodes[0]
            local_port = 10950
            proc, config_path = start_xray(xray_bin, node, local_port)
            print(f"[代理] 强制使用: {node.get('name','?')} (端口 {local_port})")
    elif direct_mode:
        local_port = None
        use_http_proxy = False
        print("[直连] 不使用代理，直接连接Telegram API")

    # 发送启动通知
    start_msg = (
        f"⚱️ {pick_quote('welcome')}\n\n"
        f"📜 群内口令：/menu菜单 /sign签到 /points积分 /queue队列 /py源术 /zip微阁 /list存货 /help帮助\n"
        f"🔗 群里扔网址自动入待掘队列，入队即@道友确认，连接器全自动逐组掘穴！\n\n"
        f"💰 积分系统（新）：\n"
        f"   📜 每日签到：+{SIGN_REWARD} 积分\n"
        f"   🔗 提交网址：+1 积分（每座）\n"
        f"   ⚡ 掘穴消耗：每座 {CRAWL_COST} 积分\n"
        f"   👑 群主/管理员：免费掘穴（仍得投穴奖励）\n"
        f"   （发送「菜单」可呼出按钮，轻点签到/查积分/提交爬虫）\n\n"
        f"📋 掘穴规矩（铁律）：\n"
        f"   🏔️ 主名册：2组（10座），满了暂存后备暗格\n"
        f"   👤 每人每日：最多3座（管理员可破格添录）\n"
        f"   🔥 全局每日：最多10座新穴（逾额不候，零点重置）\n"
        f"   🔧 修复旧穴：不计入每日额度\n"
        f"   📢 功成折戟：皆会@道友知会结果\n\n"
        f"道友静候佳音即可，无需操劳！\n\n"
        f"—— 摸金校尉·无良道士段德"
    )
    api_send_message(token, chat_id, start_msg, local_port)
    print("[启动] 已发送上线通知到群")

    # 置顶启动通知（唤醒命令置顶群通知）
    try:
        # 获取最新消息ID用于置顶（发送后通过getUpdates获取）
        time.sleep(1)
        pin_url = f"https://api.telegram.org/bot{token}/pinChatMessage"
        # 先获取最近的消息ID
        get_url = f"https://api.telegram.org/bot{token}/getUpdates?limit=5"
        opener_pin = build_opener(local_port)
        req_get = urllib.request.Request(get_url)
        resp_get = opener_pin.open(req_get, timeout=15)
        updates_data = json.loads(resp_get.read().decode("utf-8"))
        # 找到Bot自己发的启动消息（通过channel_post或message）
        pin_msg_id = None
        for upd in reversed(updates_data.get("result", [])):
            ch_post = upd.get("channel_post", {})
            msg = upd.get("message", {})
            for m in (ch_post, msg):
                if m.get("chat", {}).get("id") == int(chat_id) and "段德" in m.get("text", ""):
                    pin_msg_id = m.get("message_id")
                    break
            if pin_msg_id:
                break
        if pin_msg_id:
            pin_payload = urllib.parse.urlencode({"chat_id": chat_id, "message_id": pin_msg_id, "disable_notification": "true"}).encode("utf-8")
            req_pin = urllib.request.Request(pin_url, data=pin_payload, method="POST")
            resp_pin = opener_pin.open(req_pin, timeout=15)
            pin_result = json.loads(resp_pin.read().decode("utf-8"))
            if pin_result.get("ok"):
                print(f"[置顶] 启动通知已置顶 (消息ID: {pin_msg_id})")
            else:
                print(f"[置顶] 置顶失败: {pin_result.get('description','?')}")
        else:
            print("[置顶] 未找到启动消息ID，跳过置顶")
    except Exception as e:
        print(f"[置顶] 异常: {e}")

    # 主循环：长轮询getUpdates
    offset = 0
    consecutive_failures = 0

    try:
        while True:
            result = api_get_updates(token, offset, local_port, timeout=35)

            if not result.get("ok"):
                consecutive_failures += 1
                print(f"[警告] getUpdates失败 ({consecutive_failures}次): {result.get('description','?')}")
                if consecutive_failures >= 3:
                    if use_http_proxy:
                        print("[代理] HTTP代理模式，不切换xray，继续重试")
                    elif direct_mode:
                        print("[直连] 直连模式，不切换代理，继续重试")
                    else:
                        print("[代理] 连续失败，切换代理节点...")
                        switch_proxy()
                    consecutive_failures = 0
                time.sleep(2)
                continue

            consecutive_failures = 0
            updates = result.get("result", [])

            for update in updates:
                offset = max(offset, update["update_id"] + 1)

                # ---- 处理inline keyboard按钮回调 ----
                cb = update.get("callback_query", {})
                if cb:
                    cb_msg = cb.get("message", {})
                    cb_chat_id = str(cb_msg.get("chat", {}).get("id", ""))
                    cb_data = cb.get("data", "")
                    cb_from = cb.get("from", {})
                    cb_user_id = cb_from.get("id", None)
                    cb_user_name = cb_from.get("first_name", "?")

                    if cb_chat_id == chat_id or cb_msg.get("chat", {}).get("type") == "private":
                        # 先answerCallbackQuery（必须，否则按钮一直转圈）
                        try:
                            cb_url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
                            cb_payload = urllib.parse.urlencode({"callback_query_id": cb["id"]}).encode("utf-8")
                            opener_cb = build_opener(local_port)
                            req_cb = urllib.request.Request(cb_url, data=cb_payload, method="POST")
                            opener_cb.open(req_cb, timeout=10)
                        except Exception:
                            pass

                        # 处理回调
                        cb_reply, cb_markup = handle_callback(cb_data, cb_user_id, cb_user_name, cb_chat_id, pending_path, token=token, local_port=local_port)
                        if cb_reply:
                            pm = "HTML" if 'tg://user?id=' in cb_reply else None
                            r = api_send_message(token, cb_chat_id, cb_reply, local_port, parse_mode=pm, reply_markup=cb_markup)
                            if r.get("ok"):
                                print(f"[按钮] 已回复回调: {cb_data}")
                            else:
                                print(f"[按钮] 发送失败: {r.get('description','?')}")
                    continue

                # ---- 处理普通消息 ----
                msg = update.get("message", {})
                if not msg:
                    continue

                msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                # 只处理目标群的消息（或私聊）
                if msg_chat_id != chat_id and msg.get("chat", {}).get("type") != "private":
                    continue

                text = msg.get("text", "")
                from_user = msg.get("from", {}).get("first_name", "?")
                user_id = msg.get("from", {}).get("id", None)
                reply_to_message = msg.get("reply_to_message", None)

                # ---- 记录私聊消息（用于获取用户私发的token等配置）----
                if msg.get("chat", {}).get("type") == "private" and text:
                    try:
                        from datetime import datetime as _dt
                        private_log_path = os.path.join(SCRIPT_DIR, "logs", "private_chat.log")
                        os.makedirs(os.path.dirname(private_log_path), exist_ok=True)
                        with open(private_log_path, "a", encoding="utf-8") as _f:
                            _f.write(f"[{_dt.now().strftime('%Y-%m-%d %H:%M:%S')}] user_id={user_id} user={from_user} msg_id={msg.get('message_id','')}\n")
                            _f.write(f"{text}\n")
                            _f.write("-" * 50 + "\n")
                        print(f"[私聊记录] 已记录用户 {from_user}({user_id}) 的私聊消息")
                    except Exception as _e:
                        print(f"[私聊记录] 记录失败: {_e}")

                # ---- 记录最后一条消息到数据库（新建会话自动携带上下文）----
                if text:
                    try:
                        import db_helper as _db
                        is_private = msg.get("chat", {}).get("type") == "private"
                        _db.record_last_message(
                            message_text=text,
                            user_id=user_id,
                            username=from_user,
                            chat_id=msg_chat_id,
                            session_id="tg_bot_service",
                            message_type="text",
                            message_id=msg.get("message_id"),
                            is_from_group=not is_private
                        )
                        # 私聊消息同时存到private_messages表
                        if is_private:
                            _db.save_private_message(user_id, from_user, msg.get("message_id"), text)
                    except Exception as _e:
                        print(f"[数据库消息记录] 失败: {_e}")

                # 重新加载历史记录（可能被推送脚本更新）
                history = load_history(history_path)

                reply = process_message(token, msg_chat_id, text, from_user,
                                        local_port, history, history_path, pending_path,
                                        reply_to_message=reply_to_message, user_id=user_id, debug=args.debug)

                if reply:
                    # 支持返回(文本, reply_markup)元组
                    reply_text = reply
                    reply_markup = None
                    if isinstance(reply, tuple):
                        reply_text = reply[0]
                        reply_markup = reply[1] if len(reply) > 1 else None

                    # 检测回复中是否包含@用户的HTML链接，自动使用HTML解析
                    pm = "HTML" if 'tg://user?id=' in reply_text else None
                    r = api_send_message(token, msg_chat_id, reply_text, local_port, parse_mode=pm, reply_markup=reply_markup)
                    if r.get("ok"):
                        print(f"[回复] 已回复口令: {text[:30]}")
                    else:
                        print(f"[回复] 发送失败: {r.get('description','?')}")

    except KeyboardInterrupt:
        print("\n[停止] 收到中断信号，正在关闭...")
    finally:
        if proc:
            stop_xray(proc, config_path)
        print("[停止] 段德口令服务已下线")


if __name__ == "__main__":
    main()
