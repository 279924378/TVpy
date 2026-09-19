#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成人快播 Spider - 四壳通用Python Spider
站点: https://www.crkb5.yachts/crkb/
"""

import re
import urllib.request
import urllib.parse
import json

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass
        def homeContent(self, filter):
            pass
        def categoryContent(self, tid, pg, filter, extend):
            pass
        def detailContent(self, ids):
            pass
        def searchContent(self, key, quick, pg="1"):
            pass
        def playerContent(self, flag, id, vipFlags):
            pass
        def localProxy(self, params):
            return [404, "text/plain", ""]
        def isVideoFormat(self, url):
            return False
        def manualVideoCheck(self):
            return False
        def getName(self):
            return "成人快播"
        def getDependence(self):
            return []
        def destroy(self):
            pass


class Spider(Spider):
    def init(self, extend=""):
        self.siteUrl = "https://www.crkb5.yachts/crkb"
        self.rawUrl = "https://www.crkb5.yachts/crkb"
        return "成人快播"

    def homeContent(self, filter):
        result = {}
        class_name = []
        for i in range(20, 32):
            class_name.append({
                "type_name": f"分类{i}",
                "type_id": str(i)
            })
        result["class"] = class_name
        result["filters"] = {}
        result["list"] = self.categoryContent("20", "1", False, {})["list"]
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        url = f"{self.siteUrl}/vodtype/{tid}.html"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        
        list = []
        items = re.findall(r'<a href="(/\d+\.html)" class="video-card">(.*?)</a>', html, re.S)
        for href, item in items:
            try:
                title = re.search(r'<div class="title">(.*?)</div>', item).group(1).strip()
                img = re.search(r'src="([^"]*)"', item).group(1)
                id = re.search(r'/(\d+)\.html', href).group(1)
                list.append({
                    "vod_id": id,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
            except:
                continue
        
        result["list"] = list
        result["page"] = int(pg)
        result["pagecount"] = 100
        result["limit"] = 20
        result["total"] = 2000
        return result

    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{self.siteUrl}/{vod_id}.html"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        
        m3u8 = re.search(r'player_data\s*=\s*{[^}]*url\s*:\s*"([^"]*)"', html)
        if not m3u8:
            m3u8 = re.search(r"rawUrl\s*=\s*'([^']*)'", html)
        if not m3u8:
            m3u8 = re.search(r'"(https?://[^"]*\.m3u8[^"]*)"', html)
        
        if m3u8:
            play_url = m3u8.group(1)
        else:
            play_url = ""
        
        title = re.search(r'<title>(.*?)</title>', html).group(1)
        
        vod_list = [{
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "成人快播",
            "vod_play_url": play_url
        }]
        
        return {"list": vod_list}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.siteUrl}/vodsearch/{urllib.parse.quote(key)}.html"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        
        list = []
        items = re.findall(r'<a href="(/\d+\.html)" class="video-card">(.*?)</a>', html, re.S)
        for href, item in items:
            try:
                title = re.search(r'<div class="title">(.*?)</div>', item).group(1).strip()
                img = re.search(r'src="([^"]*)"', item).group(1)
                id = re.search(r'/(\d+)\.html', href).group(1)
                list.append({
                    "vod_id": id,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
            except:
                continue
        
        return {"list": list, "page": int(pg), "pagecount": 10, "limit": 20, "total": 200}

    def playerContent(self, flag, id, vipFlags):
        url = f"{self.siteUrl}/{id}.html"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        
        m3u8 = re.search(r'player_data\s*=\s*{[^}]*url\s*:\s*"([^"]*)"', html)
        if not m3u8:
            m3u8 = re.search(r"rawUrl\s*=\s*'([^']*)'", html)
        if not m3u8:
            m3u8 = re.search(r'"(https?://[^"]*\.m3u8[^"]*)"', html)
        
        if m3u8:
            play_url = m3u8.group(1)
        else:
            play_url = ""
        
        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": self.rawUrl + "/",
                "Origin": self.rawUrl
            }
        }

    def localProxy(self, params):
        return [404, "text/plain", ""]

    def getName(self):
        return "成人快播"

    def getDependence(self):
        return []

    def destroy(self):
        pass
