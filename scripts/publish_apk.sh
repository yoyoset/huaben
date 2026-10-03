#!/usr/bin/env bash
# 把本机构建好的安卓安装包放到 13 上(data/app/huaben.apk),手机浏览器打开 ⚙ 设置 → 下载安装包。
# 安装包是构建产物:不进 git、不打进镜像,更新 App 不用重建服务。先在 android/ 下构建:
#   JAVA_HOME=F:\dev\jdk-17  F:\dev\gradle-8.10.2\bin\gradle.bat assembleDebug
set -euo pipefail
APK="$(dirname "$0")/../android/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || { echo "没找到 $APK,先构建"; exit 1; }
ssh root@10.1.1.13 'mkdir -p /opt/huaben/data/app'
scp -q "$APK" root@10.1.1.13:/opt/huaben/data/app/huaben.apk.tmp
ssh root@10.1.1.13 'mv /opt/huaben/data/app/huaben.apk.tmp /opt/huaben/data/app/huaben.apk && ls -la /opt/huaben/data/app/'
curl -s -o /dev/null -w "下载检查:HTTP %{http_code},%{size_download} 字节
" http://10.1.1.13:8210/api/app/huaben.apk
