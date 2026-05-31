import json
import logging
from datetime import datetime, timezone

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

NSSCTF_MODE_MAP = {
    0: '个人赛',
    1: '团队赛',
    20: '团队赛',
}

NSSCTF_API_URL = "https://www.nssctf.cn/api/contest/list/{page}/"
NSSCTF_CONTEST_URL = "https://www.nssctf.cn/contest/{id}/"


class NSSCTFScraper(BaseScraper):
    SOURCE_NAME = 'nssctf'

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.nssctf.cn/',
        })

    NSSCTF_MAX_PAGES = 15

    def fetch(self) -> list[dict]:
        results = []
        page = 1

        while page <= self.NSSCTF_MAX_PAGES:
            records = self._fetch_page(page)
            if not records:
                break
            results.extend(records)
            logger.info(f"NSSCTF page {page}: {len(records)} contests")
            page += 1

        logger.info(f"NSSCTF total: collected {len(results)} competitions")
        return results

    def _fetch_page(self, page: int) -> list[dict]:
        url = NSSCTF_API_URL.format(page=page)

        # Rate limit between pages to avoid 429
        self._rate_limit()
        try:
            resp = self.session.post(url, json={}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"NSSCTF page {page} request failed: {e}")
            return []

        if data.get('code') != 200:
            logger.warning(f"NSSCTF page {page} unexpected code: {data.get('code')}")
            return []

        contests = data.get('data', {}).get('contests', [])
        if not contests:
            return []

        results = []
        for item in contests:
            try:
                record = self._map_item(item)
                if record:
                    results.append(record)
            except Exception as e:
                logger.warning(f"NSSCTF failed to process item {item.get('id')}: {e}")
                continue

        return results

    def _map_item(self, item: dict) -> dict | None:
        comp_start_ts = item.get('start_date')
        comp_end_ts = item.get('ends_date')
        if not comp_start_ts or not comp_end_ts:
            return None

        comp_start = datetime.fromtimestamp(
            comp_start_ts / 1000, tz=timezone.utc
        ).isoformat()
        comp_end = datetime.fromtimestamp(
            comp_end_ts / 1000, tz=timezone.utc
        ).isoformat()

        title = item.get('title', '').strip()
        if not title:
            return None

        contest_id = item.get('id')
        mode_value = item.get('mode', 0)

        return {
            'name': title,
            'source': self.SOURCE_NAME,
            'comp_start': comp_start,
            'comp_end': comp_end,
            'link': NSSCTF_CONTEST_URL.format(id=contest_id),
            'organizer': '',
            'detail': item.get('desc', ''),
            'mode': NSSCTF_MODE_MAP.get(mode_value, '线上'),
            'format': '未知',
            'type': 'CTF',
        }
