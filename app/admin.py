import csv
import io
import os
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, Response, session,
)
from app.database import (
    get_competitions,
    get_competition_by_id,
    upsert_competition,
    delete_competition,
    get_stats,
    get_stats_by_source,
    get_recent_competitions,
    admin_user_count,
)

bp = Blueprint('admin', __name__, url_prefix='/admin')

SOURCE_DISPLAY = {
    'hello-ctf-cn': 'Hello-CTF CN',
    'hello-ctf-global': 'Hello-CTF Global',
    'nssctf': 'NSSCTF',
    'bugku': 'BugKu',
    'ctfplus': 'CTFPlus',
    'ichunqiu': 'i春秋',
    'henan_edu': '河南教育厅',
    'anhui_edu': '安徽教育厅',
    'jiangsu_edu': '江苏教育厅',
    'guangdong_edu': '广东教育厅',
    'shandong_edu': '山东教育厅',
    'zhejiang_edu': '浙江教育厅',
    'beijing_edu': '北京教委',
    'manual': '手动录入',
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def _ensure_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = os.urandom(16).hex()
    return session['_csrf_token']


def require_csrf(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE'):
            token = request.form.get('_csrf_token', '')
            expected = session.get('_csrf_token', '')
            if not expected or token != expected:
                flash('Invalid or missing CSRF token', 'error')
                return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


def _redirect_if_no_admin():
    """If no admin user exists yet, redirect to setup."""
    if admin_user_count() == 0:
        return redirect(url_for('auth.setup'))
    return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@bp.route('/')
@login_required
def dashboard():
    redirect_to = _redirect_if_no_admin()
    if redirect_to:
        return redirect_to

    stats = get_stats()
    source_stats = get_stats_by_source()
    recent = get_recent_competitions(10)
    competitions, total = get_competitions(limit=50, offset=0)

    return render_template(
        'admin.html',
        competitions=competitions,
        total=total,
        page=1,
        total_pages=max(1, (total + 50 - 1) // 50),
        stats=stats,
        source_stats=source_stats,
        recent=recent,
        csrf_token=_ensure_csrf_token(),
        source_display=SOURCE_DISPLAY,
    )


# ---------------------------------------------------------------------------
# Competition list (with search / filter / pagination)
# ---------------------------------------------------------------------------
@bp.route('/list')
@login_required
def competition_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 10), 200)
    status = request.args.get('status')
    source = request.args.get('source')
    q = request.args.get('q', '').strip()

    competitions, total = get_competitions(
        status=status,
        source=source,
        search=q,
        offset=(page - 1) * per_page,
        limit=per_page,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    sources = sorted(SOURCE_DISPLAY.keys())

    return render_template(
        'admin_list.html',
        competitions=competitions,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total=total,
        q=q,
        active_status=status,
        active_source=source,
        csrf_token=_ensure_csrf_token(),
        source_display=SOURCE_DISPLAY,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Add / Edit
# ---------------------------------------------------------------------------
@bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_csrf
def add():
    if request.method == 'POST':
        data = _collect_form_data(request)
        if not data['name']:
            flash('比赛名称不能为空', 'error')
            return render_template(
                'admin_form.html', comp=data, editing=False,
                csrf_token=_ensure_csrf_token(), source_display=SOURCE_DISPLAY,
            )
        upsert_competition(data)
        flash('比赛已添加', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template(
        'admin_form.html', comp={}, editing=False,
        csrf_token=_ensure_csrf_token(), source_display=SOURCE_DISPLAY,
    )


@bp.route('/edit/<comp_id>', methods=['GET', 'POST'])
@login_required
@require_csrf
def edit(comp_id):
    comp = get_competition_by_id(comp_id)
    if not comp:
        flash('未找到该比赛', 'error')
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        data = _collect_form_data(request, existing=comp)
        upsert_competition(data)
        flash('比赛已更新', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template(
        'admin_form.html', comp=comp, editing=True,
        csrf_token=_ensure_csrf_token(), source_display=SOURCE_DISPLAY,
    )


def _collect_form_data(req, existing=None):
    """Collect form data into a competition dict."""
    base = dict(existing) if existing else {}
    base.update({
        'name': req.form['name'],
        'source': req.form.get('source', base.get('source', 'manual')),
        'link': req.form.get('link', ''),
        'organizer': req.form.get('organizer', ''),
        'comp_start': req.form.get('comp_start', ''),
        'comp_end': req.form.get('comp_end', ''),
        'reg_start': req.form.get('reg_start', ''),
        'reg_end': req.form.get('reg_end', ''),
        'mode': req.form.get('mode', '线上'),
        'format': req.form.get('format', '未知'),
        'type': req.form.get('type', 'CTF'),
        'detail': req.form.get('detail', ''),
        'is_manual': 1,
    })
    return base


@bp.route('/delete/<comp_id>', methods=['POST'])
@login_required
@require_csrf
def delete(comp_id):
    ok = delete_competition(comp_id)
    if ok:
        flash('比赛已删除', 'success')
    else:
        flash('删除失败', 'error')
    return redirect(url_for('admin.dashboard'))


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------
@bp.route('/export/csv')
@login_required
def export_csv():
    competitions, _ = get_competitions(limit=99999, offset=0)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['名称', '来源', '类型', '形式', '参赛方式',
                     '开始时间', '结束时间', '报名开始', '报名截止',
                     '主办单位', '链接', '状态', '备注'])
    for c in competitions:
        writer.writerow([
            c.get('name', ''),
            c.get('source', ''),
            c.get('type', ''),
            c.get('format', ''),
            c.get('mode', ''),
            c.get('comp_start', ''),
            c.get('comp_end', ''),
            c.get('reg_start', ''),
            c.get('reg_end', ''),
            c.get('organizer', ''),
            c.get('link', ''),
            c.get('status', ''),
            c.get('detail', ''),
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=ctf-calendar-export.csv'
        },
    )
