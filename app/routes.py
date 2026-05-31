from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request

from app.database import get_competitions, get_competition_by_id, get_stats
from app.admin import SOURCE_DISPLAY

bp = Blueprint('routes', __name__)


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 10), 200)  # clamp 10-200
    status = request.args.get('status')
    source = request.args.get('source')
    comp_type = request.args.get('type')
    q = request.args.get('q', '').strip()

    competitions, total = get_competitions(
        status=status,
        source=source,
        type_filter=comp_type,
        search=q,
        offset=(page - 1) * per_page,
        limit=per_page,
    )
    stats = get_stats()

    now = datetime.now(timezone.utc)

    month_competitions, _ = get_competitions(limit=100, offset=0)
    month_competitions = [
        c for c in month_competitions
        if c.get('comp_start', '')[:7] == now.strftime('%Y-%m')
    ]

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'index.html',
        competitions=competitions,
        stats=stats,
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=per_page,
        q=q,
        active_status=status,
        active_source=source,
        active_type=comp_type,
        month_competitions=month_competitions,
        now=now,
        source_display=SOURCE_DISPLAY,
    )


@bp.route('/competition/<comp_id>')
def detail(comp_id):
    comp = get_competition_by_id(comp_id)
    if not comp:
        return 'Not Found', 404
    return render_template('detail.html', comp=comp)
