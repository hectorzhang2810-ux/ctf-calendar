import hashlib
import logging
import random
import time
from datetime import datetime, timezone

from app.config import Config
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

ICHUNQIU_BASE = "https://www.ichunqiu.com"
ICHUNQIU_AJAX_LIST = f"{ICHUNQIU_BASE}/competition/ajaxList"
ICHUNQIU_AJAX_CALENDAR = f"{ICHUNQIU_BASE}/competition/ajaxCalendarInfo"
ICHUNQIU_SECRET = Config.ICHUNQIU_SECRET


class IChunQiuScraper(BaseScraper):
    SOURCE_NAME = 'ichunqiu'

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Origin': ICHUNQIU_BASE,
            'Referer': f'{ICHUNQIU_BASE}/competition/all?source=1',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        })

    # ------------------------------------------------------------------
    # Signing (reverse-engineered from jQuery.ajax.js, 2026-05)
    #
    # Step 1: rs = MD5( (Date.now() + Math.random()) + "icq" )
    # Step 2: s = sorted({key=value for all POST params} + "rs="+rs)
    # Step 3: sign_str = s.join("&") + "&" + SECRET
    # Step 4: Callauth = SHA1(sign_str)
    # Step 5: Send via header "SIGN" (NOT "Callauth")
    # ------------------------------------------------------------------
    def _sign(self, params: dict) -> tuple[str, dict]:
        d = int(time.time() * 1000) + random.random()
        h = hashlib.md5(f'{d}icq'.encode()).hexdigest()

        pairs = [f'{k}={params[k]}' for k in params]
        pairs.append(f'rs={h}')
        pairs.sort()
        sign_str = '&'.join(pairs) + f'&{ICHUNQIU_SECRET}'
        signature = hashlib.sha1(sign_str.encode()).hexdigest()

        params_with_rs = dict(params)
        params_with_rs['rs'] = h
        return signature, params_with_rs

    def _api_post(self, url: str, params: dict) -> dict | None:
        self._rate_limit()
        signature, signed_params = self._sign(params)
        self.session.headers['SIGN'] = signature
        self.last_request_time = time.time()
        try:
            resp = self.session.post(url, data=signed_params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("iChunQiu API POST failed: %s %s — %s", url, params, e)
            return None

    # ------------------------------------------------------------------
    # Fetch pipeline
    # ------------------------------------------------------------------
    def fetch(self) -> list[dict]:
        seen_ids: set[str] = set()
        results: list[dict] = []

        # 1) Calendar API — newest competitions from the front-page calendar
        for c in self._fetch_calendar():
            if c['ID'] not in seen_ids:
                seen_ids.add(c['ID'])
                r = self._map_item(c)
                if r:
                    results.append(r)

        # 2) AjaxList API — historical archive, paginate backward
        for c in self._fetch_list():
            if c['ID'] not in seen_ids:
                seen_ids.add(c['ID'])
                r = self._map_item(c)
                if r:
                    results.append(r)

        logger.info("iChunQiu: collected %d competitions", len(results))
        return results

    # ------------------------------------------------------------------
    # Calendar endpoint (date=YYYY-MM)
    # ------------------------------------------------------------------
    def _fetch_calendar(self) -> list[dict]:
        all_comps: list[dict] = []
        # 2024-2025 data is already covered by _fetch_list with better pagination.
        # Only 2026 (the newest) needs the calendar endpoint.
        for year in ('2026',):
            for month in range(1, 13):
                date_val = f'{year}-{month:02d}'
                data = self._api_post(ICHUNQIU_AJAX_CALENDAR, {'date': date_val})
                if not data or data.get('status') != 1:
                    continue
                raw = data.get('data', [])
                if isinstance(raw, dict):
                    for day, items in raw.items():
                        if isinstance(items, list):
                            all_comps.extend(items)
                elif isinstance(raw, list):
                    all_comps.extend(raw)
        return all_comps

    # ------------------------------------------------------------------
    # List endpoint (ajaxList)
    # ------------------------------------------------------------------
    def _fetch_list(self) -> list[dict]:
        all_comps: list[dict] = []
        for page in range(1, 30):
            data = self._api_post(ICHUNQIU_AJAX_LIST, {
                'status': '',
                'key_word': '',
                'page_index': str(page),
                'page_size': '20',
                'order': 'desc',
            })
            if not data or data.get('status') != 1:
                break
            comps = data.get('data', {}).get('list', [])
            if not comps:
                break
            all_comps.extend(comps)
        return all_comps

    # ------------------------------------------------------------------
    # Item mapping
    # ------------------------------------------------------------------
    def _map_item(self, item: dict) -> dict | None:
        name = (item.get('Title') or '').strip()
        if not name:
            return None

        start_raw = item.get('StartTime') or ''
        end_raw = item.get('EndTime') or ''
        if not start_raw or not end_raw:
            return None

        try:
            start_dt = datetime.strptime(start_raw, '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(end_raw, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

        raw_type = item.get('Type') or ''
        comp_format = '线上'
        if '线下' in raw_type or '线下' in (item.get('Racing') or ''):
            comp_format = '线下'

        # Newer calendar records may have "Racing" field
        # "已结束/即将开始/进行中"
        comp_url = (item.get('Url') or '').strip()
        if comp_url and not comp_url.startswith('http'):
            comp_url = ''

        return {
            'name': name,
            'comp_start': start_dt.replace(tzinfo=timezone.utc).isoformat(),
            'comp_end': end_dt.replace(tzinfo=timezone.utc).isoformat(),
            'source': self.SOURCE_NAME,
            'type': 'CTF',
            'mode': comp_format,
            'link': comp_url,
            'organizer': (item.get('Host') or '').strip(),
            'detail': '',
        }
