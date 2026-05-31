import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.config import Config
from app.scrapers.base import GovSiteScraper

logger = logging.getLogger(__name__)


class ProvinceEduScraper(GovSiteScraper):
    """
    多省份教育厅通知公告采集器

    从各省教育厅的公示公告/通知公告栏目中，抓取网络安全相关比赛通知。
    每个省份的配置在 Config.PROVINCE_EDUCATION_SITES 中定义。
    继承 GovSiteScraper，自动执行 robots.txt 检查和请求限速。
    """

    SOURCE_NAME = 'province-edu'

    def __init__(self, province_key: str):
        self.province_key = province_key
        site_config = Config.PROVINCE_EDUCATION_SITES.get(province_key, {})
        base_url = site_config.get('base_url', '')
        super().__init__(base_url=base_url)
        self.site_config = site_config
        self.province_name = site_config.get('name', province_key)
        # Each province instance gets a unique source name for DB tagging
        self.SOURCE_NAME = site_config.get('source_name', f'{province_key}-edu')

    def fetch(self) -> list[dict]:
        if not self.base_url:
            logger.warning(f"Province '{self.province_key}' has no base_url, skipping")
            return []

        list_path = self.site_config.get('list_path', '/')
        list_url = urljoin(self.base_url, list_path)
        logger.info(f"[{self.province_name}] Fetching notice list: {list_url}")

        html = self.request(list_url)
        if not html:
            logger.warning(f"[{self.province_name}] Failed to fetch list page")
            return []

        notice_links = self._extract_notice_links(html)
        logger.info(f"[{self.province_name}] Found {len(notice_links)} potential notice links")

        results = []
        for title, url in notice_links:
            if not self._is_competition_related(title):
                continue

            logger.info(f"[{self.province_name}] Competition notice: {title}")
            full_url = url if url.startswith('http') else urljoin(self.base_url, url)
            detail_html = self.request(full_url)
            if not detail_html:
                continue

            record = self._parse_notice(title, detail_html, full_url)
            if record:
                self.attach_source(record, full_url)
                results.append(record)

        logger.info(f"[{self.province_name}] Collected {len(results)} competitions")
        return results

    def _extract_notice_links(self, html: str) -> list[tuple[str, str]]:
        """Extract (title, url) pairs from the list page HTML."""
        soup = BeautifulSoup(html, 'lxml')
        links = []

        # Strategy 1: common gov site pattern — <a> with title in list
        for a_tag in soup.find_all('a', href=True):
            title = a_tag.get_text(strip=True)
            href = a_tag['href']
            if not title or len(title) < 6:
                continue
            # Filter for typical article link patterns
            if href.endswith(('.html', '.htm', '.shtml', '.asp', '.aspx')):
                links.append((title, href))
            elif '/' in href and len(href) > 10 and not href.startswith(('#', 'javascript:', 'mailto:')):
                links.append((title, href))

        # Deduplicate by URL while keeping the best (longest) title
        seen = {}
        for title, href in links:
            if href in seen:
                if len(title) > len(seen[href][0]):
                    seen[href] = (title, href)
            else:
                seen[href] = (title, href)

        return list(seen.values())

    def _is_competition_related(self, title: str) -> bool:
        keywords = self.site_config.get('keywords', [
            '网络安全', 'CTF', '信息安全', '大赛', '竞赛', '攻防', '网安',
        ])
        return any(kw.lower() in title.lower() for kw in keywords)

    def _parse_notice(self, title: str, html: str, url: str) -> dict | None:
        """Parse competition info from a notice detail page."""
        soup = BeautifulSoup(html, 'lxml')
        text = soup.get_text(separator='\n')

        record = {
            'name': title,
            'source': self.SOURCE_NAME,
            'link': url,
            'organizer': f'{self.province_name}省教育厅',
            'type': 'CTF',
            'format': '未知',
            'mode': '线上',
            'detail': '',
            'reg_start': '',
            'reg_end': '',
            'comp_start': '',
            'comp_end': '',
        }

        # Extract organizer
        org_match = re.search(r'主办[单位：:]\s*([^\n。，]+)', text)
        if org_match:
            record['organizer'] = org_match.group(1).strip()

        # Extract registration time (multiple format variations)
        reg_patterns = [
            r'(?:注册)?报名时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
            r'(?:注册)?报名时间[：:]\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2}:\d{2})?\s*[至到]\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2}:\d{2})?',
            r'报名[截止时间：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日',
        ]
        for pattern in reg_patterns:
            m = re.search(pattern, text)
            if m:
                record['reg_start'] = self._build_iso(
                    m.group(1), m.group(2), m.group(3), m.group(4) if len(m.groups()) >= 4 else ''
                )
                if len(m.groups()) >= 8 and m.group(5):
                    record['reg_end'] = self._build_iso(
                        m.group(5), m.group(6), m.group(7), m.group(8) if len(m.groups()) >= 8 else ''
                    )
                break

        # Extract competition time (variations: 线上赛, 线下赛, 比赛, 竞赛)
        comp_patterns = [
            r'线上[赛挑战赛]*时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
            r'(?:决赛|竞赛|大赛)[时间：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
            r'比赛时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?\s*[至到]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?',
        ]
        for pattern in comp_patterns:
            m = re.search(pattern, text)
            if m:
                end_year = m.group(5) if len(m.groups()) >= 5 and m.group(5) else m.group(1)
                record['comp_start'] = self._build_iso(
                    m.group(1), m.group(2), m.group(3), m.group(4) or ''
                )
                record['comp_end'] = self._build_iso(
                    end_year, m.group(6), m.group(7), m.group(8) or ''
                )
                break

        # Try to extract competition date from the title (御网杯 pattern)
        if not record['comp_start']:
            title_match = re.search(
                r'(\d{4})年(\d{1,2})月至(\d{1,2})月',
                title
            )
            if title_match:
                year = title_match.group(1)
                record['comp_start'] = f'{year}-{title_match.group(2).zfill(2)}-01'
                record['comp_end'] = f'{year}-{title_match.group(3).zfill(2)}-28'

        return record

    @staticmethod
    def _build_iso(year: str, month: str, day: str, time_str: str = '') -> str:
        try:
            y = year.zfill(4) if len(year) <= 4 else year[:4]
            m = month.zfill(2)
            d = day.zfill(2)
            if time_str and ':' in time_str:
                parts = time_str.split(':')
                h = parts[0].zfill(2)
                mi = parts[1].zfill(2)
                return f'{y}-{m}-{d}T{h}:{mi}:00'
            return f'{y}-{m}-{d}'
        except Exception:
            return ''


def create_province_scrapers() -> list[ProvinceEduScraper]:
    """Create scraper instances for all configured provinces."""
    scrapers = []
    for province_key in Config.PROVINCE_EDUCATION_SITES:
        scraper = ProvinceEduScraper(province_key)
        scrapers.append(scraper)
    return scrapers
