#!/usr/bin/env bash
set -euo pipefail

# CTF Calendar 一键部署脚本（开发模式）
# 无需 root、无需域名、无需 Nginx
# 用法: chmod +x deploy-local.sh && ./deploy-local.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " CTF Calendar — 一键部署（开发模式）"
echo "========================================"
echo ""

# 1. Python 虚拟环境
echo "==> 1/5 创建 Python 虚拟环境"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 2. 安装依赖
echo "==> 2/5 安装依赖"
pip install -r requirements.txt -q

# 3. 初始化数据库
echo "==> 3/5 初始化数据库"
FLASK_APP=app flask init-db 2>/dev/null || true

# 4. 检查 SECRET_KEY
echo "==> 4/5 检查配置"
if [ -z "${SECRET_KEY:-}" ]; then
    # 生成持久化 key（写入 .env）
    if [ ! -f ".env" ]; then
        KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
        echo "SECRET_KEY=$KEY" > .env
        echo "   .env 已生成（SECRET_KEY 已持久化，重启 session 不会丢失）"
    else
        echo "   .env 已存在，跳过"
    fi
    export $(grep -v '^#' .env | xargs)
fi

# 5. 启动
echo ""
echo "==> 5/5 启动服务"
echo ""
echo "  访问地址: http://localhost:5000"
echo "  首次访问 /admin 将进入初始化页面创建管理员账号"
echo "  按 Ctrl+C 停止"
echo ""

FLASK_APP=app flask run --host=0.0.0.0 --port=5000
