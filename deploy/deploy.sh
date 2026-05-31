#!/usr/bin/env bash
set -euo pipefail

# CTF Calendar 部署脚本
# 用法: sudo ./deploy.sh /opt/ctf-calendar your-domain.com
#
# 前置条件：
#   - 域名已解析到本服务器
#   - 端口 80/443 已开放
#   - 已安装 python3, nginx, certbot

APP_DIR="${1:-/opt/ctf-calendar}"
DOMAIN="${2:-ctf-calendar.example.com}"
LOGDIR="/var/log/ctf-calendar"

echo "========================================"
echo " CTF Calendar 部署"
echo " 目标目录: $APP_DIR"
echo " 域名:     $DOMAIN"
echo "========================================"

# ------------------------------------------------------------------
# 1. 拷贝应用文件
# ------------------------------------------------------------------
echo ""
echo "==> 1/7 拷贝应用文件到 $APP_DIR"
mkdir -p "$APP_DIR"
cp -r ../app ../requirements.txt ../Makefile ../.gitignore "$APP_DIR/"
cp -r ../scripts "$APP_DIR/" 2>/dev/null || true

# ------------------------------------------------------------------
# 2. 配置环境变量（交互式）
# ------------------------------------------------------------------
echo ""
echo "==> 2/7 配置安全凭据"
read -s -p "  输入 SECRET_KEY（留空自动生成）: " SECRET_KEY_INPUT
echo ""
SECRET_KEY="${SECRET_KEY_INPUT:-$(python3 -c "import os; print(os.urandom(32).hex())")}"

read -p "  输入 ADMIN_USERNAME（默认 admin）: " ADMIN_USERNAME_INPUT
ADMIN_USERNAME="${ADMIN_USERNAME_INPUT:-admin}"

read -s -p "  输入 ADMIN_PASSWORD: " ADMIN_PASSWORD_INPUT
echo ""
while [ -z "$ADMIN_PASSWORD_INPUT" ]; do
    read -s -p "  密码不能为空，请重新输入: " ADMIN_PASSWORD_INPUT
    echo ""
done
ADMIN_PASSWORD="$ADMIN_PASSWORD_INPUT"

# 写入 service 文件的 Environment 行
cat > /tmp/ctf-calendar-env <<ENVEOF
# 安全配置（部署时自动生成，请勿提交到版本控制）
Environment=SECRET_KEY=$SECRET_KEY
Environment=ADMIN_USERNAME=$ADMIN_USERNAME
Environment=ADMIN_PASSWORD=$ADMIN_PASSWORD
ENVEOF

# ------------------------------------------------------------------
# 3. Python 虚拟环境
# ------------------------------------------------------------------
echo ""
echo "==> 3/7 设置 Python 虚拟环境"
python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
pip install -r "$APP_DIR/requirements.txt" -q

# ------------------------------------------------------------------
# 4. 初始化数据库
# ------------------------------------------------------------------
echo ""
echo "==> 4/7 初始化数据库"
FLASK_APP=app "$APP_DIR/venv/bin/flask" init-db

# ------------------------------------------------------------------
# 5. 安装 systemd 服务
# ------------------------------------------------------------------
echo ""
echo "==> 5/7 安装 systemd 服务"
cp nginx.conf /etc/nginx/sites-available/ctf-calendar
sed -i "s/ctf-calendar\.example\.com/$DOMAIN/g" /etc/nginx/sites-available/ctf-calendar

# 写入安全凭据到 systemd service 文件
cp ctf-calendar.service /etc/systemd/system/
# 在 ExecStart 前插入 Environment 行
sed -i '/^ExecStart=/i Environment=SECRET_KEY='"$SECRET_KEY" /etc/systemd/system/ctf-calendar.service
sed -i '/^ExecStart=/i Environment=ADMIN_USERNAME='"$ADMIN_USERNAME" /etc/systemd/system/ctf-calendar.service
sed -i '/^ExecStart=/i Environment=ADMIN_PASSWORD='"$ADMIN_PASSWORD" /etc/systemd/system/ctf-calendar.service

systemctl daemon-reload
systemctl enable ctf-calendar
systemctl start ctf-calendar

# ------------------------------------------------------------------
# 6. 配置 Nginx + HTTPS（Let's Encrypt）
# ------------------------------------------------------------------
echo ""
echo "==> 6/7 配置 Nginx 和 HTTPS"

# 先启动 HTTP 用于 certbot 验证
cp nginx.conf "/etc/nginx/sites-available/ctf-calendar"
sed -i "s/ctf-calendar\.example\.com/$DOMAIN/g" /etc/nginx/sites-available/ctf-calendar
ln -sf /etc/nginx/sites-available/ctf-calendar /etc/nginx/sites-enabled/

# 临时只启用 HTTP（注释掉 HTTPS server block）获取证书
sed -i '/listen 443/,/^}/s/^/#/' /etc/nginx/sites-available/ctf-calendar
sed -i 's/#    listen 80;/listen 80;/' /etc/nginx/sites-available/ctf-calendar
sed -i 's/#    return 301/    return 301/' /etc/nginx/sites-available/ctf-calendar
sed -i 's/#server {$/server {/' /etc/nginx/sites-available/ctf-calendar
nginx -t && systemctl reload nginx

# 获取 Let's Encrypt 证书
echo "   正在获取 SSL 证书（确保域名已解析到本机）..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || {
    echo "   [WARN] certbot 失败，可稍后手动运行: certbot --nginx -d $DOMAIN"
    echo "   当前 nginx 仅监听 HTTP。"
}

# 恢复完整 HTTPS 配置
cp nginx.conf "/etc/nginx/sites-available/ctf-calendar"
sed -i "s/ctf-calendar\.example\.com/$DOMAIN/g" /etc/nginx/sites-available/ctf-calendar
nginx -t && systemctl reload nginx

# ------------------------------------------------------------------
# 7. 安装 cron 任务 & 首次采集
# ------------------------------------------------------------------
echo ""
echo "==> 7/7 安装定时任务并执行首次采集"
cp ctf-calendar.cron /etc/cron.d/ctf-calendar

cd "$APP_DIR" && FLASK_APP=app "$APP_DIR/venv/bin/flask" fetch

# ------------------------------------------------------------------
echo ""
echo "========================================"
echo " 部署完成！"
echo " 访问: https://$DOMAIN"
echo " 管理后台: https://$DOMAIN/admin"
echo "========================================"
echo ""
echo "后续维护:"
echo "  - 查看日志: journalctl -u ctf-calendar -f"
echo "  - 手动采集: cd $APP_DIR && flask fetch"
echo "  - 证书续期: certbot renew（已自动）"
systemctl status ctf-calendar --no-pager
