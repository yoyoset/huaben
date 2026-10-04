package com.huaben.app

import android.view.Choreographer
import android.widget.ScrollView

/**
 * 让 ScrollView 匀速往下走,走到底调 onEnd。只管滚,不管翻章(翻章由阅读页决定)。
 * 按屏幕刷新逐帧走(Choreographer):用定时器每次挪一个整像素,慢速档看起来会一顿一顿。
 */
class AutoScroll(
    private val scroll: ScrollView,
    private val speed: () -> Float,   // 当前速度,像素/秒
    private val onEnd: () -> Unit,
) : Choreographer.FrameCallback {
    companion object {
        /** 速度档,dp/秒。和网页版 SCROLL_SPEEDS 同一组数。 */
        val SPEEDS = intArrayOf(15, 25, 40, 60, 90)
    }

    var running = false
        private set
    private var pos = 0f
    private var last = 0L

    fun start() {
        if (running) return
        running = true
        pos = scroll.scrollY.toFloat()
        last = 0L
        Choreographer.getInstance().postFrameCallback(this)
    }

    fun stop() {
        if (!running) return
        running = false
        Choreographer.getInstance().removeFrameCallback(this)
    }

    override fun doFrame(frameTimeNanos: Long) {
        if (!running) return
        // 切到后台再回来两帧之间隔很久:封顶 0.1 秒,免得一下跳一屏
        val dt = if (last == 0L) 0f else minOf((frameTimeNanos - last) / 1e9f, 0.1f)
        last = frameTimeNanos
        val content = scroll.getChildAt(0)
        // 高度为 0 = 刚换了内容还没排版:这一帧不动也不判断到底,否则会误判成"到底了"连翻好几章
        if (content != null && content.height > 0) {
            pos += speed() * dt
            scroll.scrollTo(0, pos.toInt())
            if (scroll.scrollY + scroll.height >= content.height - 2) {
                stop()
                onEnd()
                return
            }
        }
        Choreographer.getInstance().postFrameCallback(this)
    }
}
