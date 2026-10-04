package com.huaben.app

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.concurrent.thread
import kotlin.math.abs

/**
 * 阅读页:看手机上已下载的正文,没网也能看。上一章/下一章在本页换,不新开页面。
 * 自动滚屏:点 ▶ 正文自己往下走,到章末自己翻到下一章(章号 + 1,手机上没有就向服务器取);一拖动就停。
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
    private lateinit var toggleBtn: Button
    private lateinit var noteView: TextView
    private lateinit var scroller: AutoScroll
    private val handler = Handler(Looper.getMainLooper())
    private var auto = false      // 读者要"自动读":翻到下一章后接着滚。滚没滚起来看 scroller.running
    private var used = false      // 这次打开阅读页用过自动滚屏:用过之后点正文才是"暂停/继续"
    private var waitTries = 0     // 等下一章写好:已经问了几次
    private var downY = 0f

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        texts = Texts(this)
        book = intent.getIntExtra("book", 0)
        idx = intent.getIntExtra("idx", 0)

        val root = Ui.column(this)
        scroll = ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) }
        toggleBtn = Ui.button(this, "▶", primary = true) { if (auto) pauseAuto() else startAuto() }
            .apply { contentDescription = "自动滚屏" }
        val bar = Ui.row(this,
            Ui.button(this, "A-") { changeFont(-2f) },
            Ui.button(this, "A+") { changeFont(2f) },
            Ui.button(this, "慢") { changeSpeed(-1) },
            Ui.button(this, "快") { changeSpeed(1) },
            toggleBtn).apply {
            setBackgroundColor(Ui.BG)
            val pad = Ui.dp(this@ReadActivity, 8)
            setPadding(pad, pad, pad, 0)
        }
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Ui.BG)
            addView(bar, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
            addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(page)

        scroller = AutoScroll(scroll,
            { AutoScroll.SPEEDS[prefs.scrollSpeed.coerceIn(0, AutoScroll.SPEEDS.size - 1)] * resources.displayMetrics.density },
            { turnPage() })

        root.addView(Ui.text(this, intent.getStringExtra("title") ?: "", 14f, Ui.MUTED))
        titleView = Ui.text(this, "", 22f, Ui.TEXT)
        root.addView(titleView)
        bodyView = Ui.text(this, "", prefs.fontSize, Ui.TEXT).apply {
            setLineSpacing(0f, 1.6f)
            setTextIsSelectable(false)
        }
        bodyView.setOnClickListener { if (auto) pauseAuto() else if (used) startAuto() }
        root.addView(bodyView)
        prevBtn = Ui.button(this, "上一章") { move(-1) }
        nextBtn = Ui.button(this, "下一章") { move(1) }
        root.addView(Ui.row(this, prevBtn, nextBtn))
        noteView = Ui.text(this, "", 14f, Ui.MUTED)
        root.addView(noteView)
        show()
    }

    override fun onStop() {
        pauseAuto()
        super.onStop()
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> downY = ev.y
            MotionEvent.ACTION_MOVE ->
                if (auto && abs(ev.y - downY) > ViewConfiguration.get(this).scaledTouchSlop) pauseAuto()
        }
        return super.dispatchTouchEvent(ev)
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

    private fun startAuto() {
        auto = true
        used = true
        toggleBtn.text = "⏸"
        noteView.text = ""
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) // 手不碰屏幕,不拦着它会自己熄屏
        scroller.start()
    }

    private fun pauseAuto() {
        auto = false
        toggleBtn.text = "▶"
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        scroller.stop()
        waitTries = 0
        handler.removeCallbacksAndMessages(null) // 连"等下一章"的定时也一起取消
    }

    private fun changeSpeed(dir: Int) {
        prefs.scrollSpeed = (prefs.scrollSpeed + dir).coerceIn(0, AutoScroll.SPEEDS.size - 1)
        noteView.text = "滚屏速度 ${prefs.scrollSpeed + 1}/${AutoScroll.SPEEDS.size}"
    }

    private fun show() {
        scroller.stop()
        handler.removeCallbacksAndMessages(null)
        noteView.text = ""
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
                runOnUiThread { if (want == idx) { pauseAuto(); bodyView.text = e.message ?: "取这一章失败" } }
            } catch (e: Exception) {
                runOnUiThread { if (want == idx) { pauseAuto(); bodyView.text = "这一章还没下载到手机,现在也连不上服务器。" } }
            }
        }
    }

    private fun render(title: String, body: String) {
        titleView.text = "第${idx}章 $title"
        bodyView.textSize = prefs.fontSize
        bodyView.text = format(body)
        if (auto) handler.postDelayed({ if (auto) scroller.start() }, 1500)
    }

    /** 自动滚屏走到章末。下一章 = 章号 + 1:手机上有就直接翻;没有就向服务器取;还没写好就每 10 秒问一次。 */
    private fun turnPage() {
        if (!auto) return
        val from = idx
        val want = idx + 1
        if (texts.has(book, want)) {
            waitTries = 0
            idx = want
            show()
            return
        }
        thread {
            try {
                val j = Api(prefs.server).chapter(book, want)
                texts.save(book, want, j.optString("title"), j.optString("body"))
                runOnUiThread { if (auto && idx == from) { waitTries = 0; idx = want; show() } }
            } catch (e: ApiError) {
                runOnUiThread { if (auto && idx == from) waitNext(e) }
            } catch (e: Exception) {
                runOnUiThread {
                    if (auto && idx == from) { pauseAuto(); noteView.text = "下一章没下载到手机,现在也连不上服务器。" }
                }
            }
        }
    }

    /** 服务器答 404 = 下一章还没写好(读到这里它才接着写):等。别的错误不等,照实显示。 */
    private fun waitNext(e: ApiError) {
        if (e.code != 404) { pauseAuto(); noteView.text = e.message ?: "取下一章失败"; return }
        waitTries++
        if (waitTries > 60) { // 10 分钟还没好:多半后台出了问题,别让屏幕一直亮着空等
            waitTries = 0
            pauseAuto()
            noteView.text = "下一章等了很久还没写好,先停下。稍后再点 ▶ 试试。"
            return
        }
        noteView.text = "下一章还在写,写好会自动接着读…"
        handler.postDelayed({ turnPage() }, 10_000)
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
