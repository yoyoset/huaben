#!/bin/sh
# 每日备份(宿主机 cron 调用):在容器内对数据库做一致性快照,写到挂载的 /backups,保留最近 KEEP 份。
# 例:  17 4 * * *  /opt/huaben/scripts/backup.sh >> /var/log/huaben-backup.log 2>&1
set -eu
cd "$(dirname "$0")/.."
exec docker compose exec -T huaben python -m huaben.backup --out /backups --keep "${KEEP:-14}"
