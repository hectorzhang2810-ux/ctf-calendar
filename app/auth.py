from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)
from app.database import (
    verify_admin, update_admin_password,
    admin_user_count, create_admin_user,
)

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if admin_user_count() == 0:
        return redirect(url_for('auth.setup'))

    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('请输入用户名和密码', 'error')
        elif verify_admin(username, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session.permanent = True
            flash('登录成功', 'success')
            next_url = request.args.get('next') or url_for('admin.dashboard')
            return redirect(next_url)
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('已退出登录', 'success')
    return redirect(url_for('routes.index'))


@bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login', next=url_for('auth.change_password')))

    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        username = session['admin_username']

        if not verify_admin(username, old_pw):
            flash('当前密码错误', 'error')
        elif len(new_pw) < 6:
            flash('新密码至少 6 位', 'error')
        elif new_pw != confirm_pw:
            flash('两次密码输入不一致', 'error')
        else:
            update_admin_password(username, new_pw)
            flash('密码已修改', 'success')
            return redirect(url_for('admin.dashboard'))

    return render_template('change_password.html')


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if admin_user_count() > 0:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_pw = request.form.get('confirm_password', '')

        errors = []
        if not username:
            errors.append('请输入用户名')
        if len(password) < 6:
            errors.append('密码至少 6 位')
        elif password != confirm_pw:
            errors.append('两次密码输入不一致')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            create_admin_user(username, password)
            flash('管理员账号创建成功，请登录', 'success')
            return redirect(url_for('auth.login'))

    return render_template('setup.html')
