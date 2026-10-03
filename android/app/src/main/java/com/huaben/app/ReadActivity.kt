package com.huaben.app

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.ScrollView
import android.widget.TextView
import kotlin.concurrent.thread

/**
 * 阅读页:看手机上已下载的正文,没网也能看。上一章/下一章在本页换,不新开页面。
 * 正文没下过时现场去服务器取一份存下来;真连不上就提示。
 */
class ReadActivity : Activity() {
    private lateinit var prefs: Prefs
    private lateinit var texts: Texts
    private var book = 0
    private var idx = 0

    private lateinit var scroll: ScrollView
    private lateinit var titleView: TextView
    private lateinit var bodyView: TextView
    private lateinit var prevBtn: Button
    private lateinit var nextBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        texts = Texts(this)
        book = intent.getIntExtra("book", 0)
        idx = intent.getIntExtra("idx", 0)

        val root = Ui.column(this)
        scroll = ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) }
        setContentView(scroll)

        root.addView(Ui.text(this, intent.getStringExtra("title") ?: "", 14f, Ui.MUTED))
        root.addView(Ui.row(this,
            Ui.button(this, "A-") { changeFont(-2f) },
            Ui.button(this, "A+") { changeFont(2f) }))
        titleView = Ui.text(this, "", 22f, Ui.TEXT)
        root.addView(titleView)
        bodyView = Ui.text(this, "", prefs.fontSize, Ui.TEXT).apply {
            setLineSpacing(0f, 1.6f)
            setTextIsSelectable(false)
        }
        root.addView(bodyView)
        prevBtn = Ui.button(this, "上一章") { move(-1) }
        nextBtn = Ui.button(this, "下一章") { move(1) }
        root.addView(Ui.row(this, prevBtn, nextBtn))
        show()
    }

    /** 换到已下载章号里的相邻一章:不是 idx±1(中间有没下的章时也对)。 */
    private fun move(delta: Int) {
        val chapters = texts.list(book)
        val pos = chapters.indexOf(idx)
        if (pos < 0) return
        val target = pos + delta
        if (target < 0 || target >= chapters.size) return
        idx = chapters[target]
        show()
    }

    private fun updateNav() {
        val chapters = texts.list(book)
        val pos = chapters.indexOf(idx)
        prevBtn.isEnabled = pos > 0
        nextBtn.isEnabled = pos in 0 until chapters.size - 1
    }

    private fun show() {
        updateNav()
        scroll.scrollTo(0, 0)
        prefs.setLastRead(book, idx)
        PlaybackService.report(prefs, book, idx)

        val local = texts.load(book, idx)
        if (local != null) {
            render(local.first, local.second)
        } else {
            titleView.text = "第${idx}章"
            bodyView.textSize = prefs.fontSize
            bodyView.text = "正在取这一章…"
            fetch()
        }
    }

    private fun fetch() {
        val want = idx
        thread {
            try {
                val j = Api(prefs.server).chapter(book, want)
                val title = j.optString("title")
                val body = j.optString("body")
                texts.save(book, want, title, body)
                runOnUiThread { if (want == idx) { updateNav(); render(title, body) } }
            } catch (e: ApiError) {
                runOnUiThread { if (want == idx) bodyView.text = e.message ?: "取这一章失败" }
            } catch (e: Exception) {
                runOnUiThread { if (want == idx) bodyView.text = "这一章还没下载到手机,现在也连不上服务器。" }
            }
        }
    }

    private fun render(title: String, body: String) {
        titleView.text = "第${idx}章 $title"
        bodyView.textSize = prefs.fontSize
        bodyView.text = format(body)
    }

    /** 正文按空行切段,段首缩进两个全角空格,段间空一行。照顾手机屏,不缩进也读得下去。 */
    private fun format(body: String): String =
        body.split(Regex("\\n+"))
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .joinToString("\n\n") { "\u3000\u3000$it" }

    private fun changeFont(delta: Float) {
        prefs.fontSize = (prefs.fontSize + delta).coerceIn(14f, 28f)
        bodyView.textSize = prefs.fontSize
    }
}
