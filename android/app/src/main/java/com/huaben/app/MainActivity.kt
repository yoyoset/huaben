package com.huaben.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import kotlin.concurrent.thread

/** 首页:第一次用先连服务器、选"谁在听";之后是这个人的书架。连不上服务器(跑步途中)就列已下载的书。 */
class MainActivity : Activity() {
    private lateinit var prefs: Prefs
    private lateinit var downloads: Downloads
    private lateinit var texts: Texts
    private lateinit var root: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        downloads = Downloads(this)
        texts = Texts(this)
        root = Ui.column(this)
        setContentView(ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) })
        // 安卓 13 起,播放通知(锁屏上的播放控制)要用户允许
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
    }

    override fun onResume() {
        super.onResume()
        if (prefs.server.isEmpty() || prefs.profileId == 0) setup() else shelf()
        flushPending()
    }

    private fun setup() {
        root.removeAllViews()
        root.addView(Ui.title(this, "连接话本"))
        root.addView(Ui.text(this, "服务器地址(家里局域网或 Tailscale):", 14f, Ui.MUTED))
        val input = EditText(this).apply {
            setText(prefs.server.ifEmpty { "http://10.1.1.13:8210" })
            setTextColor(Ui.TEXT)
            inputType = InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(input)
        val status = Ui.text(this, "", 14f, Ui.MUTED)
        val people = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(Ui.button(this, "连接", primary = true) {
            val server = input.text.toString().trim().trimEnd('/')
            status.text = "连接中…"
            thread {
                try {
                    val list = Api(server).profiles()
                    runOnUiThread {
                        status.text = if (list.length() == 0) "服务器上还没有读者,先在网页上选\"谁在看\"" else "谁在听?"
                        people.removeAllViews()
                        for (i in 0 until list.length()) {
                            val p = list.getJSONObject(i)
                            people.addView(Ui.button(this, p.getString("name")) {
                                prefs.server = server
                                prefs.profileId = p.getInt("id")
                                prefs.profileName = p.getString("name")
                                shelf()
                            })
                        }
                    }
                } catch (e: Exception) {
                    runOnUiThread { status.text = "连不上:${e.message ?: e.javaClass.simpleName}" }
                }
            }
        })
        root.addView(status)
        root.addView(people)
    }

    private fun shelf() {
        root.removeAllViews()
        root.addView(Ui.title(this, "${prefs.profileName} 的书架"))
        val status = Ui.text(this, "正在连服务器…", 14f, Ui.MUTED)
        val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(status)
        root.addView(list)
        root.addView(Ui.gap(this, 24))
        root.addView(Ui.button(this, "换人 / 改服务器地址") { prefs.profileId = 0; setup() })
        thread {
            try {
                val books = Api(prefs.server).books(prefs.profileId)
                runOnUiThread {
                    status.text = if (books.length() == 0) "书架是空的:先在网页上开一本书" else ""
                    for (i in 0 until books.length()) {
                        val b = books.getJSONObject(i)
                        if (b.optString("status") == "drafting") continue // 还在开书对话的书没有可听的
                        list.addView(bookButton(b.getInt("id"), b.getString("title")))
                    }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    val audio = downloads.books().toMap()
                    val text = texts.books().toMap()
                    val local = (audio.keys + text.keys).sorted().map { id -> id to (audio[id] ?: text[id] ?: "第 $id 本书") }
                    status.text = if (local.isEmpty()) "连不上服务器,手机上也还没有下载的章" else "连不上服务器(在外面很正常),下面是已下载的:"
                    local.forEach { (id, title) -> list.addView(bookButton(id, title)) }
                }
            }
        }
    }

    private fun bookButton(id: Int, title: String) = Ui.button(this, title) {
        startActivity(Intent(this, BookActivity::class.java).putExtra("book", id).putExtra("title", title))
    }

    private fun flushPending() {
        val server = prefs.server
        if (server.isEmpty()) return
        val pending = prefs.pendingProgress()
        if (pending.isEmpty()) return
        thread {
            for ((book, chapter) in pending) {
                try {
                    Api(server).progress(book, chapter)
                    prefs.clearPending(book)
                } catch (e: Exception) {
                    return@thread // 还是没网:下次再说
                }
            }
        }
    }
}
