# 段德机器人项目

TVBox影视源自动爬虫 + Telegram群机器人 + 订阅鉴权分发 全自动闭环系统。

## 功能特性

- 🤖 Telegram群机器人：网址入队、积分系统、面板交互、订阅分发
- 🕷️ 自动爬虫：四步流水线智能侦察→工具匹配→四壳Python Spider开发
- 📺 TVBox订阅：自动生成tvbox.json，支持Cloudflare KV分发
- 🔐 订阅鉴权：JWT Token + 群成员验证，退群立马失效
- 🔄 24小时守护：mihomo代理 + 机器人进程自动监控重启

## 快速部署

### 一键部署（推荐）

```bash
# 下载并执行一键部署脚本
curl -sL https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main/deploy/install.sh | bash
```

### 手动部署

```bash
# 克隆项目
git clone https://github.com/jwarrenrzflynn/TVpy.git
cd TVpy/deploy

# 执行部署
bash install.sh
```

## 配置说明

编辑 `tg_config.json`：

```json
{
  "bot": {
    "token": "你的Bot Token",
    "chat_id": -100群ID,
    "admin_id": 管理员用户ID
  },
  "auth": {
    "auth_secret": "鉴权密钥",
    "auth_worker_url": "Cloudflare Worker地址"
  },
  "github": {
    "token": "GitHub Token",
    "repo": "用户名/仓库名",
    "branch": "main"
  }
}
```

## 启动机器人

```bash
cd ~/duande_bot
python3 tg_bot_service.py
```

后台运行：
```bash
nohup python3 tg_bot_service.py >> scripts/logs/bot.log 2>&1 &
```

## 项目结构

```
duande_bot/
├── tg_bot_service.py    # Telegram机器人主服务
├── central_processor.py  # 中央处理器（任务调度）
├── db_helper.py          # 数据库助手
├── monitor_daemon.py     # 监控守护进程
├── smart_router.py       # 智能侦察路由
├── cloudflare_worker_deploy.js  # Cloudflare Worker鉴权脚本
├── mihomo_config.yaml    # mihomo代理配置
├── tg_config.json        # 机器人配置（需自行填写）
└── scripts/logs/         # 日志目录
```

## 技术栈

- Python 3.8+
- pyTelegramBotAPI
- requests
- SQLite3
- Cloudflare Workers + KV
- mihomo代理

## 许可证

MIT License
