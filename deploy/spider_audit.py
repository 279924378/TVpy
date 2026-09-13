#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
铁律14：Spider落盘前自动检测脚本
检测Python Spider是否符合四壳协议+铁律11脱敏+铁律15反代
用法: python3 spider_audit.py <spider_file.py> [config.json] [miniapp_dir]
退出码: 0=全部通过, 1=有ERROR
"""
import ast
import json
import os
import re
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== 检测规则 ==========
RULES = [
    # (规则ID, 严重级别, 检测函数名, 描述)
    ("PY001", "ERROR", "check_syntax", "Python语法检查（py_compile）"),
    ("PY002", "ERROR", "check_class_spider", "存在独立 class Spider（不继承base.spider）"),
    ("PY003", "ERROR", "check_13_interfaces", "13个标准接口齐全"),
    ("PY004", "ERROR", "check_classical_map", "铁律11：内置 CLASSICAL_MAP 字典"),
    ("PY005", "ERROR", "check_desensitize", "铁律11：内置 desensitize() 函数/方法"),
    ("PY006", "ERROR", "check_desensitize_called", "铁律11：home/category/detail/search 返回前调用脱敏"),
    ("PY007", "ERROR", "check_minor_filter", "铁律13：未成年内容检测/剔除逻辑存在"),
    ("PY008", "ERROR", "check_proxy_rawsite", "铁律15：存在 rawSite 属性（原始站点用于防盗链）"),
    ("PY009", "ERROR", "check_proxy_siteurl", "铁律15：存在 siteUrl/default_proxy 反代逻辑"),
    ("PY010", "ERROR", "check_proxy_config_read", "铁律15：读取 proxy_config.json 的 default_proxy"),
    ("PY011", "ERROR", "check_player_header", "铁律15：playerContent.header 含 Referer + Origin"),
    ("PY012", "ERROR", "check_detail_traverse_ids", "铁律8：detailContent 遍历 ids（list/tuple）"),
    ("PY013", "ERROR", "check_filters_dict", "铁律8：homeContent 返回 filters 为 dict"),
    ("PY014", "WARN", "check_instantiate", "模拟实例化 Spider() 无报错"),
    ("PY015", "WARN", "check_init_call", "模拟调用 init(extend) 无报错"),
    ("PY016", "ERROR", "check_m3u8_cleaner", "m3u8广告处理②③：清洗核心_clean_m3u8 + 广告拦截_is_ad_segment（五重识别）"),
    ("PY017", "ERROR", "check_localProxy_impl", "m3u8广告处理①：本地代理localProxy非空壳（禁止单纯return [404]）"),
    ("PY018", "INFO", "check_ad_precheck", "铁律17咨询：广告预检注释/广告处理实现（仅提示，不影响打包）"),
    ("JSON001", "ERROR", "check_json_valid", "配置JSON格式合法"),
    ("JSON002", "ERROR", "check_json_fields", "配置JSON含 key/name/type/ext 四字段"),
    ("JSON003", "ERROR", "check_json_ext_url", "配置JSON ext含站点URL"),
]


class AuditResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
        self.infos = []

    def error(self, rule_id, msg):
        self.errors.append((rule_id, msg))

    def warn(self, rule_id, msg):
        self.warnings.append((rule_id, msg))

    def ok(self, rule_id, msg):
        self.passed.append((rule_id, msg))

    def info(self, rule_id, msg):
        self.infos.append((rule_id, msg))

    def summary(self):
        print("\n" + "=" * 60)
        print("铁律14检测结果汇总")
        print("=" * 60)
        print("通过: %d 项" % len(self.passed))
        print("警告: %d 项" % len(self.warnings))
        print("错误: %d 项" % len(self.errors))
        print("提示: %d 项" % len(self.infos))
        if self.errors:
            print("\n❌ 错误清单（必须修复才能打包）：")
            for rid, msg in self.errors:
                print("  [%s] %s" % (rid, msg))
        if self.warnings:
            print("\n⚠ 警告清单（建议修复）：")
            for rid, msg in self.warnings:
                print("  [%s] %s" % (rid, msg))
        if self.infos:
            print("\nℹ 提示清单（咨询项，不影响打包）：")
            for rid, msg in self.infos:
                print("  [%s] %s" % (rid, msg))
        print("=" * 60)
        return len(self.errors) == 0


def load_source(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def check_syntax(filepath, source, result):
    """PY001: 语法检查"""
    try:
        compile(source, filepath, "exec")
        result.ok("PY001", "语法检查通过")
    except SyntaxError as e:
        result.error("PY001", "语法错误: %s (行 %d)" % (e.msg, e.lineno))


def check_class_spider(filepath, source, result):
    """PY002: 独立class Spider"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            if node.bases:
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if "base" in base_name.lower() or "spider" in base_name.lower():
                        result.error("PY002", "class Spider 继承了 %s，必须是独立类不继承 base.spider" % base_name)
                        return
            result.ok("PY002", "存在独立 class Spider")
            return
    result.error("PY002", "未找到 class Spider 定义")


def check_13_interfaces(filepath, source, result):
    """PY003: 13个标准接口"""
    required = [
        "getDependence", "init", "homeContent", "homeVideoContent",
        "categoryContent", "detailContent", "searchContent", "playerContent",
        "localProxy", "isVideoFormat", "manualVideoCheck", "action", "destroy",
    ]
    tree = ast.parse(source)
    methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
    missing = [m for m in required if m not in methods]
    if missing:
        result.error("PY003", "缺少接口方法: %s" % ", ".join(missing))
    else:
        result.ok("PY003", "13个标准接口齐全")


def check_classical_map(filepath, source, result):
    """PY004: CLASSICAL_MAP 字典"""
    if re.search(r"CLASSICAL_MAP\s*=", source):
        result.ok("PY004", "存在 CLASSICAL_MAP 字典")
    else:
        result.error("PY004", "铁律11违规：未找到 CLASSICAL_MAP 字典定义")


def check_desensitize(filepath, source, result):
    """PY005: desensitize 函数"""
    if re.search(r"def\s+desensitize\s*\(", source):
        result.ok("PY005", "存在 desensitize() 函数")
    else:
        result.error("PY005", "铁律11违规：未找到 desensitize() 函数定义")


def check_desensitize_called(filepath, source, result):
    """PY006: 脱敏在返回前被调用"""
    # 检查是否有 _sanitize_list / _sanitize_vod / desensitize( 在各接口中调用
    sanitize_calls = len(re.findall(r"_sanitize_list|_sanitize_vod|_sanitize_classes|desensitize\(", source))
    if sanitize_calls >= 3:
        result.ok("PY006", "脱敏函数被调用 %d 次（覆盖各接口）" % sanitize_calls)
    else:
        result.error("PY006", "铁律11违规：脱敏函数调用不足（仅 %d 次），各接口返回前必须调用" % sanitize_calls)


def check_minor_filter(filepath, source, result):
    """PY007: 未成年内容检测"""
    if re.search(r"_is_minor_content|_MINOR_KEYWORDS|未成年", source):
        result.ok("PY007", "存在未成年内容检测/剔除逻辑")
    else:
        result.error("PY007", "铁律13违规：未找到未成年内容检测/剔除逻辑")


def check_proxy_rawsite(filepath, source, result):
    """PY008: rawSite 属性"""
    if re.search(r"rawSite", source):
        result.ok("PY008", "存在 rawSite 属性（原始站点用于防盗链）")
    else:
        result.error("PY008", "铁律15违规：未找到 rawSite 属性（原始站点用于防盗链Referer/Origin）")


def check_proxy_siteurl(filepath, source, result):
    """PY009: siteUrl/default_proxy 反代"""
    if re.search(r"siteUrl|default_proxy|_use_proxy", source):
        result.ok("PY009", "存在 siteUrl/default_proxy 反代逻辑")
    else:
        result.error("PY009", "铁律15违规：未找到 siteUrl/default_proxy 反代逻辑")


def check_proxy_config_read(filepath, source, result):
    """PY010: 读取 proxy_config.json"""
    if re.search(r"proxy_config\.json|_load_default_proxy|_PROXY_CONFIG", source):
        result.ok("PY010", "存在读取 proxy_config.json default_proxy 的逻辑")
    else:
        result.error("PY010", "铁律15违规：未找到读取 proxy_config.json default_proxy 的逻辑")


def check_player_header(filepath, source, result):
    """PY011: playerContent.header 含 Referer + Origin"""
    # 找到 playerContent 方法
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "playerContent":
                    # 提取方法源码
                    method_source = ast.get_source_segment(source, item) or ""
                    has_referer = "Referer" in method_source or "referer" in method_source
                    has_origin = "Origin" in method_source or "origin" in method_source
                    if has_referer and has_origin:
                        result.ok("PY011", "playerContent.header 含 Referer + Origin 防盗链")
                    else:
                        missing = []
                        if not has_referer:
                            missing.append("Referer")
                        if not has_origin:
                            missing.append("Origin")
                        result.error("PY011", "铁律15违规：playerContent.header 缺少 %s" % " + ".join(missing))
                    return
    result.error("PY011", "未找到 playerContent 方法")


def check_detail_traverse_ids(filepath, source, result):
    """PY012: detailContent 遍历 ids"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "detailContent":
                    method_source = ast.get_source_segment(source, item) or ""
                    # 检查是否有 list(ids) / for ... in ids / isinstance(ids, (list, tuple))
                    if re.search(r"list\s*\(\s*ids\s*\)|for\s+\w+\s+in\s+ids|isinstance\s*\(\s*ids\s*,\s*\(?list|tuple", method_source):
                        result.ok("PY012", "detailContent 遍历 ids（list/tuple）")
                    else:
                        result.error("PY012", "铁律8违规：detailContent 未遍历 ids，可能只取第一个导致详情页空白")
                    return
    result.error("PY012", "未找到 detailContent 方法")


def check_filters_dict(filepath, source, result):
    """PY013: homeContent filters 为 dict"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "homeContent":
                    method_source = ast.get_source_segment(source, item) or ""
                    if '"filters"' in method_source or "'filters'" in method_source:
                        result.ok("PY013", "homeContent 返回 filters 字段")
                    else:
                        result.error("PY013", "铁律8违规：homeContent 未返回 filters 字段")
                    return
    result.error("PY013", "未找到 homeContent 方法")


def check_instantiate(filepath, source, result):
    """PY014: 模拟实例化"""
    try:
        spec = importlib.util.spec_from_file_location("test_spider", filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "Spider"):
            sp = mod.Spider()
            result.ok("PY014", "Spider() 实例化成功")
        else:
            result.warn("PY014", "模块中无 Spider 类")
    except Exception as e:
        result.warn("PY014", "实例化失败（可能依赖缺失）: %s" % str(e)[:100])


def check_init_call(filepath, source, result):
    """PY015: 模拟调用 init"""
    try:
        spec = importlib.util.spec_from_file_location("test_spider2", filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "Spider"):
            sp = mod.Spider()
            sp.init('{"host":"https://example.com","direct":true}')
            result.ok("PY015", "init(extend) 调用成功")
        else:
            result.warn("PY015", "模块中无 Spider 类")
    except Exception as e:
        result.warn("PY015", "init调用失败（可能依赖缺失）: %s" % str(e)[:100])


def check_m3u8_cleaner(filepath, source, result):
    """PY016: m3u8广告清洗实现"""
    has_clean = re.search(r"def\s+_clean_m3u8\s*\(", source)
    has_ad_detect = re.search(r"def\s+_is_ad_segment\s*\(", source)
    has_parse = re.search(r"def\s+_parse_m3u8_segments\s*\(", source)
    if has_clean and has_ad_detect:
        extras = []
        if has_parse:
            extras.append("m3u8解析器")
        result.ok("PY016", "m3u8广告清洗已实现（_clean_m3u8 + _is_ad_segment%s）" % ("，含" + "、".join(extras) if extras else ""))
    else:
        missing = []
        if not has_clean:
            missing.append("_clean_m3u8")
        if not has_ad_detect:
            missing.append("_is_ad_segment")
        result.error("PY016", "铁律·广告拦截违规：未实现m3u8广告清洗（缺少 %s）" % " + ".join(missing))


def check_localProxy_impl(filepath, source, result):
    """PY017: localProxy 非空壳实现"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Spider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "localProxy":
                    method_source = ast.get_source_segment(source, item) or ""
                    # 检查是否是空壳：只有 return [404 或 return [404, ...]
                    lines = [l.strip() for l in method_source.split("\n") if l.strip() and not l.strip().startswith("#")]
                    # 去掉def行和docstring
                    body_lines = [l for l in lines if not l.startswith("def ") and not l.startswith('"""') and not l.startswith("'''")]
                    if len(body_lines) <= 2 and any("404" in l for l in body_lines):
                        result.error("PY017", "铁律·广告拦截违规：localProxy 是空壳（仅 return [404]），未实现m3u8清洗/图片代理")
                    else:
                        result.ok("PY017", "localProxy 已实现（非空壳，含 %d 行逻辑）" % len(body_lines))
                    return
    result.error("PY017", "未找到 localProxy 方法")


def check_ad_precheck(filepath, source, result):
    """PY018: 铁律17咨询——提示Spider头部是否有广告预检注释/广告处理实现，仅INFO提示不影响打包"""
    # 读取文件前80行查找广告预检注释
    head_lines = source.split("\n")[:80]
    precheck_line = None
    for line in head_lines:
        if "广告预检" in line and ("#" in line or "//" in line):
            precheck_line = line.strip()
            break
    if not precheck_line:
        result.info("PY018", "铁律17咨询：未找到广告预检注释（可选在Spider头部添加 # 广告预检: has_ads=..., score=...，不强制）")
        return
    # 解析has_ads值
    has_ads = None
    m = re.search(r'has_ads\s*[=:]\s*(True|False|true|false|是|否)', precheck_line, re.I)
    if m:
        has_ads = m.group(1).lower() in ("true", "是")
    if has_ads is None:
        result.info("PY018", "铁律17咨询：广告预检注释格式不规范（建议格式：# 广告预检: has_ads=True, score=65，不强制）")
        return
    if not has_ads:
        result.ok("PY018", "铁律17咨询：广告预检has_ads=False，无需广告处理（预检注释: %s）" % precheck_line[:60])
        return
    # has_ads=True，提示检查广告处理实现（_clean_m3u8 + _is_ad_segment + localProxy非空壳）
    has_clean = "_clean_m3u8" in source
    has_ad_seg = "_is_ad_segment" in source
    has_proxy = "localProxy" in source
    # 检查localProxy是否非空壳
    localProxy_non_empty = False
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Spider":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "localProxy":
                        method_source = ast.get_source_segment(source, item) or ""
                        lines = [l.strip() for l in method_source.split("\n") if l.strip() and not l.strip().startswith("#")]
                        body_lines = [l for l in lines if not l.startswith("def ") and not l.startswith('"""') and not l.startswith("'''")]
                        if not (len(body_lines) <= 2 and any("404" in l for l in body_lines)):
                            localProxy_non_empty = True
    except Exception:
        pass
    missing = []
    if not has_clean:
        missing.append("_clean_m3u8")
    if not has_ad_seg:
        missing.append("_is_ad_segment")
    if not has_proxy:
        missing.append("localProxy")
    elif not localProxy_non_empty:
        missing.append("localProxy(非空壳)")
    if missing:
        result.info("PY018", "铁律17咨询：广告预检has_ads=True但缺少广告处理实现: %s（建议实现localProxy非空壳+_clean_m3u8+_is_ad_segment，运行时auto智能开关也可自动处理，不强制）" % ", ".join(missing))
    else:
        result.ok("PY018", "铁律17咨询：广告预检has_ads=True且广告处理实现齐全（localProxy+_clean_m3u8+_is_ad_segment）")


def check_json_valid(filepath, source, result):
    """JSON001: JSON格式合法（json已非必需交付物，未提供则直接跳过）"""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            json.load(f)
        result.ok("JSON001", "配置JSON格式合法")
    except Exception as e:
        result.error("JSON001", "配置JSON格式错误: %s" % str(e)[:100])


def check_json_fields(filepath, source, result):
    """JSON002: 四字段齐全（json已非必需交付物，未提供则直接跳过）"""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = ["key", "name", "type", "ext"]
        missing = [k for k in required if k not in data]
        if missing:
            result.error("JSON002", "配置JSON缺少字段: %s" % ", ".join(missing))
        else:
            result.ok("JSON002", "配置JSON四字段齐全（key/name/type/ext）")
    except Exception:
        result.error("JSON002", "配置JSON解析失败，无法检查字段")


def check_json_ext_url(filepath, source, result):
    """JSON003: ext含站点URL（json已非必需交付物，未提供则直接跳过）"""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        ext = data.get("ext", {})
        if isinstance(ext, str):
            ext = json.loads(ext)
        has_url = False
        for v in (ext.values() if isinstance(ext, dict) else []):
            if isinstance(v, str) and v.startswith("http"):
                has_url = True
                break
        if has_url:
            result.ok("JSON003", "配置JSON ext含站点URL")
        else:
            result.error("JSON003", "配置JSON ext中未找到站点URL")
    except Exception:
        result.error("JSON003", "配置JSON ext解析失败")


def audit_spider(py_file, json_file=None, miniapp_dir=None):
    """主检测函数"""
    result = AuditResult()
    print("铁律14 Spider落盘前自动检测")
    print("检测文件: %s" % py_file)
    print("-" * 60)

    if not os.path.exists(py_file):
        print("错误：文件不存在 %s" % py_file)
        return False

    source = load_source(py_file)

    # 执行所有检测规则
    check_funcs = {
        "check_syntax": check_syntax,
        "check_class_spider": check_class_spider,
        "check_13_interfaces": check_13_interfaces,
        "check_classical_map": check_classical_map,
        "check_desensitize": check_desensitize,
        "check_desensitize_called": check_desensitize_called,
        "check_minor_filter": check_minor_filter,
        "check_proxy_rawsite": check_proxy_rawsite,
        "check_proxy_siteurl": check_proxy_siteurl,
        "check_proxy_config_read": check_proxy_config_read,
        "check_player_header": check_player_header,
        "check_detail_traverse_ids": check_detail_traverse_ids,
        "check_filters_dict": check_filters_dict,
        "check_instantiate": check_instantiate,
        "check_init_call": check_init_call,
        "check_m3u8_cleaner": check_m3u8_cleaner,
        "check_localProxy_impl": check_localProxy_impl,
        "check_ad_precheck": check_ad_precheck,
        "check_json_valid": check_json_valid,
        "check_json_fields": check_json_fields,
        "check_json_ext_url": check_json_ext_url,
    }

    for rule_id, level, func_name, desc in RULES:
        func = check_funcs.get(func_name)
        if func is None:
            continue
        if func_name.startswith("check_json"):
            func(json_file, source, result)
        else:
            func(py_file, source, result)

    # 小程序检测（如果提供了目录）
    if miniapp_dir and os.path.isdir(miniapp_dir):
        audit_miniapp(miniapp_dir, result)

    all_pass = result.summary()
    return all_pass


def audit_miniapp(miniapp_dir, result):
    """小程序预检（铁律14第四项）"""
    print("\n--- 小程序预检: %s ---" % miniapp_dir)
    # 检查 manifest.json
    manifest_path = os.path.join(miniapp_dir, "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            perms = manifest.get("permissions", [])
            required_perms = ["ui", "storage", "network"]
            missing_perms = [p for p in required_perms if p not in perms]
            if missing_perms:
                result.error("MINI001", "manifest.json 缺少权限: %s" % ", ".join(missing_perms))
            else:
                result.ok("MINI001", "manifest.json 权限齐全")
            # 检查是否写了 network.allowlist（铁律15禁止）
            if "network" in manifest and "allowlist" in manifest["network"]:
                result.warn("MINI002", "manifest.json 写了 network.allowlist（铁律15建议不写，可能触发HOST_NOT_ALLOWED）")
            else:
                result.ok("MINI002", "manifest.json 未写 network.allowlist（符合铁律15）")
        except Exception as e:
            result.error("MINI001", "manifest.json 解析失败: %s" % str(e)[:80])
    else:
        result.error("MINI001", "manifest.json 不存在")

    # 检查 app.js 脱敏
    appjs_path = os.path.join(miniapp_dir, "app.js")
    if os.path.exists(appjs_path):
        with open(appjs_path, "r", encoding="utf-8") as f:
            appjs = f.read()
        if "classicalMap" in appjs and "desensitize" in appjs:
            result.ok("MINI003", "app.js 内置 classicalMap + desensitize")
        else:
            result.error("MINI003", "铁律11违规：app.js 缺少 classicalMap/desensitize")
    else:
        result.warn("MINI003", "app.js 不存在，跳过脱敏检查")

    # 检查 style.css 暗黑主题
    css_path = os.path.join(miniapp_dir, "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        if "#FF2D55" in css or "#0D0D0D" in css:
            result.ok("MINI004", "style.css 暗黑主题配色正确（--accent:#FF2D55 / --bg:#0D0D0D）")
        elif "#FF2442" in css:
            result.error("MINI004", "铁律10违规：style.css 使用了红果旧配色 #FF2442，必须改为 #FF2D55")
        else:
            result.warn("MINI004", "style.css 未检测到标准暗黑主题配色")
    else:
        result.warn("MINI004", "style.css 不存在，跳过配色检查")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    py_file = sys.argv[1]
    json_file = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith(".json") else None
    miniapp_dir = None
    for arg in sys.argv[2:]:
        if os.path.isdir(arg):
            miniapp_dir = arg
            break

    all_pass = audit_spider(py_file, json_file, miniapp_dir)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
