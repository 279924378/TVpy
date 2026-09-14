#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox Spider 健康检测脚本（GitHub Actions版）
功能：遍历tvbox.json里所有spider，检测每个源是否失效
测试方案：
  1. GitHub Actions环境本身在国外 → 相当于"国外直连"测试
  2. 同时测试国内站点能不能访问（判断是否需要代理）
输出：失效源列表 + 推送到TG群
"""
import json
import os
import re
import urllib.request
import urllib.error
import ssl
from datetime import datetime

# 配置
TVBOX_JSON_URL = "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/tvbox.json"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TIMEOUT = 15

UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 忽略SSL证书验证（有些站点证书有问题）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_url(url, timeout=TIMEOUT):
    """测试URL能不能访问，返回 (status_code, size, elapsed)"""
    import time
    start = time.time()
    headers = {
        "User-Agent": UA_CHROME,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
        elapsed = time.time() - start
        size = len(resp.read())
        return (resp.status, size, elapsed)
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return (e.code, 0, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        return (0, 0, elapsed)


def extract_domain_from_spider(py_url):
    """从py文件URL里下载内容，提取domain"""
    try:
        req = urllib.request.Request(py_url, headers={"User-Agent": UA_CHROME})
        resp = urllib.request.urlopen(req, timeout=30, context=SSL_CTX)
        content = resp.read().decode("utf-8", errors="replace")
        
        # 提取domain = "https://xxx"
        match = re.search(r'domain\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        
        # 备用：找base = "https://xxx"
        match = re.search(r'base\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        
        return None
    except Exception as e:
        print(f"  ❌ 下载py失败: {e}")
        return None


def send_telegram(text):
    """推送到TG群"""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  未配置TELEGRAM_BOT_TOKEN/CHAT_ID，跳过推送")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            print("✅ TG推送成功")
        else:
            print(f"❌ TG推送失败: {result.get('description')}")
    except Exception as e:
        print(f"❌ TG推送异常: {e}")


def main():
    print("=" * 60)
    print("TVBox Spider 健康检测启动")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 读取tvbox.json
    print("\n[1] 读取tvbox.json...")
    try:
        req = urllib.request.Request(TVBOX_JSON_URL, headers={"User-Agent": UA_CHROME})
        resp = urllib.request.urlopen(req, timeout=30, context=SSL_CTX)
        tvbox = json.loads(resp.read().decode("utf-8"))
        spiders = tvbox.get("spider", [])
        print(f"  ✅ 共 {len(spiders)} 个spider")
    except Exception as e:
        print(f"  ❌ 读取tvbox.json失败: {e}")
        send_telegram(f"❌ <b>健康检测失败</b>\n读取tvbox.json失败: {e}")
        return
    
    # 2. 逐个检测
    print("\n[2] 逐个检测spider...")
    alive = []
    dead = []
    slow = []
    
    for i, sp in enumerate(spiders):
        name = sp.get("name", "未知")
        api = sp.get("api", "")
        key = sp.get("key", "")
        
        print(f"\n  [{i+1}/{len(spiders)}] {name}...")
        
        # 提取domain
        domain = extract_domain_from_spider(api)
        if not domain:
            print(f"    ⚠️  无法提取domain，标记为未知")
            dead.append({"name": name, "domain": "", "reason": "无法提取domain"})
            continue
        
        print(f"    domain: {domain}")
        
        # 测试首页能不能访问
        status, size, elapsed = fetch_url(domain)
        
        if status == 200 and size > 1000:
            print(f"    ✅ HTTP {status} | {size} bytes | {elapsed:.1f}s")
            if elapsed > 5:
                slow.append({"name": name, "domain": domain, "elapsed": elapsed})
            else:
                alive.append({"name": name, "domain": domain, "elapsed": elapsed})
        elif status == 0:
            print(f"    ❌ 连接失败（超时/被墙）| {elapsed:.1f}s")
            dead.append({"name": name, "domain": domain, "reason": "连接失败（需代理）"})
        elif status >= 500:
            print(f"    ⚠️  HTTP {status}（服务器错误）| {elapsed:.1f}s")
            dead.append({"name": name, "domain": domain, "reason": f"HTTP {status}（服务器错误）"})
        else:
            print(f"    ⚠️  HTTP {status} | {size} bytes | {elapsed:.1f}s")
            # 403/404等也算部分失效
            dead.append({"name": name, "domain": domain, "reason": f"HTTP {status}"})
    
    # 3. 输出报告
    print("\n" + "=" * 60)
    print("检测报告")
    print("=" * 60)
    print(f"  ✅ 正常: {len(alive)} 个")
    print(f"  ⚠️  慢: {len(slow)} 个")
    print(f"  ❌ 失效: {len(dead)} 个")
    
    if dead:
        print("\n❌ 失效源列表:")
        for d in dead:
            print(f"  - {d['name']}: {d['reason']}")
    
    if slow:
        print("\n⚠️  慢源列表:")
        for s in slow:
            print(f"  - {s['name']}: {s['elapsed']:.1f}s")
    
    # 4. 推送到TG群
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"""📊 <b>Spider健康检测报告</b>

⏰ 时间: {now}
📦 总源数: {len(spiders)}

✅ 正常: {len(alive)} 个
⚠️ 慢源: {len(slow)} 个
❌ 失效: {len(dead)} 个"""

    if dead:
        report += "\n\n❌ <b>失效源:</b>\n"
        for d in dead[:10]:  # 最多列10个
            report += f"  • {d['name']}\n    <i>{d['reason']}</i>\n"
        if len(dead) > 10:
            report += f"  ... 等共 {len(dead)} 个"
    
    if slow:
        report += "\n\n⚠️ <b>慢源:</b>\n"
        for s in slow[:5]:
            report += f"  • {s['name']}: {s['elapsed']:.1f}s\n"
    
    report += f"\n\n📡 订阅: https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/tvbox.json"
    
    # 只有有失效源才推送
    if dead:
        print("\n[3] 推送失效源到TG群...")
        send_telegram(report)
    else:
        print("\n[3] 所有源正常，不推送TG群")
    
    print("\n" + "=" * 60)
    print("检测完成！")
    
    # 返回码：有失效源返回1，全正常返回0
    exit(1 if dead else 0)


if __name__ == "__main__":
    main()
