import logging
import re
from datetime import datetime, timezone

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

CTFPLUS_API_URL = "https://www.ctfplus.cn/api/competition/getCompetitionPanelCompetitions"
CTFPLUS_STATUS_GROUPS = ["notStart", "registering", "running", "ended", "revisit"]


class CTFPlusScraper(BaseScraper):
    SOURCE_NAME = 'ctfplus'

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.ctfplus.cn/',
        })

    def fetch(self) -> list[dict]:
        results = []
        try:
            resp = self.session.post(
                CTFPLUS_API_URL,
                json={"types": [], "isExternal": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"CTFPlus API request failed: {e}")
            return []

        if data.get('code') != 200:
            logger.warning(f"CTFPlus unexpected code: {data.get('code')}")
            return []

        comp_data = data.get('data', {})
        if not comp_data:
            logger.warning("CTFPlus empty data")
            return []

        for group in CTFPLUS_STATUS_GROUPS:
            items = comp_data.get(group)
            if not items or not isinstance(items, list):
                continue
            for item in items:
                try:
                    record = self._map_item(item)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.warning(f"CTFPlus failed to process item {item.get('id')}: {e}")
                    continue

        logger.info(f"CTFPlus: collected {len(results)} competitions")
        return results

    def _map_item(self, item: dict) -> dict | None:
        comp_start_ts = item.get('startTime')
        comp_end_ts = item.get('endTime')
        if not comp_start_ts or not comp_end_ts:
            return None

        comp_start = datetime.fromtimestamp(comp_start_ts, tz=timezone.utc).isoformat()
        comp_end = datetime.fromtimestamp(comp_end_ts, tz=timezone.utc).isoformat()

        mode_val = item.get('mode', 0)
        mode = '团队赛' if mode_val == 1 else '个人赛' if mode_val == 0 else '未知'

        address = item.get('address', '') or ''
        comp_format = '线下' if address else '线上'

        description = item.get('description', '') or ''
        offical_url = ''
        organizer = ''
        if description:
            url_m = re.search(r'Offical URL:\s*<a[^>]*href=\"([^\"]+)\"', description)
            if url_m:
                offical_url = url_m.group(1)
            org_m = re.search(r'Event organizers:\s*\n\s*<a[^>]*>([^<]+)</a>', description)
            if org_m:
                organizer = org_m.group(1).strip()

        return {
            'name': item.get('name', ''),
            'source': self.SOURCE_NAME,
            'comp_start': comp_start,
            'comp_end': comp_end,
            'link': offical_url,
            'organizer': organizer,
            'detail': description[:500] if description else '',
            'mode': mode,
            'format': comp_format,
            'type': 'CTF',
        }
