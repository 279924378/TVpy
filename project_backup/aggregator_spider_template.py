# coding=utf-8
# 聚合站爬虫模板（多源聚合+AES加密+图片分片代理+m3u8广告清洗）
# 铁律17：广告预检 has_ads=True（模板默认保留完整m3u8广告处理能力：localProxy+_clean_m3u8+_is_ad_segment），实际使用时需用detect_m3u8_ads检测目标站点真实m3u8后更新此注释
import base64
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urljoin

import requests
from Crypto.Cipher import AES

try:
    from base.spider import BaseSpider as _BaseSpider
    _HAS_BASE = True
except Exception:
    _HAS_BASE = False
    class _BaseSpider:
        pass

JSON_API = 'https://REPLACE_JSON_API'
SEARCH_API = 'https://REPLACE_SEARCH_API'
PIC_API = 'https://REPLACE_PIC_API'
HOST = 'https://REPLACE_HOST'
VIDEO_DOMAINS = ['https://REPLACE_CDN_1', 'https://REPLACE_CDN_2']
K2 = b'REPLACE_32BYTE_AES_KEY'
UA = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36'
PAGE_SIZE = 20
BUNDLE_SIZE = 200
BUNDLE_PAGES = BUNDLE_SIZE // PAGE_SIZE
CACHE_TTL = 180

_proxy_port = None
_proxy_lock = threading.Lock()

# ========== 铁律11：敏感词古典映射脱敏表 ==========
CLASSICAL_MAP = {
    "成人": "风月", "色情": "风月", "情色": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
    "AV": "光影", "av": "光影", "三级": "风月",
    "激情": "云雨", "做爱": "云雨", "性交": "交欢", "欲": "情思", "高潮": "云端",
    "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱",
    "迷奸": "迷占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
    "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
    "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人", "护士": "药女",
    "教师": "先生", "医生": "郎中", "警察": "捕快", "军人": "军爷",
    "秘书": "掌印", "老板": "东家", "丈夫": "夫君", "妻子": "拙荆",
    "情人": "相好", "小三": "外遇", "二奶": "外室", "出轨": "翻墙",
    "偷情": "私会", "通奸": "私通", "嫖娼": "寻花", "卖淫": "卖身",
    "妓女": "花娘", "性骚扰": "轻薄", "猥亵": "猥亵", "露阴": "曝玉",
    "咸猪手": "禄山爪", "丝袜": "丝履", "网袜": "网履", "内衣": "亵衣",
    "内裤": "亵裤", "情趣": "风月", "春药": "催情", "巨乳": "丰盈",
    "爆乳": "丰盈", "胸": "酥胸", "乳": "玉兔", "美乳": "玉兔",
    "臀": "玉臀", "屁股": "玉臀", "脚": "莲步", "玉足": "莲步",
    "腿": "玉腿", "裸体": "玉体", "全裸": "玉体", "半裸": "半褪",
    "走光": "泄春", "露点": "泄玉", "自慰": "弄玉", "口交": "含朱",
    "口活": "含朱", "肛交": "后庭", "屁眼": "后庭", "肛门": "后庭",
    "群交": "合卺", "乳交": "玉兔", "足交": "莲步", "车震": "车行",
    "野战": "郊合", "精液": "元阳", "精子": "元阳", "阴道": "幽处",
    "阴户": "幽处", "阴茎": "玉茎", "阳具": "玉茎", "SM": "调教",
    "制服": "官衣", "OL": "衙内", "空姐": "行云", "继母": "继室",
    "姐妹": "同根", "同学": "同窗", "邻居": "东邻", "处女": "处子",
    "初夜": "破瓜", "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥",
    "赌博": "孤注", "毒品": "药石", "枪支": "火器", "刀具": "利刃",
}

# 铁律13：未成年相关关键词
# 注意："学生"/"书生"已移除——高中生/大学生可能已成年，不视为未成年；
# 仅保留明确指向未成年的词（萝莉/幼女/少女/童/teen/loli/schoolgirl等）
_MINOR_KEYWORDS = (
    "豆蔻", "玉蕊", "碧玉", "稚子", "未成年", "teen", "loli",
    "schoolgirl", "萝莉", "幼女", "少女", "童",
)

# 铁律15：默认反代配置
_PROXY_CONFIG_PATHS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "proxy_config.json"),
    os.path.expanduser("~/.super_doubao/super-doubao-runtime/workspace/.user_skills/tvbox-dev/assets/proxy_config.json"),
)
_DEFAULT_PROXY_FALLBACK = "https://xsz-shared-proxy.97471201.workers.dev"


def _load_default_proxy():
    for path in _PROXY_CONFIG_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                proxy = data.get("default_proxy", "").strip()
                if proxy:
                    return proxy
        except Exception:
            continue
    return _DEFAULT_PROXY_FALLBACK


def desensitize(text):
    """铁律11：敏感词古典映射脱敏 + 铁律13：未成年返回空字符串"""
    if text is None:
        return ""
    result = str(text)
    for key in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, CLASSICAL_MAP[key])
    lower = result.lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return ""
    return result


def _is_minor_content(text):
    if not text:
        return False
    lower = str(text).lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def _sanitize_vod(vod):
    if not isinstance(vod, dict):
        return vod
    name = vod.get("vod_name", "")
    remarks = vod.get("vod_remarks", "")
    content = vod.get("vod_content", "")
    if _is_minor_content(name) or _is_minor_content(remarks) or _is_minor_content(content):
        return None
    vod["vod_name"] = desensitize(name)
    if vod.get("vod_remarks") is not None:
        vod["vod_remarks"] = desensitize(remarks)
    if vod.get("vod_content") is not None:
        vod["vod_content"] = desensitize(content)
    if not vod["vod_name"]:
        return None
    return vod


def _sanitize_list(vod_list):
    if not isinstance(vod_list, list):
        return vod_list
    result = []
    for item in vod_list:
        cleaned = _sanitize_vod(item)
        if cleaned is not None:
            result.append(cleaned)
    return result


def _sanitize_classes(classes):
    if not isinstance(classes, list):
        return classes
    result = []
    for cat in classes:
        if not isinstance(cat, dict):
            result.append(cat)
            continue
        name = cat.get("type_name", "")
        if _is_minor_content(name):
            continue
        cat["type_name"] = desensitize(name)
        if cat["type_name"]:
            result.append(cat)
    return result


def _aes_en(s):
    raw = s.encode('utf-8')
    n = 16 - len(raw) % 16
    raw += bytes([n]) * n
    c = AES.new(K2, AES.MODE_CBC, iv=K2[:16])
    return base64.b64encode(c.encrypt(raw)).decode()


def _aes_de(ct):
    if not ct:
        return ''
    c = AES.new(K2, AES.MODE_CBC, iv=K2[:16])
    raw = c.decrypt(base64.b64decode(ct))
    n = raw[-1]
    if 0 < n < len(raw) and raw[-n:] == bytes([n]) * n:
        raw = raw[:-n]
    return raw.decode('utf-8', errors='ignore')


def _b64e(s):
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode().rstrip('=')


def _b64d(s):
    pad = '=' * (-len(s) % 4)
    for fn in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return fn((s + pad).encode()).decode('utf-8', errors='ignore')
        except Exception:
            continue
    return ''


def _mime(head):
    if head[:2] == b'\xff\xd8':
        return 'image/jpeg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    return 'image/jpeg'


class _PicHandler(BaseHTTPRequestHandler):
    spider = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = self.path.split('url=', 1)[-1]
        data = self.spider._pic_shards(unquote(q))
        if not data:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', _mime(data))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)


class Spider:
    """铁律8：独立 class Spider，不继承 base.spider，13个标准接口齐全"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA})
        self._cache = {}
        # 铁律15：反代相关属性初始化
        self.rawSite = HOST
        self.siteUrl = HOST
        self.HOST = HOST
        self.jsonApi = JSON_API
        self.searchApi = SEARCH_API
        self.picApi = PIC_API
        self.videoDomains = list(VIDEO_DOMAINS)
        self._use_proxy = True
        self._default_proxy = _load_default_proxy()

    def getName(self):
        return '聚合站模板'

    def init(self, extend=''):
        # 解析配置（兼容dict和JSON字符串）
        config = {}
        if isinstance(extend, dict):
            config = extend
        elif extend:
            try:
                config = json.loads(extend)
            except Exception:
                try:
                    import ast
                    config = ast.literal_eval(extend)
                except Exception:
                    config = {}
        # 铁律15：原始站点
        self.rawSite = config.get('host') or config.get('rawSite') or HOST
        if not self.rawSite.startswith('http'):
            self.rawSite = 'https://' + self.rawSite
        self.rawSite = self.rawSite.rstrip('/')
        # 铁律15：反代配置
        direct = str(config.get('direct', '')).lower() in ('1', 'true', 'yes', 'on')
        ext_proxy = str(config.get('proxy') or config.get('siteUrl') or '').strip()
        if direct:
            self._use_proxy = False
            self.siteUrl = self.rawSite
        elif ext_proxy:
            self._use_proxy = True
            self.siteUrl = ext_proxy.rstrip('/')
        else:
            self._use_proxy = True
            self.siteUrl = self._default_proxy
        self.HOST = self.siteUrl
        # API地址：反代模式下通过反代访问，直连模式下用原始地址
        base = self.siteUrl if self._use_proxy else self.rawSite
        self.jsonApi = config.get('jsonApi') or JSON_API
        self.searchApi = config.get('searchApi') or SEARCH_API
        self.picApi = config.get('picApi') or PIC_API
        # 如果API是相对路径或包含原始HOST，替换为实际请求地址
        if JSON_API.startswith('https://REPLACE'):
            self.jsonApi = JSON_API
        if SEARCH_API.startswith('https://REPLACE'):
            self.searchApi = SEARCH_API
        if PIC_API.startswith('https://REPLACE'):
            self.picApi = PIC_API
        self.videoDomains = list(config.get('videoDomains') or VIDEO_DOMAINS)

    def _start_pic_proxy(self):
        global _proxy_port
        with _proxy_lock:
            if _proxy_port:
                return _proxy_port
            _PicHandler.spider = self
            httpd = ThreadingHTTPServer(('127.0.0.1', 0), _PicHandler)
            _proxy_port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            return _proxy_port

    def _pic_url(self, path):
        if not path:
            return ''
        return 'http://127.0.0.1:{}/pic?url={}'.format(self._start_pic_proxy(), quote(path, safe=''))

    def _pic_shards(self, path):
        base = re.sub(r'\.\w+$', '', path)
        # 铁律15：防盗链Referer用原始站点
        hd = {'User-Agent': UA, 'Referer': self.rawSite + '/'}
        parts = []
        for i in (1, 2, 3):
            try:
                r = self.session.get(self.picApi + '{}_{}3.txt'.format(base, i),
                                     headers=hd, timeout=10, verify=False)
                if r.status_code == 200 and len(r.content) > 10:
                    parts.append(r.content[2:].decode('utf-8', errors='ignore'))
            except Exception:
                continue
        if len(parts) != 3:
            return b''
        try:
            return base64.b64decode(''.join(parts))
        except Exception:
            return b''

    def _get_raw(self, url, **kw):
        try:
            r = self.session.get(url, timeout=15, verify=False, **kw)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except Exception:
            return ''

    def _parse_body(self, txt, plain=False):
        if not txt:
            return []
        try:
            d = json.loads(txt)
        except Exception:
            return []
        if plain:
            return d if isinstance(d, list) else (d.get('data') or d.get('list') or [])
        if isinstance(d, dict) and d.get('json_data'):
            try:
                inner = json.loads(_aes_de(d['json_data']))
                return inner if isinstance(inner, list) else (inner.get('data') or inner.get('list') or [])
            except Exception:
                return []
        return d if isinstance(d, list) else (d.get('data') or d.get('list') or [])

    def _list(self, url, plain=False):
        now = time.time()
        hit = self._cache.get(url)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        arr = self._parse_body(self._get_raw(url), plain)
        self._cache[url] = (now, arr)
        return arr

    def _fetch_cat(self, tid, page):
        typ, site, cid = tid[:1], tid[1], tid[3:]
        if typ == 't':
            url = '{}/oss/pages/1/{}/new/{}/topic.json'.format(self.jsonApi, site, cid)
            out = []
            for grp in self._list(url):
                if isinstance(grp, dict):
                    out.extend(grp.get('videoList') or [])
            return out
        url = '{}/oss/pages/1/{}/water/{}/{}.json'.format(self.jsonApi, site, cid, page)
        return self._list(url, plain=(typ == 'p'))

    def _real_video_url(self, it):
        vu = it.get('videoUrl') or it.get('video_url') or ''
        if vu:
            return vu
        pu = it.get('previewUrl') or it.get('preview_url') or ''
        if '/preview/preview.mp4' in pu:
            return pu.replace('/preview/preview.mp4', '/index.m3u8')
        if '/preview.mp4' in pu:
            return pu.replace('/preview.mp4', '/index.m3u8')
        return pu

    def _item(self, it):
        title = it.get('title') or it.get('videoName') or it.get('name') or ''
        pic = it.get('cover') or it.get('pic') or it.get('img') or it.get('previewUrl') or ''
        dur = str(it.get('duration') or it.get('videoDuration') or '')
        vu = self._real_video_url(it)
        vid = _b64e('{}|{}|{}|{}'.format(vu, title, pic, dur))
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._pic_url(pic),
            'vod_remarks': dur,
        }

    def _items(self, arr):
        out = []
        for it in arr or []:
            if not isinstance(it, dict):
                continue
            v = self._item(it)
            if v['vod_name']:
                out.append(v)
        return out

    def homeContent(self, filter):
        classes = []
        txt = self._get_raw('{}/oss/pages/1/home.json'.format(self.jsonApi))
        try:
            d = json.loads(txt)
            raw = json.loads(_aes_de(d['json_data'])) if isinstance(d, dict) and d.get('json_data') else d
            for c in raw.get('classList', raw.get('class', [])) if isinstance(raw, dict) else []:
                classes.append({'type_id': str(c.get('id') or c.get('type_id')),
                                'type_name': c.get('name') or c.get('type_name')})
        except Exception:
            pass
        # 铁律11+13：分类脱敏
        classes = _sanitize_classes(classes)
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        p = int(pg) if pg else 1
        ipage, off = (p - 1) // BUNDLE_PAGES, (p - 1) % BUNDLE_PAGES
        arr = self._fetch_cat(str(tid), ipage)
        total = ipage * BUNDLE_SIZE + len(arr)
        if len(arr) == BUNDLE_SIZE:
            pagecount = ipage * BUNDLE_PAGES + BUNDLE_PAGES
        else:
            pagecount = ipage * BUNDLE_PAGES + max(1, (len(arr) + PAGE_SIZE - 1) // PAGE_SIZE)
        seg = arr[off * PAGE_SIZE:(off + 1) * PAGE_SIZE]
        # 铁律11+13：列表脱敏
        return {'page': p, 'pagecount': pagecount, 'limit': PAGE_SIZE,
                'total': total, 'list': _sanitize_list(self._items(seg))}

    def detailContent(self, ids):
        # 铁律8：ids是list/tuple必须遍历
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        result_list = []
        for source_id in id_list:
            raw = _b64d(source_id)
            parts = raw.split('|')
            if len(parts) < 2:
                continue
            vu, title = parts[0], parts[1]
            pic = parts[2] if len(parts) > 2 else ''
            dur = parts[3] if len(parts) > 3 else ''
            urls = [d + vu for d in self.videoDomains] if vu.startswith('/') else [vu]
            vod = {
                'vod_id': source_id,
                'vod_name': title,
                'vod_pic': self._pic_url(pic),
                'vod_remarks': dur,
                'vod_content': title,
                'vod_play_from': '$$$'.join(['线路{}'.format(i + 1) for i in range(len(urls))]),
                'vod_play_url': '#'.join(['正片${}'.format(u) for u in urls]),
            }
            # 铁律11+13：详情脱敏
            cleaned = _sanitize_vod(vod)
            if cleaned is not None:
                result_list.append(cleaned)
        return {'list': result_list}

    def searchContent(self, key, quick=False, pg=1):
        body = {
            'text': _aes_en(key),
            'current': int(pg) or 1,
            'size': PAGE_SIZE,
            'sortType': 0,
            'date': '',
            'quality': '',
            'duration': '',
        }
        try:
            r = self.session.post(self.searchApi + '/search', json=body, timeout=15, verify=False)
            t = r.json()
            arr = json.loads(_aes_de(t.get('json_data'))) if t.get('json_data') else []
            total = int(t.get('total') or 0)
        except Exception:
            arr, total = [], 0
        # 铁律11+13：搜索结果脱敏
        return {'list': _sanitize_list(self._items(arr)), 'page': int(pg) or 1,
                'pagecount': max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)}

    def playerContent(self, flag, id, vipFlags=None):
        # 铁律·广告拦截：m3u8地址走本地代理清洗
        proxy_url = self._proxy_m3u8_url(id, self.rawSite + '/')
        # 铁律15：防盗链双Header，Referer/Origin用原始站点rawSite
        return {'parse': 0, 'url': proxy_url,
                'header': {'User-Agent': UA, 'Referer': self.rawSite + '/', 'Origin': self.rawSite}}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|$)', url or '', re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ""

    def action(self, action):
        return ""

    def destroy(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        return ""

    # ==================== m3u8广告清洗 + 本地代理（铁律·广告拦截） ====================

    def _sanitize_m3u8_url(self, url):
        """清洗m3u8 URL中的广告参数（cover/poster/thumb/pic等）"""
        if not url:
            return url
        url = unquote(url)
        url = re.sub(r'&[Cc]over=.*', '', url)
        url = re.sub(r'&[Pp]oster=.*', '', url)
        url = re.sub(r'&[Tt]humb=.*', '', url)
        url = re.sub(r'&[Pp]ic=.*', '', url)
        url = url.rstrip('&?')
        return url

    def _proxy_m3u8_url(self, url, referer=''):
        """生成m3u8代理地址：优先用壳的getProxyUrl()，否则返回原地址"""
        try:
            if hasattr(self, 'getProxyUrl'):
                return self.getProxyUrl() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.rawSite, safe='')
        except Exception:
            pass
        return url

    def _get_m3u8_content(self, url, referer):
        """带防盗链header下载m3u8文件"""
        try:
            headers = {
                'User-Agent': UA,
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': self.rawSite,
                'Connection': 'keep-alive',
            }
            resp = self.session.get(url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception:
            return None

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        """广告片段识别：关键词匹配 + 短时长判定"""
        u = (uri or '').strip().lower()
        if not u:
            return False
        ad_words = [
            # 英文明确广告词
            'advertisement', 'advertise', 'advert', 'commercial', 'sponsor', 'sponsorship',
            'preroll', 'pre-roll', 'pre_roll', 'midroll', 'mid-roll', 'postroll', 'post-roll',
            'banner', 'banners', 'popup', 'pop-up', 'interstitial', 'overlay', 'splash',
            'bumper', 'stinger', 'vast', 'vpaid', 'vmap',
            'doubleclick', 'googleads', 'googlesyndication', 'googletag', 'adsense', 'admob',
            'adx', 'adnetwork', 'adserving', 'ad-serving', 'adserver', 'ad-server',
            'inmobi', 'unityads', 'applovin', 'ironsource', 'vungle', 'chartboost', 'tapjoy',
            'mintegral', 'pangle', 'bytedance', 'tiktokads', 'kuaishou', 'ks-ad',
            'tracking', 'tracker', 'beacon', 'pixel', 'analytics', 'statistic',
            'leaderboard', 'skyscraper', 'rectangle', 'filler',
            # 中文广告词
            '广告', '片头', '片尾', '贴片', '赞助商', '赞助', '推广', '硬广',
            '前贴', '中插', '后贴', '角标', '广告位', '广告片', '广告段', '广告视频',
            '广告素材', '弹窗', '悬浮', '开屏', '插屏', '激励视频', '激励广告',
            # 拼音/缩写
            'guanggao', 'ggao', 'ggvideo', 'ggmedia',
            # 路径特征（精确匹配）
            '/ad/', '/ads/', '/adv/', '/adver/', '/gg/', '/gga/', '/ggb/', '/ggc/', '/ggd/',
            '_ad.', '.ad/', '_ads.', '_adv.', '_gg.', 'gg_', '_gg', '/gg', 'gg.',
            '/ad_', '/ads_', '/adv_', '/sponsor/', '/banner/', '/promo/', '/commercial/',
            '/preroll/', '/midroll/', '/postroll/', '/popup/', '/interstitial/', '/overlay/',
            '/splash/', '/bumper/', '/vast/', '/vpaid/', '/adnetwork/', '/adserving/',
            '/doubleclick/', '/googleads/', '/googlesyndication/', '/adsense/', '/admob/',
            '/tracking/', '/tracker/', '/beacon/', '/pixel/', '/analytics/',
        ]
        if any(w in u for w in ad_words):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except Exception:
            pass
        return False

    def _parse_m3u8_segments(self, text):
        """m3u8解析器：拆出header/segments/tail"""
        from urllib.parse import urlsplit
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    media_sequence = int(line.split(':', 1)[1])
                except Exception:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try:
                    target_duration = float(line.split(':', 1)[1])
                except Exception:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try:
                        dur = float(m.group(1))
                    except Exception:
                        pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j])
                        j += 1
                        continue
                    uri = lines[j]
                    break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur})
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _segment_host_key(self, uri, base_url):
        """提取片段的主机+路径前缀，用于统计主CDN"""
        from urllib.parse import urlsplit
        try:
            full = urljoin(base_url, uri)
            p = urlsplit(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except Exception:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        """从m3u8 URL提取主路径标记"""
        from urllib.parse import urlsplit
        try:
            p = urlsplit(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ''

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        """核心m3u8广告清洗：五重广告识别 + 主CDN统计 + 前置贴片切除 + 多码率递归代理"""
        from urllib.parse import urlsplit
        text = (m3u8_text or '').replace('\r', '')
        # 多码率m3u8：递归代理子m3u8
        if '#EXT-X-STREAM-INF' in text:
            out = []
            last_stream = False
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                    last_stream = line.startswith('#EXT-X-STREAM-INF')
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if last_stream or '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer or self.rawSite))
                    else:
                        out.append(abs_url)
                    last_stream = False
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return text

        marker = self._main_path_marker(m3u8_url)

        # 统计各主机路径的总时长，找出主CDN
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        # 五重广告识别
        cleaned = []
        removed = 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            if marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        # 兜底策略：前置贴片切除
        if removed == 0 and len(segments) > 4:
            acc = 0.0
            cut = 0
            for idx, seg in enumerate(segments[:12]):
                key = self._segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self._segment_host_key(segments[0]['uri'], m3u8_url)
                if first_key != main_key:
                    cleaned = segments[cut:]
                    removed = cut

        if not cleaned:
            cleaned = segments
            removed = 0

        # 重新生成干净的m3u8
        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'):
                has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append('#EXT-X-MEDIA-SEQUENCE:%d' % (media_sequence + first_idx))

        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        return '\n'.join(new_lines) + '\n'

    def localProxy(self, param):
        """本地代理：m3u8广告清洗 + 图片分片代理（原有功能保留）"""
        if not isinstance(param, dict):
            param = {}
        do = param.get('type') or param.get('action') or param.get('do')
        url = param.get('url', '') or param.get('path', '')
        # m3u8广告清洗分支
        if do == 'm3u8' or (isinstance(url, str) and url.endswith('.m3u8')):
            try:
                referer = param.get('referer', '') or self.rawSite
                if isinstance(url, list):
                    url = url[0]
                if isinstance(referer, list):
                    referer = referer[0]
                url = unquote(url)
                referer = unquote(referer)
                text = self._get_m3u8_content(url, referer)
                if not text:
                    return [502, "text/plain", "m3u8 download failed"]
                # 优先使用独立m3u8_cleaner模块（最新六重+CUE广告检测），失败回退内嵌版
                try:
                    from m3u8_cleaner import M3U8Cleaner
                    _cleaner = M3U8Cleaner(raw_site=referer or self.rawSite)
                    cleaned = _cleaner.clean(text, url, referer)
                except Exception:
                    cleaned = self._clean_m3u8(text, url, referer)
                return [200, "application/vnd.apple.mpegurl", cleaned]
            except Exception as e:
                import traceback
                return [500, "text/plain", "proxy error: %s\n%s" % (e, traceback.format_exc())]
        # 图片分片代理（原有功能）
        data = self._pic_shards(url)
        if data:
            return [200, _mime(data), data]
        return [404, 'text/plain', b'']
