# 段德机器人项目 - 备份

## 项目架构（金字塔模式）
```
第0层：定时任务（24小时守护 + AI自动处理）
第1层：基础设施（mihomo代理 + tg_bot_service机器人）
第2层：统一数据库（bot_data.db，20张表，DBHelper模块）
第3层：所有新建会话（共享数据库 + 上集回顾功能）
```

## 关键文件
- `scripts/tg_bot_service.py` - 机器人主程序（134KB）
- `scripts/db_helper.py` - 统一数据库访问模块
- `scripts/central_processor.py` - 中央处理器（任务调度）
- `scripts/tg_pusher.py` - Telegram推送模块
- `scripts/smart_router.py` - 智能侦察路由
- `scripts/bot_data.db` - 统一数据库（20张表，含31个py成品）
- `scripts/tg_config.json` - 机器人配置
- `scripts/tg_pending_urls.json` - 待处理网址队列
- `SKILL.md` - 技能文档（铁律+四步流水线）

## 数据库表（20张）
config, users, point_transactions, pending_urls, url_submitters, daily_counts,
py_files(31个成品), proxy_nodes(50个节点), private_messages, session_last_message,
doubao_session_recap(上集回顾), doubao_chat_messages(对话流水),
cron_task_log, sessions, push_history, push_queue, central_state,
central_commands, central_tasks, smart_qa

## 使用方法
```python
import sys
sys.path.insert(0, 'scripts')
import db_helper as db

# 新建会话上集回顾
recap = db.cmd_previously_on(session_id='xxx')
print(recap['summary'])

# 获取待处理任务
task = db.cmd_run()

# 保存py文件
db.save_py_file('18㊙️站点.py', content_bytes)
```

## 备份时间
2026-09-13
