import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BUGKU_GAME_URL = "https://ctf.bugku.com/game"
BUGKU_DETAIL_URL = "https://ctf.bugku.com/game/detail/id/{id}.html"


class BugKuScraper(BaseScraper):
    SOURCE_NAME = 'bugku'

    def fetch(self) -> list[dict]:
        html = self.request(BUGKU_GAME_URL)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        game_rows = self._find_game_rows(soup)
        if not game_rows:
            logger.warning("BugKu: no game rows found on listing page")
            return []

        results = []
        for row in game_rows:
            try:
                record = self._parse_row(row)
                if record:
                    results.append(record)
            except Exception as e:
                logger.warning(f"BugKu failed to parse row: {e}")
                continue

        logger.info(f"BugKu: collected {len(results)} competitions")
        return results

    def _find_game_rows(self, soup: BeautifulSoup) -> list:
        rows = soup.select('table tr')
        if rows and len(rows) > 1:
            return rows[1:]

        rows = soup.find_all('tr')
        if rows and len(rows) > 1:
            return rows[1:]

        return []

    def _parse_row(self, row) -> dict | None:
        cells = row.find_all('td')
        if len(cells) < 5:
            return None

        name_el = cells[1] if len(cells) > 1 else None
        type_el = cells[2] if len(cells) > 2 else None
        link_el = cells[3] if len(cells) > 3 else None
        schedule_el = cells[4] if len(cells) > 4 else None
        action_el = cells[5] if len(cells) > 5 else None

        name = name_el.get_text(strip=True) if name_el else ''
        if not name:
            img = name_el.find('img') if name_el else None
            name = img.get('alt', '') if img else ''

        comp_type = type_el.get_text(strip=True) if type_el else '线上'
        comp_format = '线上' if '线上' in comp_type else '线下'
        comp_link = ''
        if link_el:
            a = link_el.find('a')
            if a and a.get('href'):
                comp_link = a['href']

        schedule_text = schedule_el.get_text(strip=True) if schedule_el else ''
        comp_start = ''
        comp_end = ''
        start_m = re.search(r'开始[：:]\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?)', schedule_text)
        end_m = re.search(r'结束[：:]\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?)', schedule_text)
        if start_m:
            dt_str = start_m.group(1)
            if len(dt_str) == 16:
                dt_str += ':00'
            try:
                comp_start = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
        if end_m:
            dt_str = end_m.group(1)
            if len(dt_str) == 16:
                dt_str += ':00'
            try:
                comp_end = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

        if not comp_start or not comp_end:
            return None

        detail_url = ''
        if action_el:
            a = action_el.find('a')
            if a and a.get('href'):
                detail_url = 'https://ctf.bugku.com' + a['href']

        return {
            'name': name,
            'source': self.SOURCE_NAME,
            'comp_start': comp_start,
            'comp_end': comp_end,
            'link': comp_link,
            'organizer': '',
            'detail': detail_url,
            'mode': comp_format,
            'format': comp_format,
            'type': 'CTF',
        }
