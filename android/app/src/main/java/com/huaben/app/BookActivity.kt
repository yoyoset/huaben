package com.huaben.app

import android.app.Activity
import android.app.AlertDialog
import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import org.json.JSONObject
import kotlin.concurrent.thread

/**
 * 一本书:出门前"备 10 章 / 备 20 章"(服务器写正文、电脑配音)→ 下载到手机 → 离线播放。
 * 播放交给 PlaybackService,这里只是遥控器;关掉这个页面、锁屏都不影响播放。
 */
class BookActivity : Activity() {
    private lateinit var prefs: Prefs
    private lateinit var downloads: Downloads
    private lateinit var texts: Texts
    private var book = 0
    private var bookTitle = ""
    private var controller: MediaController? = null
    private var lastStatus: JSONObject? = null
    private val handler = Handler(Looper.getMainLooper())
    private var refreshing = false

    private lateinit var nowPlaying: TextView
    private lateinit var playBtn: Button
    private lateinit var prepStatus: TextView
    private lateinit var dlStatus: TextView
    private lateinit var list: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        downloads = Downloads(this)
        texts = Texts(this)
        book = intent.getIntExtra("book", 0)
        bookTitle = intent.getStringExtra("title") ?: ""
        val root = Ui.column(this)
        setContentView(ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) })

        root.addView(Ui.title(this, bookTitle))
        nowPlaying = Ui.text(this, "", 14f, Ui.MUTED)
        playBtn = Ui.button(this, "▶ 播放", primary = true) { togglePlay() }
        root.addView(nowPlaying)
        root.addView(Ui.row(this,
            Ui.button(this, "⏮") { controller?.seekToPreviousMediaItem() },
            playBtn,
            Ui.button(this, "⏭") { controller?.seekToNextMediaItem() }))

        root.addView(Ui.gap(this))
        root.addView(Ui.text(this, "出门听:先让服务器备好(写正文 + 电脑配音),再下载到手机", 14f, Ui.MUTED))
        root.addView(Ui.row(this, Ui.button(this, "再备 10 章") { prepare(10) }, Ui.button(this, "再备 20 章") { prepare(20) }))
        prepStatus = Ui.text(this, "", 14f, Ui.MUTED)
        root.addView(prepStatus)
        root.addView(Ui.button(this, "下载已备好的到手机", primary = true) { download() })
        dlStatus = Ui.text(this, "", 14f, Ui.MUTED)
        root.addView(dlStatus)
        root.addView(Ui.button(this, "接着看", primary = true) { continueReading() })
        root.addView(Ui.button(this, "在线阅读(网页版)") {
            startActivity(Intent(this, WebActivity::class.java).putExtra("url", "${prefs.server}/#/read/$book"))
        })

        root.addView(Ui.gap(this))
        root.addView(Ui.text(this, "手机上已下载的章(点章名看正文;点「▶ 听」从这章开始播,自动接下一章)", 14f, Ui.MUTED))
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(list)
        root.addView(Ui.gap(this, 24))
        root.addView(Ui.button(this, "删除这本书的下载") { confirmDelete() })
        renderList()
    }

    override fun onStart() {
        super.onStart()
        renderList()
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        future.addListener({
            val c = future.get()
            c.addListener(object : Player.Listener {
                override fun onEvents(player: Player, events: Player.Events) = showPlayer()
            })
            controller = c
            showPlayer()
        }, ContextCompat.getMainExecutor(this))
        refreshing = true
        refresh()
    }

    override fun onStop() {
        refreshing = false
        handler.removeCallbacksAndMessages(null)
        controller?.release()
        controller = null
        super.onStop()
    }

    private fun showPlayer() {
        val c = controller ?: return
        playBtn.text = if (c.isPlaying) "⏸ 暂停" else "▶ 播放"
        val title = c.currentMediaItem?.mediaMetadata?.title
        nowPlaying.text = if (title != null) "正在听:$title" else "还没开始听"
    }

    private fun togglePlay() {
        val c = controller ?: return
        when {
            c.isPlaying -> c.pause()
            c.mediaItemCount > 0 -> c.play()
            else -> {
                val first = downloads.list(book).firstOrNull()
                if (first != null) play(first.idx) else nowPlaying.text = "还没有下载的章"
            }
        }
    }

    private fun play(fromIdx: Int) {
        val c = controller ?: return
        val chapters = downloads.list(book)
        if (chapters.isEmpty()) return
        val start = chapters.indexOfFirst { it.idx == fromIdx }.coerceAtLeast(0)
        val items = chapters.map { ch ->
            MediaItem.Builder()
                .setMediaId(PlaybackService.mediaId(book, ch.idx))
                .setUri(Uri.fromFile(ch.file))
                .setMediaMetadata(MediaMetadata.Builder().setTitle("第${ch.idx}章 ${ch.title}").setArtist(bookTitle).build())
                .build()
        }
        val pos = prefs.positionFor(items[start].mediaId) // 上次停在这一章的哪儿,就从哪儿接着听
        c.setMediaItems(items, start, pos)
        c.prepare()
        c.play()
    }

    /** 每 10 秒看一次服务器备到哪了;备齐或页面不在前台就停。连不上服务器时不报错打扰,只显示一行。 */
    private fun refresh() {
        if (!refreshing) return
        thread {
            val text = try {
                val s = Api(prefs.server).prepStatus(book)
                lastStatus = s
                statusText(s)
            } catch (e: Exception) {
                "连不上服务器:可以照常听已下载的章"
            }
            runOnUiThread {
                prepStatus.text = text
                if (refreshing && lastStatus?.optBoolean("done") != true) handler.postDelayed({ refresh() }, 10_000)
            }
        }
    }

    private fun statusText(s: JSONObject): String {
        if (!s.optBoolean("active")) return "还没有备章。"
        val range = "第 ${s.getInt("start")}~${s.getInt("end")} 章"
        if (s.optBoolean("done")) return "$range 已备好,可以下载了"
        val total = s.getInt("total")
        val text = s.getInt("text_ready")
        val audio = s.getInt("audio_ready")
        val hint = if (audio < text) "(音频要电脑开着配音程序)" else ""
        return "正在备 $range:正文 $text/$total,音频 $audio/$total$hint"
    }

    private fun prepare(n: Int) {
        prepStatus.text = "开始备 $n 章…"
        thread {
            val text = try {
                val s = Api(prefs.server).prepare(book, n)
                lastStatus = s
                statusText(s)
            } catch (e: Exception) {
                "连不上服务器:${e.message}"
            }
            runOnUiThread {
                prepStatus.text = text
                handler.removeCallbacksAndMessages(null)
                handler.postDelayed({ refresh() }, 10_000)
            }
        }
    }

    /** 把服务器上备好范围内的正文下到手机(有配好音的顺带下);已经下过的跳过,换了音色的重下。 */
    private fun download() {
        dlStatus.text = "查看服务器上备好的章…"
        thread {
            val msg = try {
                val api = Api(prefs.server)
                val chapters = api.prepStatus(book).getJSONArray("chapters")
                val all = (0 until chapters.length()).map { chapters.getJSONObject(it) }
                texts.saveBookTitle(book, bookTitle)
                for (ch in all) {
                    val idx = ch.getInt("idx")
                    if (texts.has(book, idx)) continue
                    runOnUiThread { dlStatus.text = "下载正文:第 $idx 章" }
                    val j = api.chapter(book, idx)
                    texts.save(book, idx, j.optString("title"), j.optString("body"))
                }
                val ready = all.filter { !it.isNull("audio_url") }
                var done = 0
                for (ch in ready) {
                    val idx = ch.getInt("idx")
                    val url = ch.getString("audio_url")
                    val version = url.substringAfter("v=", url)
                    if (!downloads.has(book, idx, version)) {
                        val n = done + 1
                        runOnUiThread { dlStatus.text = "下载中:第 $idx 章($n/${ready.size})" }
                        api.download(url, downloads.fileFor(book, idx))
                        downloads.record(book, bookTitle, idx, ch.optString("title"), version)
                    }
                    done++
                }
                if (all.isEmpty()) "还没有备好的章:先点「再备 10 章」"
                else "已下载:正文 ${all.size} 章,音频 ${ready.size} 章,共 ${downloads.bytes(book) / 1_000_000} MB"
            } catch (e: Exception) {
                "下载失败:${e.message ?: e.javaClass.simpleName}(已下好的不受影响,再点一次接着下)"
            }
            runOnUiThread {
                dlStatus.text = msg
                renderList()
            }
        }
    }

    /** 列"有正文或有音频"的章:两样都有给"看 + 听",只有一样就给那一个。 */
    private fun renderList() {
        list.removeAllViews()
        val textIdx = texts.list(book)
        val audio = downloads.list(book).associateBy { it.idx }
        val all = (textIdx + audio.keys).toSortedSet()
        if (all.isEmpty()) {
            list.addView(Ui.text(this, "(还没有)", 14f, Ui.MUTED))
            return
        }
        for (idx in all) {
            val hasText = idx in textIdx
            val audioCh = audio[idx]
            when {
                hasText && audioCh != null -> {
                    val name = texts.title(book, idx).ifEmpty { audioCh.title }
                    list.addView(Ui.row(this,
                        Ui.button(this, "第${idx}章 $name") { openRead(idx) },
                        Ui.button(this, "▶ 听") { play(idx) }))
                }
                hasText -> {
                    val name = texts.title(book, idx)
                    list.addView(Ui.button(this, "第${idx}章 $name") { openRead(idx) })
                }
                audioCh != null -> list.addView(Ui.button(this, "第${idx}章 ${audioCh.title}") { play(idx) })
            }
        }
    }

    private fun openRead(idx: Int) {
        startActivity(Intent(this, ReadActivity::class.java)
            .putExtra("book", book).putExtra("idx", idx).putExtra("title", bookTitle))
    }

    /** 「接着看」:接着这本书上次读到的那章;不在已下正文里就用第一章。一章正文都没有就提示先下载。 */
    private fun continueReading() {
        val chapters = texts.list(book)
        if (chapters.isEmpty()) {
            dlStatus.text = "还没有下载正文:先点「下载已备好的到手机」"
            return
        }
        openRead(if (prefs.lastRead(book) in chapters) prefs.lastRead(book) else chapters.first())
    }

    private fun confirmDelete() {
        AlertDialog.Builder(this)
            .setMessage("删除这本书下载到手机上的所有正文和音频?(服务器上的不受影响,随时可以再下)")
            .setPositiveButton("删除") { _, _ ->
                controller?.stop()
                controller?.clearMediaItems()
                downloads.deleteAll(book)
                texts.deleteAll(book)
                renderList()
                dlStatus.text = "已删除"
            }
            .setNegativeButton("取消", null)
            .show()
    }
}
