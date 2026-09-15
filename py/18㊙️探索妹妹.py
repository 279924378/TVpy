
# -*- coding: utf-8 -*-
# 探索妹妹 Spider
# 站点: https://www.tsmm3.boats/tsmm/
# 真实结构: <a href="/123.html"><img src="..."/></a> + const rawUrl='xxx.m3u8'

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): return {}
        def categoryContent(self, tid, pg, filter, extend): return {}
        def detailContent(self, ids): return {}
        def searchContent(self, key, quick, pg): return {}
        def playerContent(self, flag, id, vipFlags): return {}
        def localProxy(self, param): return [404, "text/plain", ""]
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def getName(self): return ""

class Spider(BaseSpider):

    def init(self, extend=""):
        self.siteUrl = "https://www.tsmm3.boats"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.siteUrl + "/",
        }

    def homeContent(self, filter):
        result = {}
        class_parse = [
            {"type_name": "绝美少女", "type_id": "20"},
            {"type_name": "激情口交", "type_id": "21"},
            {"type_name": "亚洲日韩", "type_id": "22"},
            {"type_name": "人妖激情", "type_id": "23"},
            {"type_name": "重咸口味", "type_id": "24"},
            {"type_name": "国产专区", "type_id": "25"},
            {"type_name": "日韩专区", "type_id": "26"},
            {"type_name": "欧美专区", "type_id": "27"},
            {"type_name": "卡通动漫", "type_id": "28"},
            {"type_name": "三级伦理", "type_id": "29"},
        ]
        result["class"] = class_parse
        result["filters"] = {}
        result["list"] = []
        return result

    def categoryContent(self, tid, pg, filter, extend):
        import urllib.request
        import re
        result = {}
        url = f"{self.siteUrl}/vodtype/{tid}.html"
        if int(pg) > 1:
            url = f"{self.siteUrl}/vodtype/{tid}-{pg}.html"
        req = urllib.request.Request(url, headers=self.headers)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")
        
        # 真实结构: <div class="recommended-grids english-grid">...<a href="/123.html"><img src="..."/></a>...<h5><a href="/123.html" class="title">标题</a></h5>...
        items = re.findall(
            r'<a href="/(\d+)\.html"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*/>.*?<h5>.*?<a[^>]*class="title"[^>]*>([^<]*)</a>',
            html, re.S
        )
        
        video_list = []
        for vid, pic, title in items[:60]:
            video_list.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": "",
            })
        result["list"] = video_list
        result["page"] = pg
        result["pagecount"] = 100
        result["limit"] = 60
        result["total"] = 6000
        return result

    def detailContent(self, ids):
        import urllib.request
        import re
        result = {}
        vid = ids[0]
        url = f"{self.siteUrl}/{vid}.html"
        req = urllib.request.Request(url, headers=self.headers)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")
        
        # 真实结构: const rawUrl = 'https://xxx.m3u8'
        m3u8_match = re.search(r"rawUrl\s*=\s*['\"](https?://[^'\"]+\.m3u8[^'\"]*)['\"]", html)
        m3u8_url = ""
        if m3u8_match:
            m3u8_url = m3u8_match.group(1)
        
        # 标题
        title_match = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
        title = title_match.group(1).strip() if title_match else vid
        
        result["list"] = [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_letter": "",
            "vod_class": "",
            "vod_duration": "",
            "vod_content": "",
            "vod_play_from": "高清",
            "vod_play_url": m3u8_url,
        }]
        return result

    def searchContent(self, key, quick, pg):
        result = {}
        result["list"] = []
        result["page"] = pg
        result["pagecount"] = 1
        result["limit"] = 20
        result["total"] = 0
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        result["parse"] = 0
        result["jx"] = 0
        result["url"] = id
        result["header"] = self.headers
        return result

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def getName(self):
        return "探索妹妹"
