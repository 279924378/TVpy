# coding=utf-8
"""
m3u8广告清洗 + 本地代理模块（提取自千媚宫，五重广告识别大阵）
独立可复用，可直接导入使用，也可嵌入TVBox Python Spider的localProxy

用法：
    from m3u8_cleaner import M3U8Cleaner
    cleaner = M3U8Cleaner(raw_site='https://example.com', session=requests.Session())
    cleaned = cleaner.clean(m3u8_text, m3u8_url, referer)
"""

import re
from urllib.parse import quote, unquote, urljoin, urlsplit


class M3U8Cleaner:
    """m3u8广告清洗器：五重广告识别 + 主CDN统计 + 前置贴片切除 + 多码率递归代理"""

    def __init__(self, raw_site='', session=None, user_agent=''):
        self.raw_site = raw_site
        self.session = session
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

    # ==================== URL参数清洗 ====================

    def sanitize_url(self, url):
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

    # ==================== 代理URL生成 ====================

    def proxy_url(self, url, referer='', get_proxy_url_fn=None):
        """生成m3u8代理地址：优先用壳的getProxyUrl()，否则返回原地址"""
        try:
            if get_proxy_url_fn:
                return get_proxy_url_fn() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.raw_site, safe='')
        except Exception:
            pass
        return url

    # ==================== m3u8下载 ====================

    def download(self, url, referer=''):
        """带防盗链header下载m3u8文件"""
        if not self.session:
            import requests
            self.session = requests.Session()
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer or self.raw_site,
                'Origin': self.raw_site,
                'Connection': 'keep-alive',
            }
            resp = self.session.get(url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception:
            return None

    # ==================== 广告片段识别 ====================

    def is_ad_segment(self, uri, dur=0, prev_tags=None):
        """广告片段识别：关键词匹配 + 短时长判定（清洗时用，比预检严格避免误删）"""
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
            # LunaTV/社区补充词
            'redtraffic', 'adjump', 'ad-jump',
            'adserver', 'ad-serving', 'adserving', 'adnetwork', 'ad-network',
            'vast', 'vpaid', 'vmap', 'scte35', 'scte-35', 'oatcls',
            # TwitchAdSolutions广告URL模式
            'adsquared', 'ad-signifier', 'twitch-ad', 'stitched-ad',
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

    # ==================== m3u8解析 ====================

    def parse_segments(self, text):
        """m3u8解析器：拆出header/segments/tail，提取每片段的tags/uri/duration；
        同时跟踪SCTE-35/CUE广告区块（CUE-OUT到CUE-IN之间的片段标记in_cue_ad=True）"""
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        in_cue_ad = False  # SCTE-35/CUE广告区块状态
        after_discontinuity = False  # 紧跟在DISCONTINUITY之后
        discontinuity_zone = 0  # 当前处于第几个DISCONTINUITY区间（0=主视频，>0=可能广告区）
        i = 0
        while i < len(lines):
            line = lines[i]
            # SCTE-35/CUE/AdSignifier广告标记检测（行业标准+Twitch等平台自定义标记）
            if line.startswith('#EXT-X-CUE-OUT') or line.startswith('#EXT-X-SCTE35') or \
               line.startswith('#EXT-OATCLS-SCTE35') or line.startswith('#EXT-X-SCTE35-OUT') or \
               'X-TV-TWITCH-AD' in line:
                in_cue_ad = True
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
                i += 1
                continue
            # DATERANGE标记：需区分广告开始(OUT/stitched-ad)和结束(IN/end)
            if line.startswith('#EXT-X-DATERANGE'):
                upper_line = line.upper()
                lower_line = line.lower()
                is_ad_start = ('SCTE35-OUT' in upper_line or 'CUE-OUT' in upper_line or
                               ('stitched-ad' in lower_line and '-end' not in lower_line and 'end=' not in lower_line))
                is_ad_end = ('SCTE35-IN' in upper_line or 'CUE-IN' in upper_line or
                              'stitched-ad-end' in lower_line or '-end' in lower_line)
                if is_ad_start:
                    in_cue_ad = True
                elif is_ad_end:
                    in_cue_ad = False
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
                i += 1
                continue
            if line.startswith('#EXT-X-CUE-IN') or line.startswith('#EXT-X-SCTE35-IN'):
                in_cue_ad = False
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
                i += 1
                continue
            # DISCONTINUITY标记（广告前后常出现，不单独标记但保留在tags中）
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
                    seg = {'tags': tags, 'uri': uri, 'dur': dur, 'in_cue_ad': in_cue_ad,
                           'after_discontinuity': after_discontinuity, 'discontinuity_zone': discontinuity_zone}
                    segments.append(seg)
                    after_discontinuity = False
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#EXT-X-DISCONTINUITY'):
                # DISCONTINUITY标记：广告前后常出现，切换区间
                after_discontinuity = True
                discontinuity_zone += 1
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            elif line.startswith('#'):
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur, 'in_cue_ad': in_cue_ad,
                                 'after_discontinuity': after_discontinuity, 'discontinuity_zone': discontinuity_zone})
                after_discontinuity = False
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    # ==================== 主CDN统计辅助 ====================

    def segment_host_key(self, uri, base_url):
        """提取片段的主机+路径前缀，用于统计主CDN"""
        try:
            full = urljoin(base_url, uri)
            p = urlsplit(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except Exception:
            return ('', '')

    def main_path_marker(self, m3u8_url):
        """从m3u8 URL提取主路径标记（如/20240101/xxx/1000kb/hls/）"""
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

    # ==================== 核心清洗 ====================

    def clean(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25, get_proxy_url_fn=None):
        """核心m3u8广告清洗：五重广告识别 + 主CDN统计 + 前置贴片切除 + 多码率递归代理"""
        text = (m3u8_text or '').replace('\r', '')
        # 多码率m3u8（#EXT-X-STREAM-INF）：递归代理子m3u8
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
                        out.append(self.proxy_url(abs_url, referer or self.raw_site, get_proxy_url_fn))
                    else:
                        out.append(abs_url)
                    last_stream = False
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self.parse_segments(text)
        if not segments:
            return text

        marker = self.main_path_marker(m3u8_url)

        # 统计各主机路径的总时长，找出主CDN
        stat = {}
        for seg in segments:
            key = self.segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        # 六重广告识别 + SCTE-35/CUE广告区块（第零重，最高优先级）
        cleaned = []
        removed = 0
        cue_removed = 0
        for idx, seg in enumerate(segments):
            # 第零重：SCTE-35/CUE广告区块（CUE-OUT到CUE-IN之间的片段，行业标准广告标记，直接剔除）
            if seg.get('in_cue_ad'):
                removed += 1
                cue_removed += 1
                continue
            key = self.segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self.is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            # 第三重：路径标记不匹配主路径
            if marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            # 第四重：前置12片段 + METHOD=NONE + 路径不匹配
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            # 第五重：前置12片段 + 主CDN占比>=60% + 非主CDN且时长<=90秒
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            # 第六重：DISCONTINUITY后短片段（广告前后常出现不连续标记，紧跟的短片段多为广告）
            seg_dur = float(seg.get('dur') or 0)
            if (not is_ad) and seg.get('after_discontinuity') and 0 < seg_dur <= 6:
                if marker and marker not in urlsplit(abs_uri).path.lower():
                    is_ad = True
                elif key != main_key:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        # 兜底策略：没删到广告时，前12片段累计>=25秒且第一个不是主CDN，则切掉前置贴片
        if removed == 0 and len(segments) > 4:
            acc = 0.0
            cut = 0
            for idx, seg in enumerate(segments[:12]):
                key = self.segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self.segment_host_key(segments[0]['uri'], m3u8_url)
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
                # 过滤广告相关标签（CUE/SCTE35/DISCONTINUITY等）
                if tag.startswith('#EXT-X-CUE-OUT') or tag.startswith('#EXT-X-CUE-IN') or \
                   tag.startswith('#EXT-X-SCTE35') or tag.startswith('#EXT-OATCLS-SCTE35') or \
                   tag.startswith('#EXT-X-SCTE35-OUT') or tag.startswith('#EXT-X-SCTE35-IN') or \
                   tag.startswith('#EXT-X-DISCONTINUITY') or \
                   (tag.startswith('#EXT-X-DATERANGE') and ('SCTE35' in tag.upper() or 'stitched-ad' in tag.lower())) or \
                   'X-TV-TWITCH-AD' in tag or 'stitched-ad' in tag.lower():
                    continue
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

    # ==================== localProxy兼容层 ====================

    def local_proxy(self, params):
        """TVBox Spider localProxy兼容入口：接收m3u8请求 → 下载 → 清洗 → 返回"""
        try:
            if not isinstance(params, dict):
                params = {}
            do = params.get('type') or params.get('action') or params.get('do')
            url = params.get('url', '')
            if do not in ['m3u8', 'py'] and not url:
                return [404, "text/plain", "not found"]
            referer = params.get('referer', '') or self.raw_site
            if isinstance(url, list):
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            url = unquote(url)
            referer = unquote(referer)
            text = self.download(url, referer)
            if not text:
                return [502, "text/plain", "m3u8 download failed\nurl: %s\nreferer: %s" % (url, referer)]
            cleaned = self.clean(text, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            import traceback
            return [500, "text/plain", "proxy error: %s\n%s" % (e, traceback.format_exc())]

    # ==================== 广告预检（写py时自动判断是否需要广告处理） ====================

    def detect_ads(self, m3u8_url, referer=''):
        """
        广告预检：下载m3u8→解析ts分片→五重特征扫描→判断是否有广告。
        用于写Python爬虫时自动判断是否需要启用「m3u8广告处理」组合功能。
        
        返回: dict {
            'has_ads': bool,           # 是否检测到广告
            'confidence': str,          # 置信度：高/中/低/无
            'score': int,               # 检测得分（0-100，≥30判定有广告）
            'total_segments': int,      # ts片段总数
            'ad_segments': int,         # 疑似广告片段数
            'domains': list,            # 涉及的CDN域名列表
            'details': list,            # 检测到的广告特征详情
            'm3u8_url': str,            # 检测的m3u8地址
        }
        """
        result = {
            'has_ads': False, 'confidence': '无', 'score': 0,
            'total_segments': 0, 'ad_segments': 0, 'domains': [],
            'details': [], 'm3u8_url': m3u8_url,
        }
        text = self.download(m3u8_url, referer or self.raw_site)
        if not text:
            result['details'].append('m3u8下载失败，无法检测')
            return result

        # 多码率m3u8：递归检测第一个子m3u8
        if '#EXT-X-STREAM-INF' in text:
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '.m3u8' in line.lower():
                    sub_url = urljoin(m3u8_url, line)
                    return self.detect_ads(sub_url, referer or m3u8_url)
            result['details'].append('多码率m3u8但未找到子m3u8地址')
            return result

        header, segments, tail, media_sequence, target_duration = self.parse_segments(text)
        result['total_segments'] = len(segments)
        if not segments:
            result['details'].append('m3u8无ts片段')
            return result

        score = 0
        # 广告关键词库（预检用，比清洗时更宽泛，宁可误判不可漏判）
        ad_keywords = [
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
            'lead', 'leaderboard', 'skyscraper', 'rectangle', 'cube', 'fill', 'filler',
            # 中文广告词
            '广告', '片头', '片尾', '贴片', '赞助商', '赞助', '推广', '宣传', '硬广', '软广',
            '前贴', '中插', '后贴', '角标', '暂停广告', '广告位', '广告片', '广告段', '广告视频',
            '广告素材', '信息流', '弹窗', '悬浮', '开屏', '插屏', '激励视频', '激励广告',
            # 拼音/缩写
            'guanggao', 'ggao', 'ggvideo', 'ggmedia',
            # 路径特征（精确匹配，避免误判普通单词）
            '/ad/', '/ads/', '/adv/', '/adver/', '/gg/', '/gga/', '/ggb/', '/ggc/', '/ggd/',
            '_ad.', '.ad/', '_ads.', '_adv.', '_gg.', 'gg_', '_gg', '/gg', 'gg.',
            '/ad_', '/ads_', '/adv_', '/sponsor/', '/banner/', '/promo/', '/commercial/',
            '/preroll/', '/midroll/', '/postroll/', '/popup/', '/interstitial/', '/overlay/',
            '/splash/', '/bumper/', '/vast/', '/vpaid/', '/adnetwork/', '/adserving/',
            '/doubleclick/', '/googleads/', '/googlesyndication/', '/adsense/', '/admob/',
            '/tracking/', '/tracker/', '/beacon/', '/pixel/', '/analytics/',
        ]

        # 统计域名
        domain_set = set()
        for seg in segments:
            try:
                full = urljoin(m3u8_url, seg.get('uri', ''))
                p = urlsplit(full)
                if p.netloc:
                    domain_set.add(p.netloc.lower())
            except Exception:
                pass
        result['domains'] = sorted(domain_set)

        # 主路径标记
        marker = self.main_path_marker(m3u8_url)

        # 统计各域名时长
        domain_dur = {}
        for seg in segments:
            try:
                full = urljoin(m3u8_url, seg.get('uri', ''))
                p = urlsplit(full)
                dom = p.netloc.lower()
                domain_dur[dom] = domain_dur.get(dom, 0.0) + float(seg.get('dur') or 0)
            except Exception:
                pass
        main_domain = max(domain_dur.items(), key=lambda x: x[1])[0] if domain_dur else ''
        total_dur = sum(domain_dur.values()) or 0

        ad_segment_count = 0
        keyword_hits = 0
        short_duration_hits = 0
        non_main_path_hits = 0
        non_main_domain_hits = 0
        cue_ad_hits = 0  # SCTE-35/CUE广告区块片段数
        discontinuity_hits = 0  # DISCONTINUITY后短片段数

        for idx, seg in enumerate(segments):
            uri = (seg.get('uri', '') or '').lower()
            dur = float(seg.get('dur') or 0)
            is_ad = False

            # 特征0（最高优先级）：SCTE-35/CUE广告区块（行业标准广告标记）
            if seg.get('in_cue_ad'):
                cue_ad_hits += 1
                is_ad = True

            # 特征1：URL含广告关键词
            if any(w in uri for w in ad_keywords):
                keyword_hits += 1
                is_ad = True

            # 特征2：极短时长片段（≤1.5秒，预检比清洗时的1.2秒放宽）
            if 0 < dur <= 1.5:
                short_duration_hits += 1
                is_ad = True

            # 特征3：非主路径片段（路径标记不匹配）
            if marker:
                try:
                    full = urljoin(m3u8_url, seg.get('uri', ''))
                    if marker not in urlsplit(full).path.lower():
                        non_main_path_hits += 1
                        is_ad = True
                except Exception:
                    pass

            # 特征4：非主域名片段（多CDN混杂）
            if main_domain and len(domain_set) >= 2:
                try:
                    full = urljoin(m3u8_url, seg.get('uri', ''))
                    dom = urlsplit(full).netloc.lower()
                    if dom != main_domain and domain_dur.get(dom, 0) <= total_dur * 0.3:
                        non_main_domain_hits += 1
                        is_ad = True
                except Exception:
                    pass

            # 特征5：前置贴片（前5个片段中，非主路径且与后续路径结构不一致）
            if idx < 5 and marker:
                try:
                    full = urljoin(m3u8_url, seg.get('uri', ''))
                    if marker not in urlsplit(full).path.lower():
                        # 检查后续片段是否都是主路径
                        later_main = 0
                        later_total = 0
                        for later in segments[idx+1:idx+6]:
                            later_total += 1
                            try:
                                later_full = urljoin(m3u8_url, later.get('uri', ''))
                                if marker in urlsplit(later_full).path.lower():
                                    later_main += 1
                            except Exception:
                                pass
                        if later_total >= 2 and later_main / later_total >= 0.6:
                            is_ad = True
                except Exception:
                    pass

            # 特征6：DISCONTINUITY后短片段（广告前后常出现不连续标记）
            if seg.get('after_discontinuity') and 0 < dur <= 6:
                if marker:
                    try:
                        full = urljoin(m3u8_url, seg.get('uri', ''))
                        if marker not in urlsplit(full).path.lower():
                            discontinuity_hits += 1
                            is_ad = True
                    except Exception:
                        pass
                elif main_domain and len(domain_set) >= 2:
                    try:
                        full = urljoin(m3u8_url, seg.get('uri', ''))
                        if urlsplit(full).netloc.lower() != main_domain:
                            discontinuity_hits += 1
                            is_ad = True
                    except Exception:
                        pass

            if is_ad:
                ad_segment_count += 1

        result['ad_segments'] = ad_segment_count

        # 评分规则（六重特征 + SCTE-35/CUE广告区块，每重贡献不同分值）
        # CUE广告区块（最高优先级，行业标准广告标记，直接给高分）
        if cue_ad_hits > 0:
            score += min(cue_ad_hits * 15, 50)
            result['details'].append('特征0-SCTE35/CUE广告区块：命中%d个片段（行业标准广告标记）' % cue_ad_hits)
        if keyword_hits > 0:
            score += min(keyword_hits * 10, 30)
            result['details'].append('特征1-广告关键词：命中%d个片段' % keyword_hits)
        if short_duration_hits > 0:
            score += min(short_duration_hits * 8, 25)
            result['details'].append('特征2-极短时长(≤1.5s)：命中%d个片段' % short_duration_hits)
        if non_main_path_hits > 0 and len(segments) >= 5:
            ratio = non_main_path_hits / len(segments)
            if ratio >= 0.15:
                score += 20
                result['details'].append('特征3-非主路径片段：%d/%d (%.0f%%)，超过15%%阈值' % (non_main_path_hits, len(segments), ratio * 100))
            elif ratio >= 0.05:
                score += 10
                result['details'].append('特征3-非主路径片段：%d/%d (%.0f%%)' % (non_main_path_hits, len(segments), ratio * 100))
        if len(domain_set) >= 2 and non_main_domain_hits > 0:
            score += min(non_main_domain_hits * 5, 20)
            result['details'].append('特征4-多CDN混杂：%d个域名，非主域名%d个片段' % (len(domain_set), non_main_domain_hits))
        if ad_segment_count > 0 and len(segments) >= 3:
            ad_ratio = ad_segment_count / len(segments)
            if ad_ratio >= 0.1:
                score += 15
                result['details'].append('特征5-广告片段占比：%d/%d (%.0f%%)' % (ad_segment_count, len(segments), ad_ratio * 100))
        if discontinuity_hits > 0:
            score += min(discontinuity_hits * 8, 20)
            result['details'].append('特征6-DISCONTINUITY后短片段：命中%d个片段' % discontinuity_hits)

        score = min(score, 100)
        result['score'] = score

        # 判定阈值
        if score >= 50:
            result['has_ads'] = True
            result['confidence'] = '高'
        elif score >= 30:
            result['has_ads'] = True
            result['confidence'] = '中'
        elif score >= 15:
            result['has_ads'] = True
            result['confidence'] = '低'
        else:
            result['has_ads'] = False
            result['confidence'] = '无'

        if not result['details']:
            result['details'].append('未检测到明显广告特征')

        return result


# ==================== 模块级便捷函数 ====================

def detect_m3u8_ads(m3u8_url, referer='', raw_site=''):
    """
    模块级便捷函数：广告预检，写py时自动判断是否需要「m3u8广告处理」。
    
    用法:
        from m3u8_cleaner import detect_m3u8_ads
        result = detect_m3u8_ads('https://xxx.com/index.m3u8', 'https://xxx.com/play/1.html')
        if result['has_ads']:
            print('检测到广告(置信度:%s)，需要启用广告处理' % result['confidence'])
        else:
            print('未检测到广告，可省略广告处理')
    
    返回: dict（见 M3U8Cleaner.detect_ads 方法）
    """
    cleaner = M3U8Cleaner(raw_site=raw_site or referer)
    return cleaner.detect_ads(m3u8_url, referer)


# ==================== 命令行独立使用 ====================

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('用法: python3 m3u8_cleaner.py <m3u8_url> [referer]')
        print('      清洗m3u8广告片段并输出干净的m3u8')
        sys.exit(1)
    m3u8_url = sys.argv[1]
    referer = sys.argv[2] if len(sys.argv) > 2 else ''
    cleaner = M3U8Cleaner(raw_site=referer)
    text = cleaner.download(m3u8_url, referer)
    if not text:
        print('下载失败: %s' % m3u8_url, file=sys.stderr)
        sys.exit(1)
    result = cleaner.clean(text, m3u8_url, referer)
    print(result)
