"""
河南省教育厅通知公告采集器

从 jyt.henan.gov.cn 的通知公告栏目中，抓取网络安全相关比赛通知。
继承 GovSiteScraper，强制执行合规措施。
"""
import logging
import re
from datetime import datetime

from app.config import Config
from app.scrapers.base import GovSiteScraper

logger = logging.getLogger(__name__)


class HenanEduScraper(GovSiteScraper):
    SOURCE_NAME = 'henan-edu'

    def __init__(self):
        site_config = Config.PROVINCE_EDUCATION_SITES.get('henan', {})
        super().__init__(base_url=site_config.get('base_url', 'https://jyt.henan.gov.cn'))
        self.site_config = site_config

    def fetch(self) -> list[dict]:
        """采集河南省教育厅通知公告中的比赛信息"""
        list_url = self.base_url + self.site_config.get('list_path', '/xxgk/gggs/')
        html = self.request(list_url)
        if not html:
            logger.warning("Failed to fetch Henan education notice list")
            return []

        # 提取公告列表中的链接
        # 河南省教育厅列表页: 每个 li 包含标题和链接
        notice_links = self._extract_notice_links(html)
        logger.info(f"Found {len(notice_links)} notices on list page")

        results = []
        for title, url in notice_links:
            if not self._is_competition_related(title):
                logger.debug(f"Skipping non-competition notice: {title}")
                continue

            logger.info(f"Found competition notice: {title}")
            full_url = url if url.startswith('http') else self.base_url + url
            detail_html = self.request(full_url)
            if not detail_html:
                continue

            record = self._parse_notice(title, detail_html, full_url)
            if record:
                self.attach_source(record, full_url)
                results.append(record)

        logger.info(f"Henan Edu: collected {len(results)} competitions")
        return results

    def _extract_notice_links(self, html: str) -> list[tuple[str, str]]:
        """
        从列表页 HTML 提取 (标题, 链接) 对。
        处理河南省教育厅常见的列表页结构。
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        links = []

        # 常见结构: ul > li > a
        for a_tag in soup.find_all('a', href=True):
            title = a_tag.get_text(strip=True)
            href = a_tag['href']
            if title and len(title) > 5 and href.endswith('.html'):
                links.append((title, href))

        return links

    def _is_competition_related(self, title: str) -> bool:
        keywords = self.site_config.get('keywords', [
            '网络安全', 'CTF', '信息安全', '大赛', '竞赛', '攻防', '网安'
        ])
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in keywords)

    def _parse_notice(self, title: str, html: str, url: str) -> dict | None:
        """
        从通知详情页解析比赛信息，返回统一格式的记录。
        使用正则表达式提取报名时间、比赛时间等关键字段。
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        text = soup.get_text(separator='\n')

        record = {
            'name': title,
            'source': self.SOURCE_NAME,
            'link': url,
            'organizer': '河南省教育厅',
            'type': 'CTF',
            'format': '未知',
            'mode': '线上',
            'detail': '',
            'reg_start': '',
            'reg_end': '',
            'comp_start': '',
            'comp_end': '',
        }

        # 提取主办单位
        organizer_match = re.search(r'主办[单位：:]\s*([^\n。]+)', text)
        if organizer_match:
            record['organizer'] = organizer_match.group(1).strip()

        # 提取注册报名时间
        reg_match = re.search(
            r'注册报名时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*至\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
            text
        )
        if reg_match:
            record['reg_start'] = self._build_iso(
                reg_match.group(1), reg_match.group(2), reg_match.group(3), reg_match.group(4)
            )
            record['reg_end'] = self._build_iso(
                reg_match.group(5), reg_match.group(6), reg_match.group(7), reg_match.group(8)
            )

        # 提取报名时间（第二种格式）
        if not record['reg_start']:
            reg_match2 = re.search(
                r'报名时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
                text
            )
            if reg_match2:
                record['reg_start'] = self._build_iso(
                    reg_match2.group(1), reg_match2.group(2), reg_match2.group(3), reg_match2.group(4)
                )
                record['reg_end'] = self._build_iso(
                    reg_match2.group(5), reg_match2.group(6), reg_match2.group(7), reg_match2.group(8)
                )

        # 提取线上赛时间
        online_match = re.search(
            r'线上[挑战赛]*时间[：:]\s*(?:网络安全赛[：:])?\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
            text
        )
        if online_match:
            end_year = online_match.group(5) or online_match.group(1)
            record['comp_start'] = self._build_iso(
                online_match.group(1), online_match.group(2), online_match.group(3), online_match.group(4)
            )
            record['comp_end'] = self._build_iso(
                end_year, online_match.group(6), online_match.group(7), online_match.group(8)
            )

        # 提取线下赛时间
        if not record['comp_start']:
            offline_match = re.search(
                r'线下[精英赛]*时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*[至到]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日',
                text
            )
            if offline_match:
                end_year = offline_match.group(4) or offline_match.group(1)
                record['comp_start'] = self._build_iso(
                    offline_match.group(1), offline_match.group(2), offline_match.group(3), '09:00'
                )
                record['comp_end'] = self._build_iso(
                    end_year, offline_match.group(5), offline_match.group(6), '18:00'
                )
                record['mode'] = '线下'

        # 提取注册报名入口链接
        link_match = re.search(r'(?:注册)?报名(?:入口|网址)[：:]\s*(https?://[^\s\n]+)', text)
        if link_match:
            record['detail'] = f"报名入口: {link_match.group(1)}"

        # 如果没有解析到任何时间，返回 None
        if not record['comp_start'] and not record['comp_end']:
            logger.warning(f"Could not parse time from notice: {title}")
            return None

        return record

    @staticmethod
    def _build_iso(year: str, month: str, day: str, time_str: str | None) -> str:
        """构建 ISO 8601 时间字符串"""
        y = year
        m = month.zfill(2)
        d = day.zfill(2)
        t = time_str or '00:00'
        if ':' not in t:
            t = '00:00'
        return f"{y}-{m}-{d}T{t}:00+08:00"
