package com.github.catvod.spider;

import android.content.Context;
import com.github.catvod.crawler.Spider;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.HashMap;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 深液传媒 - Java版Spider（JAR包）
 * 站点: https://edi.sycm8.lat/sycm/
 * 结构: 苹果CMS变种，li.multi cate2列表，详情页/{id}.html，const rawUrl直出m3u8
 *
 * 编译方式: 需配合TVBox Android项目，引入catvod SDK后打包成JAR
 * api配置: csp_ShenYeMedia，类名 com.github.catvod.spider.ShenYeMedia
 */
public class ShenYeMedia extends Spider {

    private static final String DOMAIN = "https://edi.sycm8.lat";
    private static final String SITE_NAME = "深液传媒";
    private static final String UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

    // 未成年关键词过滤
    private static final String[] JUVENILE_KEYWORDS = {
        "萝莉", "幼女", "童", "未成年", "teen", "loli", "schoolgirl",
        "孩童", "稚子", "玉蕊", "豆蔻", "小学生", "初中生"
    };

    private String ext;

    @Override
    public void init(Context context, String extend) {
        this.ext = extend;
        // 预热：提前完成TLS握手
        fetch(DOMAIN + "/");
    }

    @Override
    public String homeContent(boolean filter) throws Exception {
        JSONArray classes = new JSONArray();
        // 16个分类硬编码
        String[][] categories = {
            {"20", "日韩"}, {"21", "偷拍"}, {"22", "无码"}, {"23", "自拍"},
            {"24", "巨乳"}, {"25", "华人"}, {"26", "嫩模"}, {"27", "剧情"},
            {"28", "动漫"}, {"29", "熟女"}, {"30", "丝袜"}, {"31", "三级"},
            {"32", "欧美"}, {"33", "有码"}, {"34", "制服"}, {"35", "口交"}
        };
        for (String[] cat : categories) {
            classes.put(new JSONObject()
                .put("type_id", cat[0])
                .put("type_name", cat[1]));
        }
        return new JSONObject()
            .put("class", classes)
            .put("filters", new JSONObject())
            .toString();
    }

    @Override
    public String categoryContent(String tid, String pg, boolean filter,
            HashMap<String, String> extend) throws Exception {
        int page = Integer.parseInt(pg);
        String url = DOMAIN + "/vodtype/" + tid + ".html";
        if (page > 1) {
            url = DOMAIN + "/vodtype/" + tid + "-" + page + ".html";
        }

        String html = fetch(url);
        JSONArray list = parseList(html);

        return new JSONObject()
            .put("page", page)
            .put("pagecount", 1)
            .put("limit", 60)
            .put("total", list.length())
            .put("list", list)
            .toString();
    }

    @Override
    public String detailContent(List<String> ids) throws Exception {
        String vodId = ids.get(0);
        String detailUrl = DOMAIN + "/" + vodId + ".html";
        String html = fetch(detailUrl);

        // 提取m3u8
        String m3u8Url = "";
        Matcher rawMatcher = Pattern.compile(
            "(?:const|let|var)\\s+rawUrl\\s*=\\s*['\"]([^'\"]+)['\"]",
            Pattern.CASE_INSENSITIVE).matcher(html);
        if (rawMatcher.find()) {
            m3u8Url = rawMatcher.group(1);
        }

        if (m3u8Url.isEmpty()) {
            Matcher m3u8Matcher = Pattern.compile(
                "https?://[^\\s\"'\\\\]+\\.m3u8[^\\s\"'\\\\]*").matcher(html);
            while (m3u8Matcher.find()) {
                String m = m3u8Matcher.group();
                if (!m.contains("sharer") && !m.contains("balecao")) {
                    m3u8Url = m;
                    break;
                }
            }
        }

        // 提取标题
        String vodName = "视频" + vodId;
        Matcher titleMatcher = Pattern.compile("<title>(.*?)</title>", Pattern.DOTALL).matcher(html);
        if (titleMatcher.find()) {
            vodName = titleMatcher.group(1).replaceAll("[-_–—]\\s*" + SITE_NAME + ".*$", "").trim();
        }

        // 提取封面
        String vodPic = "";
        Matcher picMatcher = Pattern.compile(
            "(?:data-original|data-src|src)=\"([^\"]+\\.(?:jpg|jpeg|png))\"").matcher(html);
        if (picMatcher.find()) {
            vodPic = picMatcher.group(1);
        }

        JSONObject detail = new JSONObject()
            .put("vod_id", vodId)
            .put("vod_name", vodName)
            .put("vod_pic", vodPic)
            .put("vod_remarks", SITE_NAME)
            .put("vod_play_from", SITE_NAME)
            .put("vod_play_url", "第1集$" + m3u8Url);

        return new JSONObject()
            .put("list", new JSONArray().put(detail))
            .toString();
    }

    @Override
    public String searchContent(String key, boolean quick, int pg) throws Exception {
        // 暂不支持搜索
        return new JSONObject()
            .put("page", pg)
            .put("pagecount", 0)
            .put("limit", 60)
            .put("total", 0)
            .put("list", new JSONArray())
            .toString();
    }

    @Override
    public String playerContent(String flag, String id, List<String> vipFlags) throws Exception {
        return new JSONObject()
            .put("parse", 0)
            .put("jx", 0)
            .put("url", id)
            .put("header", new JSONObject().put("User-Agent", UA))
            .toString();
    }

    // ==================== 私有辅助方法 ====================

    /**
     * 解析列表页（li.multi cate2结构）
     */
    private JSONArray parseList(String html) throws Exception {
        JSONArray list = new JSONArray();

        // 匹配 <li class="multi cate2 ...">...</li>
        Matcher itemMatcher = Pattern.compile(
            "<li[^>]*class=\"multi[^\"]*cate2[^\"]*\"[^>]*>(.*?)</li>",
            Pattern.DOTALL).matcher(html);

        while (itemMatcher.find()) {
            String item = itemMatcher.group(1);

            // 提取vod_id
            Matcher idMatcher = Pattern.compile("href=\"/(\\d+)\\.html\"").matcher(item);
            if (!idMatcher.find()) continue;
            String vodId = idMatcher.group(1);

            // 提取标题（catename里的title属性）
            String vodName = "";
            Matcher titleMatcher = Pattern.compile(
                "class=\"catename\"[^>]*>.*?title=\"([^\"]+)\"",
                Pattern.DOTALL).matcher(item);
            if (titleMatcher.find()) {
                vodName = titleMatcher.group(1);
            }
            if (vodName.isEmpty()) {
                Matcher dtMatcher = Pattern.compile("data-title=\"([^\"]+)\"").matcher(item);
                if (dtMatcher.find()) {
                    vodName = dtMatcher.group(1);
                }
            }
            if (vodName.isEmpty() || isJuvenile(vodName)) continue;

            // 提取封面（mip-img的src）
            String vodPic = "";
            Matcher picMatcher = Pattern.compile(
                "<mip-img[^>]*src=\"([^\"]+\\.(?:jpg|jpeg|png))\"",
                Pattern.CASE_INSENSITIVE).matcher(item);
            if (picMatcher.find()) {
                vodPic = picMatcher.group(1);
            }

            JSONObject video = new JSONObject()
                .put("vod_id", vodId)
                .put("vod_name", vodName)
                .put("vod_pic", vodPic)
                .put("vod_remarks", "");
            list.put(video);
        }

        return list;
    }

    /**
     * 未成年关键词检查
     */
    private boolean isJuvenile(String text) {
        if (text == null || text.isEmpty()) return false;
        String lower = text.toLowerCase();
        for (String kw : JUVENILE_KEYWORDS) {
            if (lower.contains(kw.toLowerCase())) return true;
        }
        return false;
    }

    /**
     * HTTP请求（标准库HttpURLConnection）
     */
    private String fetch(String url) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", UA);
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
            conn.setRequestProperty("Accept-Language", "zh-CN,zh;q=0.9");
            conn.setRequestProperty("Referer", DOMAIN + "/");
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(20000);

            int code = conn.getResponseCode();
            if (code != 200) return "";

            BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
            reader.close();
            return sb.toString();
        } catch (Exception e) {
            return "";
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
