#!/bin/bash
# 教育答疑 RAG 灰度回滚脚本
# 用法: ./rollback.sh [canary|stable|full]

set -euo pipefail

ACTION="${1:-full}"
NGINX_CONF_DIR="/etc/nginx/conf.d"
CONF_FILE="${NGINX_CONF_DIR}/insight-engine-canary.conf"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

rollback_canary() {
    log "开始回滚灰度版本（100% 流量切回稳定版本）"

    # 将 canary 权重设为 0
    sed -i 's/server 127.0.0.1:8002 weight=10/server 127.0.0.1:8002 weight=0/' "$CONF_FILE"
    sed -i 's/10%  insight_engine_canary/0%   insight_engine_canary/' "$CONF_FILE"

    # 测试配置并重载
    nginx -t && nginx -s reload
    log "Nginx 已重载，灰度版本流量已切回 0%"

    # 停止灰度容器
    if docker ps --format '{{.Names}}' | grep -q 'insight-engine-api-canary'; then
        docker stop insight-engine-api-canary
        log "灰度容器 insight-engine-api-canary 已停止"
    fi

    log "回滚完成"
}

rollback_full() {
    log "开始全量回滚到上一个稳定版本"

    # 拉取上一个稳定版本镜像
    PREV_TAG=$(docker images --format '{{.Tag}}' ghcr.io/org/insight-engine --filter "dangling=false" | grep -v latest | sort -r | head -1)
    log "上一个稳定版本: ${PREV_TAG}"

    # 停止当前容器
    docker stop insight-engine-api || true
    docker rm insight-engine-api || true

    # 启动上一个稳定版本
    docker run -d \
        --name insight-engine-api \
        --env-file .env.production \
        -p 8001:8000 \
        --network insight-engine-net \
        --restart unless-stopped \
        "ghcr.io/org/insight-engine:${PREV_TAG}"

    # 等待健康检查通过
    log "等待健康检查..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8001/health | grep -q "healthy"; then
            log "健康检查通过"
            break
        fi
        sleep 2
    done

    nginx -t && nginx -s reload
    log "全量回滚完成"
}

case "$ACTION" in
    canary)
        rollback_canary
        ;;
    stable)
        rollback_full
        ;;
    full)
        rollback_canary
        rollback_full
        ;;
    *)
        echo "用法: $0 [canary|stable|full]"
        echo "  canary: 仅切回灰度流量"
        echo "  stable: 回滚到上一个稳定镜像"
        echo "  full:   先切回灰度流量，再回滚镜像"
        exit 1
        ;;
esac