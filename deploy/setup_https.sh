#!/usr/bin/env bash
set -euo pipefail

DOMAIN="paper.dongli.icu"
EMAIL="${1:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGINX_SOURCE="$PROJECT_ROOT/deploy/nginx/$DOMAIN.conf"
NGINX_TARGET="/etc/nginx/sites-available/$DOMAIN.conf"

if [[ -z "$EMAIL" ]]; then
    echo "用法: sudo bash deploy/setup_https.sh 你的邮箱"
    exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx

cp "$NGINX_SOURCE" "$NGINX_TARGET"
ln -sfn "$NGINX_TARGET" "/etc/nginx/sites-enabled/$DOMAIN.conf"

nginx -t
systemctl enable nginx
systemctl restart nginx

certbot --nginx \
    --domain "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --redirect \
    --non-interactive

nginx -t
systemctl reload nginx
systemctl enable --now certbot.timer

echo "HTTPS 配置完成: https://$DOMAIN"
