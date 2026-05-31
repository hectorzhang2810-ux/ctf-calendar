"""
合规爬虫基类

所有数据源采集器必须继承 BaseScraper。
政府网站采集器必须继承 GovSiteScraper（增加了合规限制）。
"""
import time
import logging
from typing import Optional

import requests
from urllib.robotparser import RobotFileParser

from app.config import Config

logger = logging.getLogger(__name__)


class BaseScraper:
    """通用数据源采集基类"""

    SOURCE_NAME = 'base'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.SCRAPER_USER_AGENT,
        })
        self.last_request_time = 0.0

    def fetch(self) -> list[dict]:
        """
        采集数据，返回统一格式的比赛信息列表。
        子类必须实现此方法。
        """
        raise NotImplementedError

    def request(self, url: str) -> Optional[str]:
        """发送 HTTP 请求（带限速）"""
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=Config.SCRAPER_TIMEOUT)
            self.last_request_time = time.time()
            if resp.status_code >= 500:
                logger.error(f"Server error {resp.status_code} on {url}")
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"Request failed: {url} - {e}")
            return None

    def _rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < Config.SCRAPER_REQUEST_INTERVAL:
            time.sleep(Config.SCRAPER_REQUEST_INTERVAL - elapsed)


class GovSiteScraper(BaseScraper):
    """
    政府网站合规爬虫基类

    增加了 robots.txt 检查和更严格的合规控制。
    所有爬取省教育厅网站的爬虫必须继承此类。
    """

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.robots = None
        self._check_robots_txt()

    def _check_robots_txt(self):
        """检查 robots.txt 并记录结果"""
        robots_url = f"{self.base_url}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            self.robots = rp
            allowed = rp.can_fetch(Config.SCRAPER_USER_AGENT, self.base_url)
            if not allowed:
                logger.warning(
                    f"robots.txt disallows our UA on {self.base_url}. "
                    f"Proceeding with caution."
                )
            else:
                logger.info(f"robots.txt OK for {self.base_url}")
        except Exception as e:
            logger.info(f"No robots.txt or unreadable on {self.base_url}: {e}")
            self.robots = None

    def request(self, url: str) -> Optional[str]:
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=Config.SCRAPER_TIMEOUT)
            self.last_request_time = time.time()
            if resp.status_code >= 500:
                logger.error(f"Server error {resp.status_code} on {url}")
                return None
            resp.raise_for_status()
            # Chinese gov sites often misreport encoding as ISO-8859-1
            # Use apparent encoding or force utf-8
            resp.encoding = 'utf-8'
            html = resp.text
            if len(html) < 100:
                logger.warning(f"Suspiciously short response from {url}")
                return None
            return html
        except requests.RequestException as e:
            logger.warning(f"Request failed: {url} - {e}")
            return None

    @staticmethod
    def attach_source(record: dict, source_url: str) -> dict:
        record['source_url'] = source_url
        record.setdefault('detail', '')
        record['detail'] += (
            " | 本信息来自政府公开通知公告，仅供教育参考，请以官方发布为准。"
        )
        return record
