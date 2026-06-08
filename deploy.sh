#!/bin/bash
# =============================================
# Скрипт быстрого развёртывания VPN Subscription System
# Использование: bash deploy.sh
# =============================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  VPN Subscription System - Deploy Script${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# === Проверка прав ===
if [[ $EUID -ne 0 ]]; then
   echo -e "${YELLOW}⚠️  Рекомендуется запускать с sudo для установки Docker${NC}"
fi

# === Функции ===

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ $1 не найден. Установите $1 и попробуйте снова.${NC}"
        return 1
    fi
    return 0
}

install_docker() {
    echo -e "${YELLOW}📦 Установка Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker установлен${NC}"
}

install_docker_compose() {
    echo -e "${YELLOW}📦 Установка Docker Compose...${NC}"
    pip3 install docker-compose
    echo -e "${GREEN}✅ Docker Compose установлен${NC}"
}

setup_nginx() {
    echo -e "${YELLOW}🔧 Настройка Nginx Reverse Proxy...${NC}"
    
    # Проверяем конфиг Nginx
    if [ -f "nginx.conf" ]; then
        sudo cp nginx.conf /etc/nginx/sites-available/vpn-api
        sudo ln -sf /etc/nginx/sites-available/vpn-api /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx
        echo -e "${GREEN}✅ Nginx настроен${NC}"
    else
        echo -e "${YELLOW}⚠️  nginx.conf не найден, создаю базовый...${NC}"
        
        # Читаем домен из .env
        DOMAIN=$(grep API_BASE_URL .env | cut -d '=' -f2 | sed 's|https://||' | sed 's|/||')
        if [ -z "$DOMAIN" ]; then
            DOMAIN="api.maximikvpn.fun"
        fi
        
        cat > /tmp/nginx-vpn.conf << EOF
server {
    listen 80;
    server_name ${DOMAIN} ${DOMAIN#api.};
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
        sudo cp /tmp/nginx-vpn.conf /etc/nginx/sites-available/vpn-api
        sudo ln -sf /etc/nginx/sites-available/vpn-api /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx
        echo -e "${GREEN}✅ Базовый Nginx конфиг создан${NC}"
        echo -e "${YELLOW}⚠️  Далее настройте Certbot: sudo certbot --nginx -d ${DOMAIN}${NC}"
    fi
}

setup_ssl() {
    echo -e "${YELLOW}🔐 Настройка SSL через Certbot...${NC}"
    
    if ! check_command certbot; then
        echo -e "${YELLOW}📦 Установка Certbot...${NC}"
        sudo apt-get update
        sudo apt-get install -y certbot python3-certbot-nginx
    fi
    
    DOMAIN=$(grep API_BASE_URL .env | cut -d '=' -f2 | sed 's|https://||' | sed 's|/||')
    if [ -z "$DOMAIN" ]; then
        DOMAIN="api.maximikvpn.fun"
    fi
    
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN#api.}" || {
        echo -e "${YELLOW}⚠️  Certbot не удалось выполнить. Запустите вручную:${NC}"
        echo -e "   sudo certbot --nginx -d ${DOMAIN}"
    }
}

# === Главное меню ===

echo -e "${BLUE}Выберите способ развёртывания:${NC}"
echo -e "1) ${GREEN}🚀 Полное развёртывание (Docker + Nginx + SSL)${NC}"
echo -e "2) ${GREEN}🐳 Только Docker (без Nginx/SSL)${NC}"
echo -e "3) ${GREEN}📦 Только установка зависимостей (pip)${NC}"
echo -e "4) ${RED}❌ Выход${NC}"
echo ""
read -rp "Ваш выбор [1-4]: " choice

case $choice in
    1)
        echo -e "${BLUE}🚀 Полное развёртывание...${NC}"
        
        # Проверка/установка Docker
        if ! check_command docker; then
            install_docker
        else
            echo -e "${GREEN}✅ Docker уже установлен${NC}"
        fi
        
        # Проверка/установка Docker Compose
        if ! check_command docker-compose; then
            install_docker_compose
        else
            echo -e "${GREEN}✅ Docker Compose уже установлен${NC}"
        fi
        
        # Проверка .env
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}⚠️  .env не найден! Создаю из .env.example...${NC}"
            cp .env.example .env
            echo -e "${RED}❌ Отредактируйте .env файл и запустите скрипт снова!${NC}"
            exit 1
        fi
        
        # Создаём директории
        mkdir -p data media
        
        # Запускаем Docker Compose
        echo -e "${YELLOW}🐳 Запуск Docker Compose...${NC}"
        docker-compose up -d --build
        
        # Настройка Nginx
        if check_command nginx; then
            setup_nginx
            setup_ssl
        else
            echo -e "${YELLOW}📦 Установка Nginx...${NC}"
            sudo apt-get update
            sudo apt-get install -y nginx
            setup_nginx
            setup_ssl
        fi
        
        echo -e "${GREEN}============================================${NC}"
        echo -e "${GREEN}  ✅ Развёртывание завершено!${NC}"
        echo -e "${GREEN}============================================${NC}"
        echo -e "📡 API: ${BLUE}http://localhost:8000${NC}"
        echo -e "🤖 Bot: ${BLUE}Запущен в контейнере vpn-bot${NC}"
        echo -e ""
        echo -e "Полезные команды:"
        echo -e "  ${YELLOW}docker-compose logs -f api${NC}  — логи API"
        echo -e "  ${YELLOW}docker-compose logs -f bot${NC}  — логи бота"
        echo -e "  ${YELLOW}docker-compose restart${NC}      — перезапуск"
        echo -e "  ${YELLOW}docker-compose down${NC}         — остановка"
        ;;
        
    2)
        echo -e "${BLUE}🐳 Docker развёртывание...${NC}"
        
        # Проверка/установка Docker
        if ! check_command docker; then
            install_docker
        fi
        
        if ! check_command docker-compose; then
            install_docker_compose
        fi
        
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}⚠️  .env не найден! Создаю из .env.example...${NC}"
            cp .env.example .env
            echo -e "${RED}❌ Отредактируйте .env файл и запустите скрипт снова!${NC}"
            exit 1
        fi
        
        mkdir -p data media
        docker-compose up -d --build
        
        echo -e "${GREEN}✅ Docker контейнеры запущены!${NC}"
        echo -e "📡 API: http://localhost:8000"
        echo -e "🤖 Bot запущен в контейнере"
        ;;
        
    3)
        echo -e "${BLUE}📦 Установка зависимостей через pip...${NC}"
        
        if [ ! -f ".env" ]; then
            cp .env.example .env
            echo -e "${YELLOW}⚠️  Создан .env из .env.example. Отредактируйте его!${NC}"
        fi
        
        # Создаём виртуальное окружение
        python3 -m venv venv
        source venv/bin/activate
        
        pip install --upgrade pip
        pip install -r requirements.txt
        
        echo -e "${GREEN}✅ Зависимости установлены!${NC}"
        echo -e ""
        echo -e "Запуск компонентов:"
        echo -e "  ${YELLOW}source venv/bin/activate${NC}"
        echo -e "  ${YELLOW}uvicorn backend.main:app --host 0.0.0.0 --port 8000${NC}  — API"
        echo -e "  ${YELLOW}python bot/main.py${NC}  — Telegram бот"
        ;;
        
    4)
        echo -e "${BLUE}👋 Выход...${NC}"
        exit 0
        ;;
        
    *)
        echo -e "${RED}❌ Неверный выбор!${NC}"
        exit 1
        ;;
esac