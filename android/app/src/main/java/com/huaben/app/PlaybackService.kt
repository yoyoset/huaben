package com.huaben.app

import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import kotlin.concurrent.thread

/**
 * 后台播放服务:锁屏、通知栏、耳机线控/蓝牙耳机按键都走它(Media3 自带),跑步时手机揣兜里照样能听、能切章。
 * 每开始一章就告诉服务器"听到第几章"——服务器据此往后写、往后配;没网就记下来,下次联网再报。
 */
class PlaybackService : MediaSessionService() {
    private var session: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val prefs = Prefs(this)
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(),
                true, // 来电话/导航播报时自动让路
            )
            .setHandleAudioBecomingNoisy(true) // 耳机掉了自动暂停,不外放
            .build()
        player.addListener(object : Player.Listener {
            override fun onMediaItemTransition(item: MediaItem?, reason: Int) {
                val (book, idx) = parseId(item?.mediaId) ?: return
                report(prefs, book, idx)
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                val id = player.currentMediaItem?.mediaId ?: return
                if (!isPlaying) prefs.savePosition(id, player.currentPosition)
            }
        })
        session = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: android.content.Intent?) {
        val p = session?.player
        if (p == null || !p.playWhenReady || p.mediaItemCount == 0) stopSelf() // 没在播:划掉 App 就退出;在播就继续
    }

    override fun onDestroy() {
        session?.run {
            player.release()
            release()
        }
        session = null
        super.onDestroy()
    }

    companion object {
        fun mediaId(book: Int, idx: Int) = "$book:$idx"
        fun parseId(id: String?): Pair<Int, Int>? {
            val parts = id?.split(":") ?: return null
            if (parts.size != 2) return null
            val b = parts[0].toIntOrNull() ?: return null
            val i = parts[1].toIntOrNull() ?: return null
            return b to i
        }

        fun report(prefs: Prefs, book: Int, idx: Int) {
            val server = prefs.server
            if (server.isEmpty()) return
            thread {
                try {
                    Api(server).progress(book, idx)
                } catch (e: Exception) {
                    prefs.addPending(book, idx) // 跑步时多半没网:回家联网后由 MainActivity 补报
                }
            }
        }
    }
}
