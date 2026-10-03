# 话本安卓 App

跑步/出门时离线听:在 App 里"备 10 章 / 备 20 章"(服务器写正文、电脑配音)→ 下载 MP3 到手机 → 锁屏后台播放。
下载时正文一起存到手机,App 里可以离线看。在线阅读直接打开网页版(目录、自动滚屏、写法设定都在网页里,不在 App 里重做)。

## 为什么是原生 App
服务在 `http://10.1.1.13:8210`(局域网 / Tailscale,没有 https)。浏览器和 WebView 在非安全来源下不允许 Service Worker,
网页做不了离线;跑步要锁屏后台播放、耳机/蓝牙按键切章,需要原生媒体服务(Media3 MediaSessionService)。

## 构建与发布
工具装在 `F:\dev`(JDK 17、Android SDK 35、Gradle 8.10.2),不改系统 PATH:
```
cd android
set JAVA_HOME=F:\dev\jdk-17
set GRADLE_USER_HOME=F:\dev\gradle-home
F:\dev\gradle-8.10.2\bin\gradle.bat assembleDebug
```
产物 `app/build/outputs/apk/debug/app-debug.apk`;`bash scripts/publish_apk.sh` 传到 13,手机浏览器打开话本 → ⚙ 设置 → 下载安装包。
(debug 签名:自用够了;以后要换正式签名,注意已装的 App 要先卸载。)

## 装工具时踩过的坑
- sdkmanager 报 "IO exception while downloading manifest",curl 却能下:本机 Java 走 IPv6 失败。
  `SDKMANAGER_OPTS=-Djava.net.preferIPv4Stack=true`;Gradle 同理写在 `gradle.properties`。
- PowerShell 管道给 `sdkmanager --licenses` 喂 y 不生效,改成 cmd 的 `< yes.txt` 重定向。
- git bash 里 `cmd //c` 调相对路径的 .bat 会被拆坏,用绝对 Windows 路径。

## 没做的
- 没在真机上测过(本机没有安卓设备/模拟器)。
- 每个读者不同音色。
