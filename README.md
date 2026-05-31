# CTF 赛事日历

多源聚合的 CTF 赛事日历，自动采集国内外主流赛事平台及各省教育厅公告，支持管理后台和 HTTPS 部署。

## 功能

- **多源自动采集** — 每小时自动抓取 14 个数据源的最新赛事
- **智能状态识别** — 自动标记报名中/进行中/即将开始/已结束
- **多维度筛选** — 按状态、来源、类型、关键词快速过滤
- **管理后台** — 登录后可增删改赛事、CSV 导出、修改密码
- **安全认证** — 首次运行初始化管理员，密码哈希存储，CSRF 保护
- **HTTPS 部署** — 内置 Nginx + Certbot 配置

## 数据来源

| 来源 | 类型 |
|---|---|
| [Hello-CTF](https://hello-ctf.com) CN / Global | 赛事聚合 |
| [NSSCTF](https://www.nssctf.cn) | 赛事聚合 |
| [i春秋](https://www.ichunqiu.com) | 竞赛平台 |
| [BugKu](https://www.bugku.com) | 竞赛平台 |
| [CTFPlus](https://ctf.plus) | 赛事聚合 |
| 河南/安徽/江苏/广东/山东/浙江教育厅、北京教委 | 官方公告 |

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/hectorzhang2810-ux/ctf-calendar.git
cd ctf-calendar

# 2. 一键部署（开发模式）
chmod +x deploy-local.sh
./deploy-local.sh

# 3. 打开浏览器访问
# http://localhost:5000

# 4. 采集赛事数据
flask fetch
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3 + Flask |
| 数据库 | SQLite (WAL 模式) |
| 模板 | Jinja2 |
| 爬虫 | Requests + BeautifulSoup4 |
| 生产部署 | Gunicorn + Nginx + Certbot |
| 认证 | Session-based + PBKDF2 密码哈希 |

## 项目结构

```
ctf-calendar/
├── app/                    # 应用核心
│   ├── admin.py            # 管理后台路由
│   ├── auth.py             # 登录/登出/改密
│   ├── config.py           # 配置项
│   ├── database.py         # SQLite 操作
│   ├── routes.py           # 前端路由
│   ├── models.py           # 状态计算
│   ├── scrapers/           # 爬虫模块
│   │   ├── hello_ctf.py    # Hello-CTF 爬虫
│   │   ├── nssctf.py       # NSSCTF 爬虫
│   │   ├── ichunqiu.py     # i春秋 爬虫
│   │   ├── bugku.py        # BugKu 爬虫
│   │   ├── ctfplus.py      # CTFPlus 爬虫
│   │   └── provinces.py    # 各省教育厅通用爬虫
│   ├── static/css/         # 样式
│   └── templates/          # Jinja2 模板
├── deploy/                 # 生产部署文件
│   ├── deploy.sh           # 生产部署脚本
│   ├── nginx.conf          # Nginx HTTPS 配置
│   ├── ctf-calendar.service # systemd 服务
│   └── ctf-calendar.cron   # 定时采集任务
├── requirements.txt
├── Makefile
└── README.md
```

## 生产部署

```bash
# 前置条件: python3, nginx, certbot, 已解析的域名
sudo ./deploy/deploy.sh /opt/ctf-calendar your-domain.com
```

详见 [deploy/README.md](deploy/README.md)（待完善）。

## 安全说明

- 密码使用 `werkzeug.security.generate_password_hash`（PBKDF2-SHA256）存储
- 所有管理 POST 请求需 CSRF token 验证
- Session 使用服务端随机密钥签名
- 首次运行无默认密码，强制进入初始化页面创建管理员
- 数据库文件 (`.db`) 已加入 `.gitignore`，不会提交到版本控制
- 生产部署请通过环境变量设置 `SECRET_KEY`

## License

MIT
