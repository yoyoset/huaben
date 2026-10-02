"""前端静态文件(PWA 壳)。

为什么要加 `Cache-Control: no-cache`:Starlette 的 StaticFiles 只给 ETag/Last-Modified、不给 Cache-Control,
浏览器于是按"启发式新鲜度"(大约文件年龄的 10%)直接用缓存,不问服务器。service worker 的"网络优先"`fetch()`
也走这层 HTTP 缓存。实测:服务器已返回新代码,整页重载后浏览器仍执行旧模块——部署新版后,手机可能在一段时间内
跑着新旧混杂的前端(一个模块新、它 import 的另一个旧)。

`no-cache` 不是"不缓存",而是"每次用前先问服务器":文件没变时服务器回 304、不传正文,代价只是一次很小的往返;
家用局域网/Tailscale 下可以忽略。没有用"文件名带哈希 + 长缓存",因为前端刻意不做构建步骤。
"""
from fastapi.staticfiles import StaticFiles


class RevalidatingStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response
