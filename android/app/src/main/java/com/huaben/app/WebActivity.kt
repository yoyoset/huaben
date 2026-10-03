package com.huaben.app

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient

/** 在线阅读:直接打开网页版(目录、自动滚屏、写法设定都在网页里),不在 App 里重做一遍。 */
class WebActivity : Activity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true // 网页用 localStorage 记"谁在看"、字号
            settings.mediaPlaybackRequiresUserGesture = true
            webViewClient = WebViewClient()
            setBackgroundColor(Ui.BG)
        }
        setContentView(web)
        web.loadUrl(intent.getStringExtra("url") ?: return finish())
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
