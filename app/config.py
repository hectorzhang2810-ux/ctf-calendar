"""
应用配置
"""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        import warnings
        warnings.warn(
            "SECRET_KEY environment variable not set! "
            "Using a random key — sessions will be invalidated on restart. "
            "Set SECRET_KEY in production."
        )
        SECRET_KEY = os.urandom(32).hex()

    # 日志
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # 数据库
    DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'competitions.db'))

    # 爬虫
    SCRAPER_USER_AGENT = (
        "CTF-Calendar-Bot/1.0 "
        "(Educational non-commercial project; "
        "contact: admin@example.com)"
    )
    SCRAPER_REQUEST_INTERVAL = 3.0  # 合规请求间隔（秒）
    SCRAPER_TIMEOUT = 15

    # 采集开关 —— 可单独启停每个数据源
    SCRAPER_ENABLED = {
        'hello_ctf_cn': True,
        'hello_ctf_global': True,
        'henan_edu': True,
        'anhui_edu': True,
        'beijing_edu': True,
        'jiangsu_edu': True,
        'guangdong_edu': True,
        'shandong_edu': True,
        'zhejiang_edu': True,
        'nssctf': True,
        'ctfplus': True,
        'bugku': True,
        'ichunqiu': True,
    }

    # 采集频率（分钟），cron 实际执行间隔
    SCRAPER_INTERVAL_MINUTES = 60

    # 管理后台认证（已迁移至数据库，此配置仅保留供旧版兼容）
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ctf2026')

    # 数据源 URLs
    HELLO_CTF_CN_URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/CN.json"
    HELLO_CTF_GLOBAL_URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/Global.json"

    # iChunQiu API 签名密钥（来自前端 JS，非敏感凭据，但提取到配置便于维护）
    ICHUNQIU_SECRET = os.environ.get('ICHUNQIU_SECRET', '9ebced8552d853232fb766ec3aed153a24578999')

    # 各省教育厅监控列表
    # list_path: 通知公告列表页路径（通过 research 确认）
    PROVINCE_EDUCATION_SITES = {
        'henan': {
            'name': '河南',
            'base_url': 'https://jyt.henan.gov.cn',
            'list_path': '/xxgk/gggs/',
            'source_name': 'henan_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '大赛', '竞赛', '攻防', '网安'],
        },
        'anhui': {
            'name': '安徽',
            'base_url': 'https://jyt.ah.gov.cn',
            'list_path': '/',
            'source_name': 'anhui_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '信息安全竞赛', '大赛', '竞赛'],
        },
        'jiangsu': {
            'name': '江苏',
            'base_url': 'https://jyt.jiangsu.gov.cn',
            'list_path': '/col/col58320/index.html',
            'source_name': 'jiangsu_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '领航杯', '大赛', '竞赛'],
        },
        'guangdong': {
            'name': '广东',
            'base_url': 'https://edu.gd.gov.cn',
            'list_path': '/zwgknew/gsgg/',
            'source_name': 'guangdong_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '大赛', '竞赛', '攻防'],
        },
        'shandong': {
            'name': '山东',
            'base_url': 'https://edu.shandong.gov.cn',
            'list_path': '/col/col107093/index.html',
            'source_name': 'shandong_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '技能大赛', '竞赛'],
        },
        'zhejiang': {
            'name': '浙江',
            'base_url': 'https://jyt.zj.gov.cn',
            'list_path': '/col/col1532802/index.html',
            'source_name': 'zhejiang_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '大赛', '竞赛'],
        },
        'beijing': {
            'name': '北京',
            'base_url': 'https://jw.beijing.gov.cn',
            'list_path': '/tzgg/',
            'source_name': 'beijing_edu',
            'encoding': 'utf-8',
            'keywords': ['网络安全', 'CTF', '信息安全', '大赛', '竞赛'],
        },
    }
