# -*- coding: utf-8 -*-
"""
六区影视 - 四壳通用Python Spider
站点: https://6181027.xyz/（六区，从跳转站解析出来的真实域名）
结构: 自定义CMS，视频信息直接编码在URL里（?v=m3u8&b=封面图）
列表URL: /index.php/vod/type/id/{cid}.html
视频URL: /html/dcdc/{乱码标题}.html?v={m3u8}&b={封面图}
封面: img.lazy的data-original属性
标题: p.km-script标签
注意: 直连可访问（不用加代理行）
"""

import re
import json
import urllib.request
import urllib.parse
import urllib.error

# ==================== 双协议兼容基类 ====================
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            self.extend = {}
        def init(self, extend):
            self.extend = extend if isinstance(extend, dict) else {}
        def isVideoFormat(self, url):
            return any(url.lower().endswith(ext) for ext in ['.m3u8', '.mp4', '.flv', '.ts'])
        def homeContent(self, filter):
            return {}
        def categoryContent(self, tid, pg, filter, extend):
            return {}
        def detailContent(self, ids):
            return {}
        def searchContent(self, key, quick, pg):
            return {}
        def playerContent(self, flag, id, vipFlags):
            return {}
        def localProxy(self, param):
            return [404, "text/plain", ""]
        def getDependence(self):
            return ""
        def destroy(self):
            pass

# ==================== 主Spider类 ====================
class Spider(Spider):
    domain = "https://6181027.xyz"
    siteName = "六区影视"
    
    # 分类硬编码
    CATEGORIES = [
        {"type_id": "13", "type_name": "一区"},
        {"type_id": "1", "type_name": "二区"},
        {"type_id": "66", "type_name": "三区"},
        {"type_id": "5", "type_name": "四区"},
        {"type_id": "2", "type_name": "五区"},
        {"type_id": "44", "type_name": "六区"},
        {"type_id": "40", "type_name": "七区"},
        {"type_id": "66", "type_name": "八区"},
        {"type_id": "35", "type_name": "九区"},
        {"type_id": "27", "type_name": "漫画"},
    ]
    
    UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    
    def __init__(self):
        super().__init__()
        self.extend = {}
    
    def init(self, extend=""):
        if isinstance(extend, dict):
            self.extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        else:
            self.extend = {}
    
    def getDependence(self):
        return ""
    
    def destroy(self):
        pass
    
    # ==================== HTTP请求 ====================
    def _fetch(self, url, timeout=20):
        headers = {
            "User-Agent": self.UA_CHROME,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Referer": self.domain + "/",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            content = resp.read()
            return content.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            try:
                return e.read().decode("utf-8", errors="replace")
            except Exception:
                return ""
        except Exception:
            return ""
    
    def _strip_tags(self, html):
        if not html:
            return ""
        return re.sub(r"<[^>]+>", "", html).strip()
    
    # ==================== 解析列表（vodbox结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_urls = set()
        
        # 找所有vodbox项
        items = re.findall(r'<a class="vodbox"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
        
        for href, item_html in items:
            try:
                # 从href里解析m3u8和封面图
                # 格式: /html/dcdc/{标题}.html?v={m3u8}&b={封面图}
                m3u8_url = ""
                cover_url = ""
                
                # 提取v参数（m3u8）
                v_match = re.search(r'[?&]v=([^&]+)', href)
                if v_match:
                    m3u8_url = urllib.parse.unquote(v_match.group(1))
                
                # 提取b参数（封面图）
                b_match = re.search(r'[?&]b=([^&]+)', href)
                if b_match:
                    cover_url = urllib.parse.unquote(b_match.group(1))
                
                if not m3u8_url:
                    continue
                
                # 标题：从p.km-script提取
                vod_name = ""
                title_match = re.search(r'<p class="km-script">(.*?)</p>', item_html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1)).strip()
                
                if not vod_name or len(vod_name) < 3:
                    # 备用：从URL里提取
                    vod_name = f"视频{len(videos)+1}"
                
                # 封面：优先从img的data-original提取，备用从b参数
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*data-original="([^"]+\.(?:jpg|jpeg|png))"', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                elif cover_url:
                    vod_pic = cover_url
                
                # 用m3u8的hash作为vod_id（唯一标识）
                vod_id = m3u8_url
                if vod_id in seen_urls:
                    continue
                seen_urls.add(vod_id)
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
            except Exception:
                continue
        return videos
    
    # ==================== 1. homeContent ====================
    def homeContent(self, filter=False):
        classes = []
        for cat in self.CATEGORIES:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })
        return {"class": classes, "filters": {}}
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        
        url = f"{self.domain}/index.php/vod/type/id/{tid}.html"
        if pg > 1:
            url = f"{self.domain}/index.php/vod/type/id/{tid}-{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        return {
            "page": pg,
            "pagecount": pg,
            "limit": 20,
            "total": len(videos),
            "list": videos,
        }
    
    # ==================== 3. detailContent（直接返回m3u8） ====================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]
        
        list_data = []
        for m3u8_url in ids:
            try:
                m3u8_url = str(m3u8_url).strip()
                if not m3u8_url:
                    continue
                
                # 直接返回m3u8，不需要访问详情页
                vod_id = m3u8_url
                vod_name = f"视频{len(list_data)+1}"
                vod_pic = ""
                
                # 尝试从m3u8 URL推断封面图（不太准确，留空）
                # 实际上封面图已经在列表页解析过了，这里留空就行
                
                vod_play_from = "六区影视"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "六区影视",
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": "",
                    "vod_year": "",
                    "vod_area": "",
                    "vod_tags": "",
                    "vod_douban_score": "",
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                }
                list_data.append(detail)
            except Exception:
                continue
        
        return {"list": list_data}
    
    # ==================== 4. searchContent ====================
    def searchContent(self, key, quick=False, pg=1):
        return {
            "page": pg,
            "pagecount": 0,
            "limit": 20,
            "total": 0,
            "list": [],
        }
    
    # ==================== 5. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        
        url = id
        header = {
            "User-Agent": self.UA_CHROME,
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": header,
        }
    
    def localProxy(self, param):
        if not param or "do" not in param:
            return [404, "text/plain", ""]
        do = param.get("do", "")
        if do == "ck":
            url = param.get("url", "")
            if url:
                try:
                    headers = {"User-Agent": self.UA_CHROME}
                    req = urllib.request.Request(url, headers=headers)
                    resp = urllib.request.urlopen(req, timeout=15)
                    content = resp.read()
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    return [200, content_type, content]
                except Exception:
                    pass
        return [404, "text/plain", ""]


# ==================== 调试入口 ====================
if __name__ == "__main__":
    import sys
    sp = Spider()
    sp.init("{}")
    
    print("=" * 60)
    print("六区影视 Spider 自测")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']:5s}  {c['type_name']}")
    
    print("\n[2] categoryContent (id=13, page=1):")
    cat = sp.categoryContent("13", 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    for v in cat.get("list", [])[:3]:
        print(f"    {v['vod_name'][:40]}")
        print(f"      封面: {v['vod_pic'][:60]}")
        print(f"      m3u8: {v['vod_id'][:80]}")
    
    if cat.get("list"):
        first_m3u8 = cat["list"][0]["vod_id"]
        print(f"\n[3] detailContent (id={first_m3u8[:50]}...):")
        detail = sp.detailContent([first_m3u8])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d['vod_name'][:50]}")
            print(f"  播放线路: {d['vod_play_from']}")
            play_urls = d['vod_play_url'].split("#")
            print(f"  播放集数: {len(play_urls)}")
            for pu in play_urls[:1]:
                print(f"    {pu[:100]}")
        else:
            print("  无详情数据")
    
    print("\n" + "=" * 60)
    print("自测完成!")
