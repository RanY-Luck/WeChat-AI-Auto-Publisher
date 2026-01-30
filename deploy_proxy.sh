#!/bin/bash

###############################################
# 微信公众号API代理服务一键部署脚本
# 用途: 解决NAS动态IP导致的白名单问题
# 使用: bash deploy_proxy.sh
###############################################

set -e

echo "=========================================="
echo "  微信公众号API代理服务部署工具"
echo "=========================================="
echo ""

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "❌ 无法检测操作系统"
    exit 1
fi

echo "✅ 检测到操作系统: $OS"
echo ""

# 选择部署方式
echo "请选择部署方式:"
echo "1) Docker部署 (推荐,最简单)"
echo "2) Squid代理 (传统方式)"
echo "3) Tinyproxy (轻量级)"
read -p "请输入选项 [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "========== Docker部署 =========="

        # 检查Docker是否安装
        if ! command -v docker &> /dev/null; then
            echo "Docker未安装,正在安装..."
            curl -fsSL https://get.docker.com | bash
            systemctl start docker
            systemctl enable docker
        fi

        echo "✅ Docker已就绪"

        # 停止并删除旧容器
        docker rm -f squid-proxy 2>/dev/null || true

        # 启动代理容器
        echo "正在启动代理服务..."
        docker run -d \
          --name squid-proxy \
          --restart always \
          -p 8080:3128 \
          ubuntu/squid:latest

        echo "✅ 代理服务已启动"
        PROXY_PORT=8080
        ;;

    2)
        echo ""
        echo "========== Squid部署 =========="

        # 安装Squid
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            apt update
            apt install squid -y
        elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
            yum install squid -y
        else
            echo "❌ 不支持的操作系统"
            exit 1
        fi

        # 配置Squid
        cat > /etc/squid/squid.conf << 'EOF'
# 监听端口
http_port 8080

# 允许所有IP访问
http_access allow all

# 禁用缓存
cache deny all

# 日志
access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

        # 启动Squid
        systemctl restart squid
        systemctl enable squid

        echo "✅ Squid已配置并启动"
        PROXY_PORT=8080
        ;;

    3)
        echo ""
        echo "========== Tinyproxy部署 =========="

        # 安装Tinyproxy
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            apt update
            apt install tinyproxy -y
        elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
            yum install tinyproxy -y
        else
            echo "❌ 不支持的操作系统"
            exit 1
        fi

        # 配置允许所有IP访问
        sed -i 's/^Allow 127.0.0.1/#Allow 127.0.0.1/' /etc/tinyproxy/tinyproxy.conf
        echo "Allow 0.0.0.0/0" >> /etc/tinyproxy/tinyproxy.conf

        # 启动Tinyproxy
        systemctl restart tinyproxy
        systemctl enable tinyproxy

        echo "✅ Tinyproxy已配置并启动"
        PROXY_PORT=8888
        ;;

    *)
        echo "❌ 无效的选项"
        exit 1
        ;;
esac

# 开放防火墙端口
echo ""
echo "正在配置防火墙..."

if command -v ufw &> /dev/null; then
    ufw allow $PROXY_PORT/tcp
    echo "✅ UFW防火墙已配置"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --add-port=$PROXY_PORT/tcp --permanent
    firewall-cmd --reload
    echo "✅ Firewalld防火墙已配置"
else
    echo "⚠️  未检测到防火墙,请手动开放端口 $PROXY_PORT"
fi

# 获取公网IP
PUBLIC_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip)

# 测试代理
echo ""
echo "正在测试代理..."
sleep 2

TEST_RESULT=$(curl -s -x http://127.0.0.1:$PROXY_PORT http://httpbin.org/ip 2>&1 || echo "failed")

if echo "$TEST_RESULT" | grep -q "origin"; then
    echo "✅ 代理测试成功!"
else
    echo "⚠️  代理测试失败,请检查日志"
fi

# 输出配置信息
echo ""
echo "=========================================="
echo "  🎉 部署完成!"
echo "=========================================="
echo ""
echo "代理服务器信息:"
echo "  公网IP: $PUBLIC_IP"
echo "  代理端口: $PROXY_PORT"
echo "  代理地址: http://$PUBLIC_IP:$PROXY_PORT"
echo ""
echo "下一步操作:"
echo ""
echo "1️⃣  将以下IP添加到微信公众平台白名单:"
echo "    登录 https://mp.weixin.qq.com"
echo "    进入: 开发 -> 基本配置 -> IP白名单"
echo "    添加IP: $PUBLIC_IP"
echo ""
echo "2️⃣  在您的NAS项目中修改 config/config.py:"
echo '    WECHAT_CONFIG = {'
echo '        "app_id": "wxXXXXXX",'
echo '        "app_secret": "XXXXXXXX",'
echo "        \"proxy_url\": \"http://$PUBLIC_IP:$PROXY_PORT\""
echo '    }'
echo ""
echo "3️⃣  重启NAS上的Docker容器:"
echo "    docker restart wechat-ai-publisher"
echo ""
echo "=========================================="
echo ""

# 保存配置信息到文件
cat > ~/wechat_proxy_info.txt << EOF
微信公众号代理配置信息
==========================================

部署时间: $(date)
公网IP: $PUBLIC_IP
代理端口: $PROXY_PORT
代理地址: http://$PUBLIC_IP:$PROXY_PORT

配置代码:
WECHAT_CONFIG = {
    "app_id": "wxXXXXXX",
    "app_secret": "XXXXXXXX",
    "proxy_url": "http://$PUBLIC_IP:$PROXY_PORT"
}

服务管理命令:
- 查看状态: systemctl status squid (或tinyproxy)
- 重启服务: systemctl restart squid (或tinyproxy)
- 查看日志: tail -f /var/log/squid/access.log

测试代理:
curl -x http://$PUBLIC_IP:$PROXY_PORT http://httpbin.org/ip
EOF

echo "📝 配置信息已保存到: ~/wechat_proxy_info.txt"
echo ""