#!/usr/bin/env bash
# 从开发机(git bash)把话本部署/更新到 13:打包代码 → 传到 /opt/huaben → 构建并启动 → 探活。
#
# 只替换代码(huaben/ web/ scripts/ 与构建文件);服务器上的 data/(数据库+音频)与 .env(密钥)从不碰。
# 代码目录先删再解包:仓库里删掉的模块不会残留在服务器上被误导入。
# 首次部署:.env 不存在时从模板生成并照常启动(没密钥也能起),提示填密钥——密钥只由用户自己写进服务器,不经过这里。
set -euo pipefail
HOST=${HUABEN_DEPLOY_HOST:-root@10.1.1.13}
DIR=/opt/huaben
cd "$(dirname "$0")/.."

# --owner/--no-same-owner:开发机(Windows)上的用户号在服务器上不存在,保留属主会让解包报错退出(首次部署实测)
tar czf - --owner=0 --group=0 --exclude='__pycache__' --exclude='*.pyc' \
    Dockerfile docker-compose.yml requirements.txt .env.example huaben web scripts \
  | ssh "$HOST" "mkdir -p $DIR /mnt/4t/backups/huaben && cd $DIR && rm -rf huaben web scripts && tar xzf - --no-same-owner"

ssh "$HOST" bash -s <<EOF
set -e
cd $DIR
if [ ! -f .env ]; then
  cp .env.example .env
  echo "HUABEN_BACKUP_DIR=/mnt/4t/backups/huaben" >> .env
  # 没密钥服务照样能起(书架/阅读/配音队列都在),只是不能开书写章;填好后 docker compose up -d 即生效
  echo "!! 已从模板生成 $DIR/.env:还需填入 HUABEN_OPENROUTER_API_KEY,然后在 $DIR 执行 docker compose up -d"
fi
docker compose up -d --build
for i in \$(seq 1 30); do
  curl -fsS "http://127.0.0.1:\${HUABEN_HOST_PORT:-8210}/api/health" && echo && exit 0
  sleep 2
done
echo "60 秒内探活没通过,看日志:docker compose logs --tail 50 huaben" >&2
exit 1
EOF
