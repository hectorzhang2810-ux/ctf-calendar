"""
Hello-CTFtime 数据源采集器

从 ProbiusOfficial/Hello-CTFtime 项目获取国内和国外赛事 JSON 数据。
这是最轻量的数据源（纯 API，零解析成本）。
"""
import logging

from app.config import Config
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HelloCTFScraper(BaseScraper):
    SOURCE_NAME_CN = 'hello-ctf-cn'
    SOURCE_NAME_GLOBAL = 'hello-ctf-global'

    def fetch(self) -> list[dict]:
        results = []
        results.extend(self._fetch_cn())
        results.extend(self._fetch_global())
        return results

    def _fetch_cn(self) -> list[dict]:
        raw = self.request(Config.HELLO_CTF_CN_URL)
        if not raw:
            return []

        import json
        try:
            data = json.loads(raw)
            items = data.get('data', {}).get('result', [])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse Hello-CTF CN JSON: {e}")
            return []

        results = []
        for item in items:
            try:
                comp_start = self._parse_time(item.get('comp_time_start', ''))
                comp_end = self._parse_time(item.get('comp_time_end', ''))

                if not comp_start or not comp_end:
                    continue

                link = item.get('link', '')
                mode = '线下' if '线下' in item.get('detail', '') else '线上'
                if link == '/isPrepare':
                    link = ''

                record = {
                    'name': item.get('name', ''),
                    'source': self.SOURCE_NAME_CN,
                    'comp_start': comp_start,
                    'comp_end': comp_end,
                    'link': link or '',
                    'organizer': '',
                    'detail': item.get('detail', ''),
                    'mode': mode,
                    'format': '未知',
                    'type': 'CTF',
                }
                results.append(record)
            except Exception as e:
                logger.warning(f"Failed to process CN item {item.get('name')}: {e}")
                continue

        logger.info(f"Hello-CTF CN: collected {len(results)} competitions")
        return results

    def _fetch_global(self) -> list[dict]:
        raw = self.request(Config.HELLO_CTF_GLOBAL_URL)
        if not raw:
            return []

        import json
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse Hello-CTF Global JSON: {e}")
            return []

        results = []
        for item in items:
            try:
                time_str = item.get('比赛时间', '')
                times = time_str.split(' - ')
                comp_start = self._parse_ctftime(times[0]) if len(times) > 0 else ''
                comp_end = self._parse_ctftime(times[1]) if len(times) > 1 else ''

                if not comp_start or not comp_end:
                    continue

                record = {
                    'name': item.get('比赛名称', ''),
                    'source': self.SOURCE_NAME_GLOBAL,
                    'comp_start': comp_start,
                    'comp_end': comp_end,
                    'link': item.get('比赛链接', ''),
                    'organizer': item.get('赛事主办', ''),
                    'detail': '',
                    'mode': '线上',
                    'format': item.get('比赛形式', '未知'),
                    'type': 'CTF',
                }
                results.append(record)
            except Exception as e:
                logger.warning(f"Failed to process global item: {e}")
                continue

        logger.info(f"Hello-CTF Global: collected {len(results)} competitions")
        return results

    @staticmethod
    def _parse_time(s: str) -> str:
        """解析 '2026年07月10日 19:00' 格式为 ISO 8601"""
        import re
        m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?', s)
        if m:
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            t = m.group(4) or '00:00'
            return f"{y}-{mo}-{d}T{t}:00+08:00"
        return ''

    @staticmethod
    def _parse_ctftime(s: str) -> str:
        """解析 '2026-06-05 18:00:00 UTC+8' 为 ISO 8601"""
        s = s.strip()
        if 'UTC+8' in s:
            s = s.replace(' UTC+8', '+08:00')
        elif 'UTC' in s:
            s = s.replace(' UTC', 'Z')
        return s
