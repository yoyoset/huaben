package com.huaben.app

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** 界面用代码搭:几个页面都很简单,不值得为它们引 XML 布局和设计库。颜色与网页版一致(深色、暖色)。 */
object Ui {
    const val BG = 0xFF14110F.toInt()
    const val SURFACE = 0xFF1E1A17.toInt()
    const val TEXT = 0xFFECE4D8.toInt()
    const val MUTED = 0xFF9A8F80.toInt()
    const val ACCENT = 0xFFD9A55B.toInt()

    fun dp(ctx: Context, v: Int) = (v * ctx.resources.displayMetrics.density).toInt()

    fun column(ctx: Context) = LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(BG)
        val pad = dp(ctx, 16)
        setPadding(pad, dp(ctx, 24), pad, pad)
    }

    fun row(ctx: Context, vararg views: View) = LinearLayout(ctx).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        views.forEach { addView(it, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)) }
    }

    fun title(ctx: Context, s: String) = text(ctx, s, 22f, TEXT).apply { setPadding(0, 0, 0, dp(ctx, 8)) }

    fun text(ctx: Context, s: String, size: Float = 16f, color: Int = TEXT) = TextView(ctx).apply {
        text = s
        textSize = size
        setTextColor(color)
        setPadding(0, dp(ctx, 4), 0, dp(ctx, 4))
    }

    fun button(ctx: Context, label: String, primary: Boolean = false, onClick: () -> Unit) = Button(ctx).apply {
        text = label
        textSize = 16f
        isAllCaps = false
        setTextColor(if (primary) BG else TEXT)
        background = GradientDrawable().apply {
            cornerRadius = dp(ctx, 10).toFloat()
            setColor(if (primary) ACCENT else SURFACE)
        }
        setOnClickListener { onClick() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(dp(ctx, 4), dp(ctx, 4), dp(ctx, 4), dp(ctx, 4)) }
    }

    fun gap(ctx: Context, h: Int = 12) = View(ctx).apply {
        layoutParams = LinearLayout.LayoutParams(1, dp(ctx, h))
        setBackgroundColor(Color.TRANSPARENT)
    }
}
