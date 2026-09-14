#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坚果云自动上传工具（铁律16）
- 支持单文件/目录递归/增量跳过
- 上传自动改名+改后缀+文件名脱敏（防封号）
- 日志记录
用法:
  python3 nutstore_uploader.py <文件1> [文件2] ...
  python3 nutstore_uploader.py --list [远程目录]
"""
import os, sys, json, base64, requests, logging
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "nutstore_config.json")

# ========== 文件名古典映射脱敏表（铁律16，防封号） ==========
FILENAME_MAP = {
    # 站点类型
    "宅男视频": "光影图鉴", "宅男": "光影", "AV": "光影", "国产AV": "国产光影",
    "视频": "图鉴", "影视": "光影", "影视源包": "图鉴合集", "源包": "合集",
    "解剖报告": "品鉴录", "解剖": "品鉴", "APK": "法器", "apk": "法器",
    "spider": "daoke", "Spider": "Daoke", "爬虫": "寻道", "tvbox": "yingku",
    "TVBox": "YingKu", "猫源": "猫谱", "drpy": "daoyin", "小程序": "微阁",
    "miniapp": "weige", "西瓜短剧": "瓜田小戏",
    # 风月类站点名脱敏
    "欲女": "欲语", "心经": "心镜", "欲女心经": "欲语心镜",
    "红桃": "鸿图", "桃子": "陶然", "橘子": "菊隐", "小黄人": "小皇人",
    "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫",
    "激情": "云雨", "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔",
    "强奸": "强占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
    "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
    "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人", "巨乳": "丰盈",
    "裸体": "玉体", "自慰": "弄玉", "口交": "含朱", "肛交": "后庭",
    "群交": "合卺", "车震": "车行", "野战": "郊合", "丝袜": "丝履",
    "内衣": "亵衣", "情趣": "风月", "春药": "催情", "赌博": "孤注",
    "毒品": "药石", "暴力": "杀伐", "恐怖": "幽冥", "国产": "华夏",
    "日韩": "东瀛", "欧美": "西洋", "港台": "香江", "动漫": "丹青",
    "综艺": "百戏", "电视剧": "传奇", "电影": "光影",
}

def setup_logging():
    log_dir = os.path.join(SCRIPT_DIR, "nutstore_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "upload_%s.log" % datetime.now().strftime("%Y%m%d"))
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("配置文件不存在:", CONFIG_PATH)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def auth_header(cfg):
    token = base64.b64encode(("%s:%s" % (cfg["username"], cfg["password"])).encode()).decode()
    return {"Authorization": "Basic %s" % token}

def dav_url(cfg, remote_path):
    base = cfg["webdav_url"].rstrip("/")
    if not remote_path.startswith("/"):
        remote_path = "/" + remote_path
    return base + remote_path

# ========== 文件名脱敏+改后缀 ==========
def desensitize_filename(filename, cfg):
    """文件名脱敏：古典映射替换敏感词 + 改后缀"""
    if not cfg.get("upload_rename", False):
        return filename
    
    name, ext = os.path.splitext(filename)
    
    # 1. 文件名古典映射脱敏
    if cfg.get("desensitize_filename", True):
        for k, v in FILENAME_MAP.items():
            name = name.replace(k, v)
    
    # 2. 改后缀
    rename_map = cfg.get("rename_map", {})
    if ext.lower() in rename_map:
        ext = rename_map[ext.lower()]
    
    return name + ext

def ensure_remote_dir(cfg, remote_path, logger):
    """确保远程目录存在"""
    headers = auth_header(cfg)
    url = dav_url(cfg, remote_path)
    try:
        r = requests.request("MKCOL", url, headers=headers, timeout=15)
        if r.status_code in (201, 405):
            return True
        return True
    except Exception as e:
        logger.warning("创建目录异常: %s" % e)
        return True

def remote_file_exists(cfg, remote_path, logger):
    """检查远程文件是否存在"""
    headers = auth_header(cfg)
    url = dav_url(cfg, remote_path)
    try:
        r = requests.head(url, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def delete_remote_file(cfg, remote_path, logger):
    """删除远程文件，用于覆盖更新前清理历史版本"""
    headers = auth_header(cfg)
    url = dav_url(cfg, remote_path)
    try:
        r = requests.delete(url, headers=headers, timeout=15)
        if r.status_code in (200, 204):
            return True
        return False
    except Exception as e:
        logger.warning("删除历史文件异常: %s" % e)
        return False

def upload_file(cfg, local_path, remote_dir, logger, skip_existing=True):
    """上传单个文件，自动改名脱敏。
    铁律16：上传前必查历史文件。force_overwrite=true时，存在则先删除再上传（强制覆盖更新）；
    force_overwrite=false时，增量模式比较大小，一致才跳过，不一致则删除再上传。
    返回 (success: bool, skipped: bool)"""
    if not os.path.isfile(local_path):
        logger.error("文件不存在: %s" % local_path)
        return False, False
    
    original_name = os.path.basename(local_path)
    # 上传前自动改名+脱敏
    remote_name = desensitize_filename(original_name, cfg)
    remote_path = remote_dir.rstrip("/") + "/" + remote_name
    
    force_overwrite = cfg.get("force_overwrite", False)
    
    # 上传前检查历史文件（铁律16：必查历史）
    history_exists = remote_file_exists(cfg, remote_path, logger)
    if history_exists:
        if force_overwrite:
            # 强制覆盖模式：不管大小是否一致，先删除历史文件再上传，确保云盘为最新版
            logger.info("发现历史文件(强制覆盖): %s -> %s，先删除再上传" % (original_name, remote_name))
            delete_remote_file(cfg, remote_path, logger)
        elif skip_existing:
            # 增量模式：检查本地与远程大小是否一致，一致才跳过，不一致则覆盖更新
            try:
                headers = auth_header(cfg)
                url = dav_url(cfg, remote_path)
                r = requests.head(url, headers=headers, timeout=10)
                remote_size = int(r.headers.get("Content-Length", 0))
                local_size = os.path.getsize(local_path)
                if remote_size == local_size and remote_size > 0:
                    logger.info("跳过(已存在且大小一致): %s -> %s" % (original_name, remote_name))
                    return True, True
            except Exception:
                pass
            # 历史文件存在但大小不同，先删除再上传，确保覆盖更新
            logger.info("发现历史文件(需更新): %s -> %s，先删除再上传" % (original_name, remote_name))
            delete_remote_file(cfg, remote_path, logger)
        else:
            # 非增量模式：直接删除再上传
            logger.info("发现历史文件(覆盖模式): %s -> %s，先删除再上传" % (original_name, remote_name))
            delete_remote_file(cfg, remote_path, logger)
    
    ensure_remote_dir(cfg, remote_dir, logger)
    
    headers = auth_header(cfg)
    headers["Content-Type"] = "application/octet-stream"
    url = dav_url(cfg, remote_path)
    
    try:
        with open(local_path, "rb") as f:
            r = requests.put(url, data=f, headers=headers, timeout=120)
        if r.status_code in (200, 201, 204):
            size = os.path.getsize(local_path)
            logger.info("上传成功: %s -> %s (%d bytes)" % (original_name, remote_name, size))
            return True, False
        else:
            logger.error("上传失败: %s HTTP %d %s" % (original_name, r.status_code, r.text[:100]))
            return False, False
    except Exception as e:
        logger.error("上传异常: %s %s" % (original_name, e))
        return False, False

def list_remote(cfg, remote_dir, logger):
    """列出远程目录"""
    headers = auth_header(cfg)
    headers["Depth"] = "1"
    url = dav_url(cfg, remote_dir)
    try:
        r = requests.request("PROPFIND", url, headers=headers, timeout=15)
        if r.status_code == 207:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            ns = {"d": "DAV:"}
            logger.info("目录: %s" % remote_dir)
            logger.info("-" * 60)
            for resp in root.findall("d:response", ns):
                href = resp.find("d:href", ns)
                prop = resp.find("d:propstat/d:prop", ns)
                if href is not None and prop is not None:
                    name = href.text.split("/")[-2] if href.text.endswith("/") else href.text.split("/")[-1]
                    size = prop.find("d:getcontentlength", ns)
                    is_dir = prop.find("d:resourcetype/d:collection", ns) is not None
                    size_str = "<DIR>" if is_dir else (size.text + " bytes" if size is not None else "?")
                    logger.info("  %-40s %s" % (name, size_str))
        else:
            logger.error("列表失败: HTTP %d" % r.status_code)
    except Exception as e:
        logger.error("列表异常: %s" % e)

def main():
    logger = setup_logging()
    cfg = load_config()

    # 坚果云上传开关（用户可暂停上传，代码保留，随时可恢复）
    if not cfg.get("enabled", True):
        print("=" * 50)
        print("⏸️  坚果云上传已暂停（配置 enabled=false）")
        print("   成品文件不上传云盘，仅推送TG群")
        print("   如需恢复上传，将 nutstore_config.json 中 enabled 改为 true")
        print("=" * 50)
        logger.info("坚果云上传已暂停（enabled=false），跳过上传")
        sys.exit(0)

    remote_root = cfg.get("remote_root", "/个人文件/")
    
    # 修复：--help/-h 参数处理（之前被当成文件名上传）
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("--help", "-h", "help") else 1)
    
    if sys.argv[1] == "--list":
        remote_dir = sys.argv[2] if len(sys.argv) > 2 else remote_root
        list_remote(cfg, remote_dir, logger)
        return
    
    # 过滤掉可能的误传参数（如 --help 出现在中间）
    file_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not file_args:
        print("错误：未指定要上传的文件路径")
        print(__doc__)
        sys.exit(1)
    
    success = 0
    skipped = 0
    failed = 0
    failed_files = []
    
    for local_path in file_args:
        local_path = os.path.abspath(local_path)
        if os.path.isdir(local_path):
            # 目录递归上传
            for root, dirs, files in os.walk(local_path):
                for f in files:
                    fp = os.path.join(root, f)
                    ok, was_skipped = upload_file(cfg, fp, remote_root, logger)
                    if ok:
                        if was_skipped:
                            skipped += 1
                        else:
                            success += 1
                    else:
                        failed += 1
                        failed_files.append(fp)
        else:
            ok, was_skipped = upload_file(cfg, local_path, remote_root, logger)
            if ok:
                if was_skipped:
                    skipped += 1
                else:
                    success += 1
            else:
                failed += 1
                failed_files.append(local_path)
    
    logger.info("===== 上传完成 =====")
    logger.info("成功: %d, 跳过: %d, 失败: %d" % (success, skipped, failed))
    
    if failed > 0:
        # 失败重试最多3次（覆盖上传，skip_existing=False）
        logger.info("失败文件重试中...")
        retry_success = 0
        for retry in range(3):
            still_failed = []
            for fp in failed_files:
                if os.path.isfile(fp):
                    ok, _ = upload_file(cfg, fp, remote_root, logger, skip_existing=False)
                    if ok:
                        retry_success += 1
                        failed -= 1
                        success += 1
                    else:
                        still_failed.append(fp)
            failed_files = still_failed
            if not failed_files:
                logger.info("重试全部成功")
                break
            logger.info("第%d次重试，仍有%d个失败" % (retry + 1, len(failed_files)))
        if failed_files:
            logger.error("最终仍有 %d 个文件上传失败: %s" % (len(failed_files), failed_files[:5]))
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
