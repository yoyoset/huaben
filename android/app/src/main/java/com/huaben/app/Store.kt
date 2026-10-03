package com.huaben.app

import android.content.Context
import org.json.JSONObject
import java.io.File

data class LocalChapter(val book: Int, val idx: Int, val title: String, val file: File)

/** 本机设置:服务器地址、谁在听、没报上去的收听进度。 */
class Prefs(ctx: Context) {
    private val p = ctx.getSharedPreferences("huaben", Context.MODE_PRIVATE)
    var server: String
        get() = p.getString("server", "") ?: ""
        set(v) = p.edit().putString("server", v.trim().trimEnd('/')).apply()
    var profileId: Int
        get() = p.getInt("profile_id", 0)
        set(v) = p.edit().putInt("profile_id", v).apply()
    var profileName: String
        get() = p.getString("profile_name", "") ?: ""
        set(v) = p.edit().putString("profile_name", v).apply()

    /** 阅读字号(sp)。全 App 一套设置,不分书。 */
    var fontSize: Float
        get() = p.getFloat("font_size", 19f)
        set(v) = p.edit().putFloat("font_size", v).apply()

    /** 这本书上次读到第几章:书页上的「接着看」从这里接。没有返回 0。 */
    fun lastRead(book: Int): Int = p.getInt("read_$book", 0)
    fun setLastRead(book: Int, idx: Int) = p.edit().putInt("read_$book", idx).apply()

    /** 离线时听到的章:等联网再告诉服务器,好让它接着往后写、往后配。每本书只记最远的一章。 */
    fun pendingProgress(): Map<Int, Int> =
        p.all.filterKeys { it.startsWith("pending_") }.mapNotNull { (k, v) ->
            k.removePrefix("pending_").toIntOrNull()?.let { it to (v as? Int ?: 0) }
        }.toMap()
    fun addPending(book: Int, chapter: Int) {
        if (chapter > p.getInt("pending_$book", 0)) p.edit().putInt("pending_$book", chapter).apply()
    }
    fun clearPending(book: Int) = p.edit().remove("pending_$book").apply()

    /** 上次停在哪:媒体 id("书:章")+ 毫秒。只记一处:跑步回来接着听的就是它。 */
    fun savePosition(mediaId: String, ms: Long) = p.edit().putString("pos_id", mediaId).putLong("pos_ms", ms).apply()
    fun positionFor(mediaId: String): Long = if (p.getString("pos_id", "") == mediaId) p.getLong("pos_ms", 0) else 0
}

/**
 * 下到手机上的章:filesDir/audio/<书>/<章>.mp3;同目录 index.json 记书名、各章标题和文件版本
 * (服务器音频地址里的 v=,换了音色或换成电脑版后会变——据此知道要重下)。离线时书架也从这里列。
 */
class Downloads(ctx: Context) {
    private val root = File(ctx.filesDir, "audio")

    private fun dir(book: Int) = File(root, book.toString())
    private fun indexFile(book: Int) = File(dir(book), "index.json")
    private fun index(book: Int): JSONObject =
        try { JSONObject(indexFile(book).readText()) } catch (e: Exception) { JSONObject() }
    private fun writeIndex(book: Int, j: JSONObject) {
        dir(book).mkdirs()
        indexFile(book).writeText(j.toString())
    }

    fun fileFor(book: Int, idx: Int) = File(dir(book), "$idx.mp3")

    fun has(book: Int, idx: Int, version: String): Boolean =
        fileFor(book, idx).isFile && index(book).optJSONObject("chapters")?.optJSONObject("$idx")?.optString("v") == version

    fun record(book: Int, bookTitle: String, idx: Int, title: String, version: String) {
        val j = index(book).put("title", bookTitle)
        val chapters = j.optJSONObject("chapters") ?: JSONObject()
        j.put("chapters", chapters.put("$idx", JSONObject().put("title", title).put("v", version)))
        writeIndex(book, j)
    }

    fun list(book: Int): List<LocalChapter> {
        val chapters = index(book).optJSONObject("chapters") ?: return emptyList()
        return chapters.keys().asSequence().mapNotNull { k ->
            val idx = k.toIntOrNull() ?: return@mapNotNull null
            val f = fileFor(book, idx)
            if (f.isFile) LocalChapter(book, idx, chapters.getJSONObject(k).optString("title"), f) else null
        }.sortedBy { it.idx }.toList()
    }

    /** 下过东西的书:离线打开 App 时书架就列这些。 */
    fun books(): List<Pair<Int, String>> =
        (root.listFiles() ?: emptyArray()).mapNotNull { d ->
            val id = d.name.toIntOrNull() ?: return@mapNotNull null
            if (list(id).isEmpty()) null else id to index(id).optString("title", "第 $id 本书")
        }.sortedBy { it.first }

    fun bytes(book: Int): Long = (dir(book).listFiles() ?: emptyArray()).sumOf { it.length() }

    fun deleteAll(book: Int) = dir(book).deleteRecursively()
}

/** 下到手机上的正文:filesDir/text/<书>/<章>.json = {"title": 章名, "body": 正文}。离线也能看。 */
class Texts(ctx: Context) {
    private val root = File(ctx.filesDir, "text")

    private fun dir(book: Int) = File(root, book.toString())
    private fun fileFor(book: Int, idx: Int) = File(dir(book), "$idx.json")

    fun has(book: Int, idx: Int): Boolean = fileFor(book, idx).isFile

    /** 先写 .part 再改名:写到一半被中断时,读到的要么是上一份要么没有,不会是坏文件。 */
    fun save(book: Int, idx: Int, title: String, body: String) {
        dir(book).mkdirs()
        val dest = fileFor(book, idx)
        val tmp = File(dest.path + ".part")
        tmp.writeText(JSONObject().put("title", title).put("body", body).toString())
        if (!tmp.renameTo(dest)) {
            dest.delete()
            tmp.renameTo(dest)
        }
    }

    /** (章名, 正文);没有或文件读坏了都返回 null,界面据此去服务器取。 */
    fun load(book: Int, idx: Int): Pair<String, String>? =
        try {
            val j = JSONObject(fileFor(book, idx).readText())
            j.optString("title") to j.optString("body")
        } catch (e: Exception) {
            null
        }

    fun list(book: Int): List<Int> =
        (dir(book).listFiles() ?: emptyArray())
            .filter { it.isFile && it.name.endsWith(".json") }
            .mapNotNull { it.name.removeSuffix(".json").toIntOrNull() }
            .sorted()

    fun title(book: Int, idx: Int): String = load(book, idx)?.first ?: ""

    fun deleteAll(book: Int) = dir(book).deleteRecursively()
}
