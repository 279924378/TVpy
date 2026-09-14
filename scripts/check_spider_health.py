#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox Spider 深度健康检测脚本（GitHub Actions版）
和本地自测一模一样：真的运行Spider代码，调用homeContent/categoryContent/detailContent
"""
import json
import os
import sys
import re
import importlib.util
import urllib.request
import urllib.error
import ssl
import time
from datetime import datetime

# 配置
TVBOX_JSON_URL = "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/tvbox.json"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TIMEOUT = 20

# 代理池（GitHub Actions在国外，国内站点需要走代理）
PROXY_POOL = [
    None,  # 先试直连
    "http://127.0.0.1:10809",  # 备用代理（如果有的话）
]

UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 忽略SSL证书验证
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_url(url, timeout=TIMEOUT):
    """测试URL能不能访问，返回 (status_code, size, elapsed)"""
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


def download_py(url, local_path):
    """下载py文件到本地（自动处理中文URL编码）"""
    # 把URL路径部分做编码，处理中文文件名
    parsed = urllib.parse.urlparse(url)
    encoded_path = urllib.parse.quote(parsed.path)
    encoded_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))
    
    req = urllib.request.Request(encoded_url, headers={"User-Agent": UA_CHROME})
    resp = urllib.request.urlopen(req, timeout=30, context=SSL_CTX)
    with open(local_path, "wb") as f:
        f.write(resp.read())


def load_spider_class(py_path):
    """动态加载py文件里的Spider类"""
    spec = importlib.util.spec_from_file_location("spider_module", py_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Spider


def test_spider(spider_class, name):
    """真的运行Spider代码，检测三个接口"""
    results = {"name": name, "home": False, "category": False, "detail": False, "errors": []}
    
    try:
        # 1. 初始化
        sp = spider_class()
        sp.init("{}")
        
        # 2. 测试homeContent
        try:
            home = sp.homeContent()
            classes = home.get("class", [])
            if len(classes) >= 3:
                results["home"] = True
                results["class_count"] = len(classes)
            else:
                results["errors"].append(f"homeContent分类数太少: {len(classes)}")
        except Exception as e:
            results["errors"].append(f"homeContent异常: {str(e)[:80]}")
        
        # 3. 测试categoryContent
        try:
            if results["home"]:
                first_cid = home["class"][0]["type_id"]
                cat = sp.categoryContent(first_cid, 1)
                video_list = cat.get("list", [])
                if len(video_list) >= 5:
                    results["category"] = True
                    results["video_count"] = len(video_list)
                    results["first_vod_id"] = video_list[0].get("vod_id", "")
                elif len(video_list) == 0:
                    results["errors"].append(f"categoryContent返回空（可能需国内网络/代理）")
                    results["network_issue"] = True
                else:
                    results["errors"].append(f"categoryContent视频太少: {len(video_list)}")
        except Exception as e:
            err_str = str(e)[:80]
            results["errors"].append(f"categoryContent异常: {err_str}")
            # 网络类异常标记为网络问题
            if "timed out" in err_str or "Connection" in err_str or "SSL" in err_str:
                results["network_issue"] = True
        
        # 4. 测试detailContent
        try:
            if results["category"] and results.get("first_vod_id"):
                detail = sp.detailContent([results["first_vod_id"]])
                detail_list = detail.get("list", [])
                if detail_list:
                    vod_play_url = detail_list[0].get("vod_play_url", "")
                    if ".m3u8" in vod_play_url or ".mp4" in vod_play_url:
                        results["detail"] = True
                    else:
                        results["errors"].append("detailContent无播放地址")
                else:
                    results["errors"].append("detailContent无详情数据")
        except Exception as e:
            results["errors"].append(f"detailContent异常: {str(e)[:80]}")
    
    except Exception as e:
        results["errors"].append(f"初始化异常: {str(e)[:80]}")
    
    # 判定
    if results["home"] and results["category"] and results["detail"]:
        results["status"] = "alive"
    elif results.get("network_issue"):
        # 网络问题（GitHub Actions在国外，国内站点访问不了）
        results["status"] = "network"
    elif results["home"] and results["category"]:
        results["status"] = "partial"
    else:
        results["status"] = "dead"
    
    return results


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
    print("TVBox Spider 深度健康检测启动")
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
    
    # 2. 逐个深度检测
    print("\n[2] 逐个深度检测（真的运行Spider代码）...")
    alive = []
    partial = []
    dead = []
    network = []
    
    for i, sp in enumerate(spiders):
        name = sp.get("name", "未知")
        api = sp.get("api", "")
        
        print(f"\n  [{i+1}/{len(spiders)}] {name}...")
        
        # 下载py文件
        py_path = f"/tmp/spider_{i}.py"
        try:
            download_py(api, py_path)
        except Exception as e:
            print(f"    ❌ 下载py失败: {str(e)[:60]}")
            dead.append({"name": name, "errors": [f"下载py失败: {str(e)[:60]}"]})
            continue
        
        # 加载并测试
        try:
            spider_class = load_spider_class(py_path)
            result = test_spider(spider_class, name)
            
            if result["status"] == "alive":
                print(f"    ✅ 全接口通过 ({result.get('class_count','?')}分类/{result.get('video_count','?')}视频)")
                alive.append(result)
            elif result["status"] == "partial":
                print(f"    ⚠️  部分失效: {result['errors'][0]}")
                partial.append(result)
            elif result["status"] == "network":
                print(f"    🌐 网络问题（需国内网络验证）: {result['errors'][0]}")
                network.append(result)
            else:
                print(f"    ❌ 失效: {result['errors'][0]}")
                dead.append(result)
        except Exception as e:
            err_str = str(e)[:60]
            if "No module named" in err_str or "ImportError" in err_str:
                print(f"    📦 缺依赖: {err_str}")
                network.append({"name": name, "errors": [f"缺依赖: {err_str}"]})
            else:
                print(f"    ❌ 加载失败: {err_str}")
                dead.append({"name": name, "errors": [f"加载失败: {err_str}"]})
    
    # 3. 输出报告
    print("\n" + "=" * 60)
    print("深度检测报告")
    print("=" * 60)
    print(f"  ✅ 全正常: {len(alive)} 个")
    print(f"  🌐 网络问题(需国内验证): {len(network)} 个")
    print(f"  ⚠️  部分失效: {len(partial)} 个")
    print(f"  ❌ 完全失效: {len(dead)} 个")
    
    if dead:
        print("\n❌ 完全失效列表:")
        for d in dead:
            print(f"  - {d['name']}: {d['errors'][0]}")
    
    if partial:
        print("\n⚠️  部分失效列表:")
        for p in partial:
            print(f"  - {p['name']}: {p['errors'][0]}")
    
    if network:
        print("\n🌐 网络问题列表（GitHub Actions在国外，国内站点访问不了）:")
        for n in network[:10]:
            print(f"  - {n['name']}: {n['errors'][0]}")
    
    # 4. 推送到TG群
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"""📊 <b>Spider深度健康检测报告</b>

⏰ 时间: {now}
📦 总源数: {len(spiders)}
🔬 检测方式: 真的运行Spider代码（三接口全测）
🌍 检测环境: GitHub Actions（国外服务器）

✅ 全正常: {len(alive)} 个
🌐 网络问题(需国内验证): {len(network)} 个
⚠️ 部分失效: {len(partial)} 个
❌ 完全失效: {len(dead)} 个"""

    if dead:
        report += "\n\n❌ <b>完全失效:</b>\n"
        for d in dead[:10]:
            report += f"  • {d['name']}\n    <i>{d['errors'][0]}</i>\n"
        if len(dead) > 10:
            report += f"  ... 等共 {len(dead)} 个"
    
    if partial:
        report += "\n\n⚠️ <b>部分失效:</b>\n"
        for p in partial[:5]:
            report += f"  • {p['name']}\n    <i>{p['errors'][0]}</i>\n"
    
    if network:
        report += f"\n\n🌐 <b>网络问题（{len(network)}个，GitHub Actions国外访问不了，不算失效）:</b>\n"
        report += "  这些源在国内手机上应该是正常的，只是GitHub Actions在国外访问不了。\n"
        for n in network[:5]:
            report += f"  • {n['name']}\n"
        if len(network) > 5:
            report += f"  ... 等共 {len(network)} 个"
    
    report += f"\n\n📡 订阅: https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/tvbox.json"
    
    # 只有真的失效或部分失效才推送（网络问题不单独推，附在报告里）
    if dead or partial:
        print("\n[3] 推送检测结果到TG群...")
        send_telegram(report)
    else:
        print("\n[3] 没有真失效的源，不推送TG群")
    
    print("\n" + "=" * 60)
    print("检测完成！")
    
    # 返回码：有失效源返回1
    exit(1 if (dead or partial) else 0)


if __name__ == "__main__":
    main()
