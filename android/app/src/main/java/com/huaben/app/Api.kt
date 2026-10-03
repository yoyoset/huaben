package com.huaben.app

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** 服务器给的错误:message 是后端写好的人话(detail),界面直接显示。 */
class ApiError(val code: Int, message: String) : Exception(message)

/**
 * 话本服务器接口。只用系统自带的 HttpURLConnection + org.json,不引第三方网络库。
 * 全是阻塞调用,只在后台线程里用。连不上时抛 IOException,界面据此提示"连不上服务器"。
 */
class Api(base: String) {
    private val base = base.trimEnd('/')

    private fun open(path: String, method: String, readTimeoutMs: Int = 30_000): HttpURLConnection =
        (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 8_000
            readTimeout = readTimeoutMs
            setRequestProperty("User-Agent", "huaben-android/0.1")
        }

    private fun send(path: String, method: String, body: JSONObject? = null): String {
        val c = open(path, method)
        try {
            if (body != null) {
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json")
                c.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = c.responseCode
            val text = (if (code < 400) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            if (code >= 400) throw ApiError(code, detail(text) ?: "请求失败($code)")
            return text
        } finally {
            c.disconnect()
        }
    }

    private fun detail(text: String): String? =
        try { JSONObject(text).optString("detail").ifEmpty { null } } catch (e: Exception) { null }

    fun profiles() = JSONArray(send("/api/profiles", "GET"))
    fun books(profile: Int) = JSONArray(send("/api/books?profile=$profile", "GET"))
    fun prepStatus(book: Int) = JSONObject(send("/api/books/$book/prepare", "GET"))
    fun prepare(book: Int, count: Int) = JSONObject(send("/api/books/$book/prepare", "POST", JSONObject().put("count", count)))
    fun progress(book: Int, chapter: Int) {
        send("/api/books/$book/progress", "PUT", JSONObject().put("chapter", chapter))
    }

    /** 先写临时文件,完整下完再改名:跑步途中打开 App 永远看不到下了一半的 MP3。 */
    fun download(path: String, dest: File) {
        val c = open(path, "GET", readTimeoutMs = 120_000)
        try {
            if (c.responseCode >= 400) throw ApiError(c.responseCode, "下载失败(${c.responseCode})")
            dest.parentFile?.mkdirs()
            val tmp = File(dest.path + ".part")
            c.inputStream.use { input -> tmp.outputStream().use { input.copyTo(it) } }
            if (!tmp.renameTo(dest)) {
                dest.delete()
                tmp.renameTo(dest)
            }
        } finally {
            c.disconnect()
        }
    }
}
