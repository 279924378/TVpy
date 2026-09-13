#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 推送工具（代理池智能轮换·版本更新撤回版）
- 内置12节点VLESS代理池，单个失败自动切换下一个
- 纯标准库实现，无第三方依赖
- 支持推送文字消息和文件附件（sendDocument）
- 版本更新：推送前自动撤回该站点旧消息（文字+文件），再推新版本
- TG推送不脱敏：文件名直接用原始名称，不做古典映射/改后缀
- 自动启动/管理xray本地代理

用法:
  python3 tg_pusher.py --site 站点名 "文字通知" --file spider.py --file miniapp.zip
  python3 tg_pusher.py --site 站点名 --clean          # 只撤回旧消息不推送
  python3 tg_pusher.py --list-nodes                     # 列出代理池节点
  python3 tg_pusher.py --history                        # 查看推送历史记录
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
import email.mime.multipart
import email.mime.base
import email.encoders
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "tg_config.json")
DEFAULT_PROXY_POOL = os.path.join(SCRIPT_DIR, "..", "assets", "tg_proxy_pool.json")
DEFAULT_HISTORY = os.path.join(SCRIPT_DIR, "tg_push_history.json")


def load_config(path):
    if not os.path.isfile(path):
        print(f"[错误] 配置文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_proxy_pool(path):
    if not os.path.isfile(path):
        print(f"[警告] 代理池不存在: {path}，将直连")
        return {"nodes": [], "base_local_port": 10900}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history(path):
    """加载推送历史记录"""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(path, history):
    """保存推送历史记录"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 历史记录保存失败: {e}")


def gen_xray_config(node, local_port):
    return {
        "log": {"loglevel": "error"},
        "inbounds": [{
            "tag": "http_in",
            "port": local_port,
            "listen": "127.0.0.1",
            "protocol": "http"
        }],
        "outbounds": [{
            "tag": "proxy_out",
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node["server"],
                    "port": node["port"],
                    "users": [{
                        "id": node["uuid"],
                        "encryption": "none",
                        "flow": node.get("flow", "xtls-rprx-vision")
                    }]
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": node["server_name"],
                    "allowInsecure": node.get("insecure", True),
                    "fingerprint": "chrome"
                }
            }
        }]
    }


def start_xray(xray_bin, node, local_port):
    config = gen_xray_config(node, local_port)
    fd, config_path = tempfile.mkstemp(suffix=".json", prefix="xray_tg_")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)
    try:
        proc = subprocess.Popen(
            [xray_bin, "run", "-c", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)
        if proc.poll() is not None:
            return None, config_path
        return proc, config_path
    except Exception as e:
        print(f"  xray启动异常: {e}")
        return None, config_path


def stop_xray(proc, config_path):
    try:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        os.unlink(config_path)
    except Exception:
        pass


def build_opener(local_port=None):
    if local_port:
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{local_port}",
            "https": f"http://127.0.0.1:{local_port}"
        })
        return urllib.request.build_opener(proxy_handler)
    return urllib.request.build_opener()


def test_proxy(local_port, timeout=8):
    opener = build_opener(local_port)
    try:
        req = urllib.request.Request("https://api.telegram.org", method="HEAD")
        resp = opener.open(req, timeout=timeout)
        return True
    except Exception:
        return False


def api_post(token, method, data, local_port=None, timeout=30):
    """通用Telegram API POST（urlencode表单）"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = urllib.parse.urlencode(data).encode("utf-8")
    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body_text)
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}: {body_text[:100]}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def api_post_document(token, chat_id, file_path, caption="", local_port=None, timeout=120):
    """发送文件附件（multipart/form-data，手动构造避免email库ascii编码问题）。TG推送不脱敏，直接用原始文件名。"""
    if not os.path.isfile(file_path):
        return {"ok": False, "description": f"文件不存在: {file_path}"}

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    filename = os.path.basename(file_path)  # 原始文件名，不脱敏

    # 手动构造multipart/form-data，彻底绕开email库的ascii编码问题
    boundary = "----WebKitFormBoundary" + "".join(random.choices("0123456789abcdef", k=16))
    crlf = b"\r\n"
    body = b""

    # chat_id字段
    body += f"--{boundary}\r\n".encode("utf-8")
    body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body += str(chat_id).encode("utf-8") + crlf

    # caption字段（支持中文/emoji）
    if caption:
        body += f"--{boundary}\r\n".encode("utf-8")
        body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
        body += caption.encode("utf-8") + crlf

    # 文件字段（文件名用RFC 5987编码支持中文）
    with open(file_path, "rb") as f:
        file_data = f.read()
    filename_encoded = urllib.parse.quote(filename)  # URL编码中文文件名
    body += f"--{boundary}\r\n".encode("utf-8")
    body += f'Content-Disposition: form-data; name="document"; filename="{filename_encoded}"\r\n'.encode("utf-8")
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += file_data + crlf

    # 结束标记
    body += f"--{boundary}--\r\n".encode("utf-8")

    opener = build_opener(local_port)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body_text)
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}: {body_text[:100]}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def delete_message(token, chat_id, message_id, local_port=None, timeout=15):
    """撤回/删除一条消息（Bot只能删自己发的，48小时内）"""
    return api_post(token, "deleteMessage", {
        "chat_id": chat_id,
        "message_id": message_id
    }, local_port=local_port, timeout=timeout)


def cleanup_old_messages(token, chat_id, site_name, history, history_path, local_port=None):
    """撤回该站点的所有旧消息（文字+文件），返回撤回统计。
    兼容新旧两种历史记录结构：旧版=纯message_id，新版=含chat_id的字典"""
    if site_name not in history:
        print(f"[撤回] 站点「{site_name}」无历史记录，跳过撤回")
        return 0, 0

    record = history[site_name]
    msg_ids = record.get("message_ids", {})
    if not msg_ids:
        print(f"[撤回] 站点「{site_name}」历史记录为空，跳过")
        return 0, 0

    total = len(msg_ids)
    success = 0
    failed = 0
    print(f"[撤回] 站点「{site_name}」发现 {total} 条旧消息，开始撤回...")

    for key, mid_info in msg_ids.items():
        # 兼容新旧结构：新版是字典{message_id, chat_id}，旧版是纯数字
        if isinstance(mid_info, dict):
            mid = mid_info.get("message_id")
            target_chat = mid_info.get("chat_id", chat_id)
        else:
            mid = mid_info
            target_chat = chat_id
        if not mid:
            continue
        r = delete_message(token, target_chat, mid, local_port=local_port)
        if r.get("ok"):
            print(f"  ✅ 已撤回 [{key}] 消息ID:{mid} (群:{target_chat})")
            success += 1
        else:
            err = r.get("description", "未知")
            print(f"  ⚠️  撤回失败 [{key}] 消息ID:{mid}: {err}")
            failed += 1

    # 撤回完成后清除该站点历史记录
    del history[site_name]
    save_history(history_path, history)
    print(f"[撤回] 完成: 成功{success}条, 失败{failed}条")
    return success, failed


def is_fatal_error(err):
    return "Unauthorized" in err or "chat not found" in err or "wrong file identifier" in err


def push_with_proxy_pool(config, proxy_pool, text, files=None, site_name=None,
                          history_path=None, skip_cleanup=False):
    """使用代理池智能轮换推送。版本更新模式：先撤回旧消息再推新。
    支持分群推送：py文件+文字通知→主群；小程序zip→蚂蚁影视群（如配置了miniapp_push）"""
    token = config["bot"]["token"]
    chat_id = config["bot"]["chat_id"]
    # 蚂蚁影视群配置（小程序单独推送）
    miniapp_cfg = config.get("miniapp_push", {})
    miniapp_chat_id = miniapp_cfg.get("chat_id") if miniapp_cfg.get("enabled") else None
    # 校验miniapp_chat_id是否为有效数字（不是占位符）
    if miniapp_chat_id and not str(miniapp_chat_id).startswith("-"):
        print(f"[警告] 蚂蚁影视群chat_id未配置（当前值: {miniapp_chat_id}），小程序将推送到主群")
        miniapp_chat_id = None
    xray_bin = config.get("xray_binary", os.path.join(SCRIPT_DIR, "xray"))
    if not os.path.isfile(xray_bin):
        xray_bin = "xray"

    nodes = proxy_pool.get("nodes", [])
    files = files or []
    base_port = proxy_pool.get("base_local_port", 10900)
    max_retries = proxy_pool.get("rotation", {}).get("max_retries", 3)
    history_path = history_path or DEFAULT_HISTORY
    history = load_history(history_path)

    # 版本更新：先撤回旧消息
    if site_name and not skip_cleanup:
        # 撤回不需要代理池轮换（用第一个可用节点即可），但需要先启动代理
        # 这里先不撤回，等代理启动后在do_push里撤回
        pass

    def do_push(local_port):
        """在指定代理端口执行完整推送（撤回旧消息→文字→所有文件）"""
        new_msg_ids = {}

        # 1. 版本更新：撤回该站点旧消息
        if site_name and not skip_cleanup:
            cleanup_old_messages(token, chat_id, site_name, history, history_path, local_port=local_port)

        # 2. 推文字通知
        if text:
            r = api_post(token, "sendMessage", {
                "chat_id": chat_id, "text": text
            }, local_port=local_port)
            if not r.get("ok"):
                return r, "文字通知", new_msg_ids
            mid = r["result"]["message_id"]
            new_msg_ids["text"] = mid
            print(f"  ✅ 文字通知发送成功 (ID:{mid})")

        # 3. 逐个推文件附件（TG不脱敏，原始文件名）
        # py文件→主群；小程序zip→蚂蚁影视群（如配置了miniapp_chat_id）
        for fp in files:
            fname = os.path.basename(fp)
            # 根据文件类型选择推送群和caption
            if fname.endswith(".py"):
                target_chat = chat_id
                caption = f"🔮 {fname}（四壳源术）"
                group_label = "主群"
            elif fname.endswith(".zip") and miniapp_chat_id:
                target_chat = miniapp_chat_id
                caption = f"🗃️ {fname}（蚂蚁小程序·暗黑抖音式UI）"
                group_label = "蚂蚁影视群"
            elif fname.endswith(".zip"):
                target_chat = chat_id
                caption = f"🗃️ {fname}（微阁洞天）"
                group_label = "主群"
            else:
                target_chat = chat_id
                caption = f"📎 {fname}"
                group_label = "主群"
            r = api_post_document(token, target_chat, fp, caption=caption, local_port=local_port)
            if not r.get("ok"):
                return r, f"文件 {fname}（{group_label}）", new_msg_ids
            mid = r["result"]["message_id"]
            # 用文件扩展名作为记录key
            key = os.path.splitext(fname)[1].lstrip(".") or f"file{len(new_msg_ids)}"
            new_msg_ids[key] = {"message_id": mid, "chat_id": target_chat}
            print(f"  ✅ 文件 {fname} 推送成功（{group_label}, ID:{mid}）")

        # 4. 保存历史记录
        if site_name:
            history[site_name] = {
                "last_push_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "chat_id": chat_id,
                "miniapp_chat_id": miniapp_chat_id,
                "message_ids": new_msg_ids
            }
            save_history(history_path, history)
            print(f"  📝 历史记录已更新（站点「{site_name}」共{len(new_msg_ids)}条消息）")

        return {"ok": True}, "全部", new_msg_ids

    # 无代理节点时直连
    # 常驻代理优先：检测127.0.0.1:10809是否可用，可用则直接共享使用，不启动临时xray（所有会话共享一个代理进程，避免端口冲突）
    PERMANENT_PROXY_PORT = 10809
    if test_proxy(PERMANENT_PROXY_PORT, timeout=5):
        print(f"[常驻代理] 127.0.0.1:{PERMANENT_PROXY_PORT} 可用，直接共享使用（不启动临时xray）")
        result, stage, _ = do_push(PERMANENT_PROXY_PORT)
        if result.get("ok"):
            print(f"  ✅ 全部推送完成!")
            return result
        else:
            err = result.get("description", "未知错误")
            print(f"  {stage}失败: {err}")
            if is_fatal_error(err):
                return result
            print("  常驻代理推送失败，切换临时代理池重试...")

    if not nodes:
        print("[信息] 无代理节点，尝试直连...")
        result, stage, _ = do_push(None)
        return result

    # 随机打乱节点顺序
    shuffled = nodes[:]
    random.shuffle(shuffled)

    attempted = 0
    for i, node in enumerate(shuffled):
        if attempted >= max_retries:
            break
        local_port = base_port + i
        node_name = node.get("name", f"节点{i+1}")
        print(f"[尝试 {attempted+1}/{max_retries}] {node_name} (端口 {local_port})")

        proc, config_path = start_xray(xray_bin, node, local_port)
        if not proc:
            print("  xray启动失败，跳过")
            stop_xray(proc, config_path)
            attempted += 1
            continue

        if not test_proxy(local_port, timeout=8):
            print("  代理连通性测试失败，切换下一节点")
            stop_xray(proc, config_path)
            attempted += 1
            continue

        result, stage, _ = do_push(local_port)
        stop_xray(proc, config_path)

        if result.get("ok"):
            print(f"  ✅ 全部推送完成!")
            return result
        else:
            err = result.get("description", "未知错误")
            print(f"  {stage}失败: {err}")
            if is_fatal_error(err):
                print("  [终止] 致命错误，换代理无用")
                return result
            attempted += 1

    return {"ok": False, "description": f"所有{min(max_retries, len(nodes))}个代理节点均失败"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Bot推送（代理池轮换·版本更新撤回·TG不脱敏）")
    parser.add_argument("message", nargs="?", help="文字通知内容")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")
    parser.add_argument("--chat-id", help="覆盖配置中的chat_id")
    parser.add_argument("--token", help="覆盖配置中的bot token")
    parser.add_argument("--file", action="append", default=[], help="推送文件附件（可多次指定）")
    parser.add_argument("--site", help="站点名称（用于版本更新：撤回该站点旧消息再推新）")
    parser.add_argument("--clean", action="store_true", help="只撤回指定站点旧消息，不推送新内容")
    parser.add_argument("--skip-cleanup", action="store_true", help="跳过撤回旧消息（直接追加推送）")
    parser.add_argument("--history", action="store_true", help="查看推送历史记录")
    parser.add_argument("--list-nodes", action="store_true", help="列出代理池所有节点")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.token:
        config["bot"]["token"] = args.token
    if args.chat_id:
        config["bot"]["chat_id"] = args.chat_id

    proxy_pool_path = config.get("proxy_pool", DEFAULT_PROXY_POOL)
    proxy_pool = load_proxy_pool(proxy_pool_path)
    history_path = config.get("history_file", DEFAULT_HISTORY)

    if args.list_nodes:
        print(f"代理池共 {len(proxy_pool.get('nodes',[]))} 个节点:")
        for i, n in enumerate(proxy_pool["nodes"], 1):
            print(f"  {i:2d}. [{n.get('region','?')}] {n.get('name','?')} -> {n['server']}:{n['port']}")
        return

    if args.history:
        history = load_history(history_path)
        if not history:
            print("暂无推送历史记录")
            return
        print(f"推送历史记录（共{len(history)}个站点）:")
        for site, rec in history.items():
            print(f"\n  【{site}】")
            print(f"    最后推送: {rec.get('last_push_time', '?')}")
            print(f"    群ID: {rec.get('chat_id', '?')}")
            print(f"    消息ID:")
            for k, v in rec.get("message_ids", {}).items():
                print(f"      {k}: {v}")
        return

    if args.clean:
        if not args.site:
            print("[错误] --clean 必须配合 --site 指定站点名")
            sys.exit(1)
        history = load_history(history_path)
        print(f"仅撤回模式：站点「{args.site}」")
        # 撤回需要代理，用第一个节点
        token = config["bot"]["token"]
        chat_id = config["bot"]["chat_id"]
        nodes = proxy_pool.get("nodes", [])
        if nodes:
            xray_bin = config.get("xray_binary", os.path.join(SCRIPT_DIR, "xray"))
            proc, cp = start_xray(xray_bin, nodes[0], 10950)
            if proc:
                cleanup_old_messages(token, chat_id, args.site, history, history_path, local_port=10950)
                stop_xray(proc, cp)
            else:
                print("代理启动失败，尝试直连撤回...")
                cleanup_old_messages(token, chat_id, args.site, history, history_path)
        else:
            cleanup_old_messages(token, chat_id, args.site, history, history_path)
        return

    if not args.message and not args.file:
        parser.print_help()
        sys.exit(1)

    if not config.get("bot", {}).get("token"):
        print("[错误] 配置中缺少 bot.token")
        sys.exit(1)
    if not config.get("bot", {}).get("chat_id"):
        print("[错误] 配置中缺少 bot.chat_id")
        sys.exit(1)

    valid_files = []
    for fp in args.file:
        if os.path.isfile(fp):
            valid_files.append(fp)
        else:
            print(f"[警告] 文件不存在，跳过: {fp}")

    print(f"推送目标: chat_id={config['bot']['chat_id']}")
    if args.site:
        mode = "版本更新（先撤回旧消息再推新）" if not args.skip_cleanup else "追加推送（不撤回）"
        print(f"站点: {args.site} ({mode})")
    if args.message:
        print(f"文字通知: {len(args.message)} 字符")
    if valid_files:
        print(f"文件附件: {len(valid_files)} 个（TG不脱敏，原始文件名）")
        for f in valid_files:
            print(f"  - {os.path.basename(f)} ({os.path.getsize(f)} bytes)")
    print(f"代理池: {len(proxy_pool.get('nodes',[]))} 个节点")
    print("-" * 50)

    result = push_with_proxy_pool(
        config, proxy_pool, args.message,
        files=valid_files,
        site_name=args.site,
        history_path=history_path,
        skip_cleanup=args.skip_cleanup
    )

    if result.get("ok"):
        print("\n✅ 推送完成")
        sys.exit(0)
    else:
        print(f"\n❌ 推送失败: {result.get('description','未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
