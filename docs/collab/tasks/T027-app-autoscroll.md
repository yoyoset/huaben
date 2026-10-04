# T027 安卓 App:阅读页自动滚屏,读完自动接下一章

依赖:无(T020、T024 已通过)。只动 `android/`,不动服务器、不动网页。

## 为什么

2026-10-04 用户:"APK 可以看文字,自动滚屏,自动下一章。"App 里看正文已经有了(T020),但要一直用手划,读完一章还要点"下一章"。
网页版早就有自动滚屏 + 连续阅读(`web/js/autoscroll.js`),这张卡把同样的行为搬到 App 的阅读页:
**点一下开始,正文自己往下走;走到章末自己翻到下一章接着走;读者一动手就停。**

和网页版的两处不同(已定,不要照搬网页):

- App 换章是在同一个页面里换内容(`ReadActivity.show()`),"正在自动读"用一个成员变量记就够,不需要网页那种跨页面的标记。
- 自动翻到的"下一章"是 **章号 + 1**,不是"已下载章号里的下一个":手机上没有就现场向服务器取(取到就存下)。
  「下一章」按钮的行为**不变**(仍然只在已下载的章之间走)。

## 已定的方案

### 1. `Store.kt` 的 `Prefs`:加一项设置

加在 `fontSize` 后面:

```kotlin
/** 自动滚屏的速度档(0~4,对应 AutoScroll.SPEEDS)。全 App 一套设置,不分书。 */
var scrollSpeed: Int
    get() = p.getInt("scroll_speed", 1)
    set(v) = p.edit().putInt("scroll_speed", v).apply()
```

### 2. 新建 `android/app/src/main/java/com/huaben/app/AutoScroll.kt`

只管"让一个 ScrollView 匀速往下走,到底了说一声"。不知道章节、不知道网络。照下面写(可以直接用):

```kotlin
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
```

### 3. `ReadActivity.kt`

#### 3.1 布局:顶上一条固定的工具条,下面才是可滚动的正文

现在整页是一个 `ScrollView`,`A-`/`A+` 在里面,滚下去就看不见了。改成:

```kotlin
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
```

- `root` 里原来那一行 `Ui.row(this, A-, A+)` **删掉**(挪到工具条里了)。书名那行、章标题、正文、上一章/下一章照旧。
- `root` 最后(上一章/下一章那一行后面)加一行提示:`noteView = Ui.text(this, "", 14f, Ui.MUTED)`。
- 开关按钮的文字只有两种:没在自动读 `▶`,正在自动读 `⏸`(五个按钮挤一行,字多了会折行)。

#### 3.2 成员

```kotlin
private lateinit var toggleBtn: Button
private lateinit var noteView: TextView
private lateinit var scroller: AutoScroll
private val handler = Handler(Looper.getMainLooper())
private var auto = false      // 读者要"自动读":翻到下一章后接着滚。滚没滚起来看 scroller.running
private var used = false      // 这次打开阅读页用过自动滚屏:用过之后点正文才是"暂停/继续"
private var waitTries = 0     // 等下一章写好:已经问了几次
private var downY = 0f
```

`onCreate` 里(`scroll` 建好之后)建 `scroller`:

```kotlin
scroller = AutoScroll(scroll,
    { AutoScroll.SPEEDS[prefs.scrollSpeed.coerceIn(0, AutoScroll.SPEEDS.size - 1)] * resources.displayMetrics.density },
    { turnPage() })
```

#### 3.3 开始 / 暂停

```kotlin
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
    handler.removeCallbacksAndMessages(null) // 连"等下一章"的定时也一起取消
}
```

- `onStop()` 里调 `pauseAuto()`,再 `super.onStop()`:离开阅读页就停,回来不会自己动。
- 正文点击:`bodyView.setOnClickListener { if (auto) pauseAuto() else if (used) startAuto() }`
  (没用过自动滚屏时点正文什么都不做,免得随手一点它自己动起来)。
- 读者自己拖动 = 想自己看,暂停。在 Activity 上重写(不要用 `setOnTouchListener`:正文可点击后,轻点时手指的细微抖动也会算成移动):

  ```kotlin
  override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
      when (ev.actionMasked) {
          MotionEvent.ACTION_DOWN -> downY = ev.y
          MotionEvent.ACTION_MOVE ->
              if (auto && abs(ev.y - downY) > ViewConfiguration.get(this).scaledTouchSlop) pauseAuto()
      }
      return super.dispatchTouchEvent(ev)
  }
  ```

#### 3.4 速度

```kotlin
private fun changeSpeed(dir: Int) {
    prefs.scrollSpeed = (prefs.scrollSpeed + dir).coerceIn(0, AutoScroll.SPEEDS.size - 1)
    noteView.text = "滚屏速度 ${prefs.scrollSpeed + 1}/${AutoScroll.SPEEDS.size}"
}
```

正在滚的时候改速度立刻生效(`scroller` 每帧都重新读速度),不用重启滚动。

#### 3.5 换章时接着滚

- `show()` 最开头加三行(在 `updateNav()` 之前):

  ```kotlin
  scroller.stop()
  handler.removeCallbacksAndMessages(null)
  noteView.text = ""
  ```

- `render()` 最后加一行:正文真的显示出来了才接着滚,先停 1.5 秒让读者看清标题。

  ```kotlin
  if (auto) handler.postDelayed({ if (auto) scroller.start() }, 1500)
  ```

  只加在 `render()` 里。"正在取这一章…"和取失败的那几处**不要**加:那时页面上只有一行字,滚起来会立刻"到底"。
- `fetch()` 里两处失败分支(`ApiError` 和 `Exception`)各加一句 `pauseAuto()`(在 `if (want == idx)` 的花括号里,设置文字之前)。

#### 3.6 滚到章末:翻到下一章(章号 + 1)

```kotlin
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
```

- `startAuto()` 里不用管 `waitTries`;`pauseAuto()` 里加一句 `waitTries = 0`。
- 读者已经在章末(正文短,或者手动划到底)时点 `▶`:`scroller` 下一帧就判到底、调 `turnPage()`——这是对的,不用特殊处理。

#### 3.7 需要新增的 import

`android.os.Handler`、`android.os.Looper`、`android.view.MotionEvent`、`android.view.ViewConfiguration`、`android.view.WindowManager`、
`android.widget.LinearLayout`、`kotlin.math.abs`。

#### 3.8 类注释

类上面的注释第一行后面加一句:`自动滚屏:点 ▶ 正文自己往下走,到章末自己翻到下一章(章号 + 1,手机上没有就向服务器取);一拖动就停。`

### 4. 其它文件

- `android/app/build.gradle.kts`:`versionCode = 5`,`versionName = "0.5"`。
- `android/README.md` 第 4 行,把
  `在线阅读直接打开网页版(目录、自动滚屏、写法设定都在网页里,不在 App 里重做)。`
  改成
  `App 的阅读页有自动滚屏,读完一章自动接下一章。目录、写法设定在网页版里(「在线阅读」打开),不在 App 里重做。`

## 改哪些文件

- 新建:`android/app/src/main/java/com/huaben/app/AutoScroll.kt`
- 改:`android/app/src/main/java/com/huaben/app/ReadActivity.kt`、`.../Store.kt`、`android/app/build.gradle.kts`、`android/README.md`

`BookActivity.kt`、`Ui.kt`、`Api.kt`、`AndroidManifest.xml` 都不用动。

## 验收标准

1. 构建成功(在 Windows 的 cmd 里;副本里没有 `android/local.properties` 时,照主仓库 `F:\my_ai\huaben\android\local.properties` 的内容建一份,它不进 git):

   ```
   cd /d <本仓库>\android
   set JAVA_HOME=F:\dev\jdk-17
   set GRADLE_USER_HOME=F:\dev\gradle-home
   F:\dev\gradle-8.10.2\bin\gradle.bat assembleDebug
   ```

   报告贴最后 15 行,要有 `BUILD SUCCESSFUL`。构建失败且修了 3 次还不过:状态改「卡住」。
2. `python -m pytest -q` 仍然全过(现在 507;这张卡不该改变它)。
3. 报告里逐条回答(读自己的代码回答,写出对应的行号):
   - `show()` 开头有没有先停滚动、清掉定时?
   - "正在取这一章…"显示期间,有没有任何地方会启动滚动?(应该没有)
   - `pauseAuto()` 有没有清掉屏幕常亮?`onStop()` 有没有调它?
4. 不要运行 `scripts/publish_apk.sh`。报告"没有实测的部分"照实写:本机没有安卓设备,滚动、拖动暂停、翻章都没有在真机上试过。

## 这次不做

- 不记一章之内读到哪(退出再进来仍从章首开始)。
- 不改「上一章 / 下一章」按钮的规则(仍只在已下载的章之间走)。
- 不做工具条自动隐藏、不做翻页动画、不做配色切换、不做边听边看的同步。
- 不给书页(`BookActivity`)加任何东西;不改服务器、不改网页;不引新的依赖。
- 没有安卓单元测试工程,这张卡也不建(滚动要真机才看得出对不对,架构方验收时请用户装上试)。

## 审核记录

通过 2026-10-04(执行:opencode · deepseek-v4.1-flash,289 秒,由架构方用 `huaben-trials/run.sh` 派发)。
架构方在主仓库重跑:`gradle assembleDebug` → BUILD SUCCESSFUL,安装包 5.3 MB;`python -m pytest -q` 507 全过。
读了 `AutoScroll.kt`、`ReadActivity.kt`、`Store.kt` 的全部改动,与方案逐条一致,没有偏差。
对照网页版 `web/js/autoscroll.js`:五档速度、点正文暂停/继续、拖动即停、翻章后停 1.5 秒、等下一章的提示文字相同;
有意不同两处:开关按钮只显示 ▶/⏸(一行五个按钮放不下字)、等下一章每 10 秒问一次(网页 3 秒)。
安装包 0.5 已发布(`scripts/publish_apk.sh`,下载检查 HTTP 200)。**没有在真机上试过**:滚动手感、拖动暂停、翻章要用户装上试。
