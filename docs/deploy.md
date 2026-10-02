# 部署(10.1.1.13,Docker Compose)

状态:**文件已备好,尚未部署,Dockerfile 尚未真正构建过**(开发机没有 docker;只做了静态自检,见 `tests/test_deploy_files.py`)。
首次部署时按下面步骤走,遇到的实际问题请回写到本文末尾"首次部署记录"。

## 前置(需要用户确认/提供)

1. **宿主机端口**:`docker-compose.yml` 默认映射 `8210`。13 上 8100 已被 SillyTavern 占用,先 `ss -ltn` 确认 8210 空闲,不空闲就在 `.env` 里设 `HUABEN_HOST_PORT`。
2. **OpenRouter 密钥**:写进服务器上的 `/opt/huaben/.env`(`HUABEN_OPENROUTER_API_KEY=...`),不要进 git、不要进镜像。
3. **花费上限**:`HUABEN_SPEND_LIMIT_USD_24H` 默认 2 美元/24 小时(全部书合计,只为拦住失控);按实际用量调整。
   当前花费见 `/api/health` 的 `spend_24h`;其中 `reliable: false` 表示有调用上游没报费用(换了非 OpenRouter 接口或免费模型),
   这时金额偏低、上限可能拦不住,需自行监控。
4. 参照 13 上 vpsmon / opencode-usage 的 compose 惯例核对一遍(本项目按 CLAUDE.md 里记录的惯例写成,**没有登录 13 看过实际文件**,可能有出入)。

## 步骤

```bash
# 在 13 上
sudo mkdir -p /opt/huaben /mnt/4t/backups/huaben && cd /opt/huaben
# 把项目文件放到这里(Dockerfile / docker-compose.yml / huaben/ / web/ / requirements.txt / scripts/)
cp .env.example .env && $EDITOR .env          # 填密钥;并设 HUABEN_BACKUP_DIR=/mnt/4t/backups/huaben
docker compose up -d --build
docker compose ps                              # 应为 healthy
curl -s http://127.0.0.1:${HUABEN_HOST_PORT:-8210}/api/health   # {"ok":true}
```

访问:`http://<13 的 Tailscale 地址>:8210/`,手机浏览器打开后"添加到主屏幕"。

## 备份

每日一次(宿主机 cron),备份**数据库**到 `/mnt/4t/backups/huaben`,保留最近 14 份:

```
17 4 * * *  /opt/huaben/scripts/backup.sh >> /var/log/huaben-backup.log 2>&1
```

- 用 SQLite 在线备份 API,服务运行中也是一致快照;备份后立刻 `integrity_check`,坏了会删掉并报错。
- **不备份音频**:音频由正文重新合成即可,体积大且无不可替代性。恢复流程:停容器 → 用备份文件替换 `data/huaben.db` → 起容器 → 后台会自动给缺音频的章补配音。
- 恢复演练还没做过(待首次部署后做一次,确认流程真的走得通)。

## 已知取舍 / 风险

- **容器以 root 运行**:避免 bind mount 目录属主不匹配导致首次启动写不进 `/data`(这类问题在没有 docker 的开发机上无法提前验证)。
  服务只在 Tailscale/局域网内,风险可接受;稳定后可改非 root 并相应 `chown`。
- **数据库迁移**:用 `PRAGMA user_version` 记版本,`huaben/migrations.py` 是有序清单(第 1 条 = 冻结的基线)。启动时自动升级;
  有数据的库升级前会先备份到 `data/premigrate/`;迁移在事务里执行,失败整体回滚、版本不变;程序比库旧则拒绝启动。
  **改表结构 = 在清单末尾追加一条,绝不改已有条目**(基线哈希有测试钉住)。回滚到旧版本程序不被支持(会被"库比程序新"拦住),只能用迁移前备份恢复。
- 单进程单 worker:补货互斥锁是进程内的,不要用 `--workers N` 起多进程。
- 音频与 DB 同在 `./data`,磁盘占用随连载线性增长(24kHz/48kbps 单声道约 360 KB/分钟);13 的 `/opt` 所在盘空间需留意。

## 首次部署记录

(待填)
