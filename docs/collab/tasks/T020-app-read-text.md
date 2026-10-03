# T020 安卓 App:在 App 里看正文(下载后离线也能看)

依赖:无。只动 `android/`,不动服务器代码。

## 为什么

2026-10-03 用户:"让 APK 的内容也可以看文字。"现在 App 只能离线听;看正文要点"在线阅读(网页版)",那是个网页壳,没网就打不开,
也不和下载的章放在一起。要做的是:**下载时把正文一起存到手机,App 里有一个自己的阅读页,没网也能看。**

服务器已经有现成的接口,不用改:`GET /api/books/{book}/chapters/{idx}` 返回 `{"idx", "title", "body", "audio_url"}`;
`GET /api/books/{book}/prepare` 的 `chapters` 里列着范围内已写好的章(有没有音频都列)。

## 已定的方案

### 1. `Api.kt`:加一个方法

```kotlin
fun chapter(book: Int, idx: Int) = JSONObject(send("/api/books/$book/chapters/$idx", "GET"))
```

### 2. `Store.kt`:加正文的本地存储和两项设置

```kotlin
/** 下到手机上的正文:filesDir/text/<书>/<章>.json = {"title": 章名, "body": 正文}。 */
class Texts(ctx: Context) {
    fun has(book: Int, idx: Int): Boolean
    fun save(book: Int, idx: Int, title: String, body: String)   // 先写 .part 再改名,照 Api.download 的做法
    fun load(book: Int, idx: Int): Pair<String, String>?          // (章名, 正文);没有或读坏了返回 null
    fun list(book: Int): List<Int>                                // 已存的章号,从小到大
    fun title(book: Int, idx: Int): String                        // 没有返回 ""
    fun deleteAll(book: Int)
}
```

`Prefs` 里加:

```kotlin
var fontSize: Float          // 阅读字号(sp),默认 19f,键 "font_size"
fun lastRead(book: Int): Int // 这本书上次看到第几章,没有返回 0,键 "read_$book"
fun setLastRead(book: Int, idx: Int)
```

### 3. 新建 `ReadActivity.kt`:阅读页

- 入参(Intent extra):`book`(Int)、`idx`(Int)、`title`(书名,String)。
- 界面照 `Ui` 现有的写法用代码搭(不引 XML 布局):`ScrollView` 里一个 `Ui.column`,从上到下:
  1. 一行两个按钮:`A-`、`A+`(字号每次 ∓2,限制在 14~28,存进 `prefs.fontSize`,立刻生效)。
  2. 章标题:`Ui.text(this, "第${idx}章 ${章名}", 22f, Ui.TEXT)`。
  3. 正文:一个 `TextView`,字号 `prefs.fontSize`,颜色 `Ui.TEXT`,`setLineSpacing(0f, 1.6f)`,`setTextIsSelectable(false)`。
     显示的文字 = 正文按 `Regex("\\n+")` 切段,每段去掉首尾空白、丢掉空段,段首加两个全角空格 `\u3000\u3000`,段与段之间用 `"\n\n"` 连起来。
  4. 一行两个按钮:`上一章`、`下一章`。上一章/下一章指 `texts.list(book)` 里相邻的章号;没有就把按钮 `isEnabled = false`。
     点了之后在本页换章(不新开页面),并把 `ScrollView` 滚回顶部。
- 显示某一章时(包括换章):
  1. `texts.load(book, idx)` 有 → 直接显示。
  2. 没有 → 正文处先显示"正在取这一章…",后台线程 `Api(prefs.server).chapter(book, idx)`,成功就 `texts.save(...)` 并显示;
     失败显示"这一章还没下载到手机,现在也连不上服务器。"(`ApiError` 就显示它的 message)。
  3. `prefs.setLastRead(book, idx)`。
  4. `PlaybackService.report(prefs, book, idx)`(现成的:告诉服务器读到第几章,没网就记下来以后补报)。
- 页面背景 `Ui.BG`。不做翻页动画、不做自动滚屏、不记一章之内滚到了哪。

### 4. `BookActivity.kt`

- 加成员 `private lateinit var texts: Texts`,`onCreate` 里和 `downloads` 一起初始化。
- **下载**(`download()`):先把 `prepStatus` 的 `chapters` 里**每一章**的正文存下来(`texts.has` 的跳过),再照原样下载有 `audio_url` 的音频。
  下正文时状态行显示 `下载正文:第 $idx 章`。结尾的消息改成:
  - 一章都没有(`chapters` 为空):`还没有备好的章:先点「备 10 章」`
  - 否则:`已下载:正文 ${正文章数} 章,音频 ${音频章数} 章,共 ${MB} MB`(MB 只算音频,照旧)。
  - 失败的消息不变。
- **列表**(`renderList()`):列出"有正文或有音频"的全部章号(`texts.list(book)` 与 `downloads.list(book)` 的章号并集,从小到大)。每一章一行:
  - 有音频:`Ui.row(this, 看按钮, 听按钮)`;没有音频:只有看按钮;只有音频没有正文:只有听按钮。
  - 看按钮文字 `第${idx}章 ${章名}`,点了打开 `ReadActivity`(章名优先取 `texts.title`,为空再取 `downloads.list` 里的 title)。
  - 听按钮文字 `▶ 听`,点了 `play(idx)`(原有行为)。只有听按钮时文字照旧 `第${idx}章 ${章名}`。
  - 一章都没有:显示 `(还没有)`,照旧。
- 列表上面那行说明改成:`手机上已下载的章(点章名看正文;点「▶ 听」从这章开始播,自动接下一章)`。
- 在"下载已备好的到手机"按钮下面(`dlStatus` 之后)加一个主按钮,文字 `接着看`:
  点了打开 `ReadActivity`,章号 = `prefs.lastRead(book)`(若它不在 `texts.list(book)` 里,就用 `texts.list(book)` 的第一个);
  `texts.list(book)` 为空时,点了只在 `dlStatus` 显示 `还没有下载正文:先点「下载已备好的到手机」`。
- "在线阅读(网页版)"按钮保留不动。
- **删除**(`confirmDelete()`):提示文字改成 `删除这本书下载到手机上的所有正文和音频?(服务器上的不受影响,随时可以再下)`;确认后加一句 `texts.deleteAll(book)`。

### 5. 其它文件

- `AndroidManifest.xml`:在 `WebActivity` 那一行后面加 `<activity android:name=".ReadActivity" android:exported="false" />`。
- `android/app/build.gradle.kts`:`versionCode = 2`,`versionName = "0.2"`。
- `android/README.md`:开头的说明加一句"下载时正文一起存到手机,App 里可以离线看";"没做的"里把"正文离线阅读(现在只离线听);"这半句删掉,
  加一条"只下了正文、没下音频的书,离线时书架上不列(书架照旧只列有音频的书)"。

## 验收标准

1. 构建成功。在 Windows 的 cmd 里(不是 git bash,见 README 的坑):

   ```
   cd /d F:\my_ai\huaben\android
   set JAVA_HOME=F:\dev\jdk-17
   set GRADLE_USER_HOME=F:\dev\gradle-home
   F:\dev\gradle-8.10.2\bin\gradle.bat assembleDebug
   ```

   报告贴最后 15 行,要有 `BUILD SUCCESSFUL`。构建失败且修了 3 次还不过:状态改「卡住」。
2. `python -m pytest -q` 仍然全过(现在 496;这张卡不该改变它)。
3. 报告"没有实测的部分"照实写:本机没有安卓设备,界面没有在真机上点过。
4. 不要运行 `scripts/publish_apk.sh`(那是部署,架构方做)。

## 这次不做

- 不改服务器、不改网页。
- 不做离线书架列出"只有正文的书"、不做一章之内的阅读位置、不做夜间/护眼配色切换、不做边听边看的同步高亮。
- 不引新的依赖。

## 审核记录
