// 启动器设置:pc_worker\HuabenVoice.ini(key=value)。第一次运行时写出带说明的默认文件,
// 想换音色/语速/服务器地址就用记事本改它,重启配音生效——不用碰命令行。
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

sealed class LauncherConfig
{
    public string Server = "http://10.1.1.13:8210";
    public string Engine = "qwen3-zh";
    public string Voice = "女声";
    public string Speed = "1.0";
    public string Token = "";
    public string Instruct = "";
    public string Path;

    const string Template =
        "# 话本配音设置。改完点窗口里的「重新启动」生效。以 # 开头的行是说明。\r\n" +
        "\r\n" +
        "# 话本服务器地址\r\n" +
        "server={0}\r\n" +
        "# 配音引擎:qwen3-zh(音质好,约 1.8 倍实时)/ kokoro-zh(快 15 倍,音色一般)\r\n" +
        "engine={1}\r\n" +
        "# 音色。qwen3-zh:女声 / 男声(pc_worker\\voices 里的参考音,整本书都照它配,前后一致)\r\n" +
        "# kokoro-zh:zf_ 开头女声、zm_ 开头男声,完整列表见 pc_worker\\README.md\r\n" +
        "voice={2}\r\n" +
        "# 语速倍率(kokoro-zh 用;qwen3-zh 跟随参考音的语速):1.0 正常,1.2 快一些\r\n" +
        "speed={3}\r\n" +
        "# 朗读语气:目前两个引擎都不使用,留空即可\r\n" +
        "instruct={5}\r\n" +
        "# 服务器设了配音令牌(HUABEN_VOICE_WORKER_TOKEN)才需要填\r\n" +
        "token={4}\r\n";

    public static LauncherConfig Load(string path)
    {
        var c = new LauncherConfig { Path = path };
        if (!File.Exists(path))
        {
            File.WriteAllText(path, string.Format(Template, c.Server, c.Engine, c.Voice, c.Speed, c.Token, c.Instruct), new UTF8Encoding(false));
            return c;
        }
        var kv = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var raw in File.ReadAllLines(path, Encoding.UTF8))
        {
            var line = raw.Trim();
            int eq = line.IndexOf('=');
            if (line.Length == 0 || line.StartsWith("#") || eq < 0) continue;
            kv[line.Substring(0, eq).Trim()] = line.Substring(eq + 1).Trim();
        }
        string v;
        if (kv.TryGetValue("server", out v) && v != "") c.Server = v.TrimEnd('/');
        if (kv.TryGetValue("engine", out v) && v != "") c.Engine = v;
        if (kv.TryGetValue("voice", out v) && v != "") c.Voice = v;
        double d;
        if (kv.TryGetValue("speed", out v) && double.TryParse(v, NumberStyles.Float, CultureInfo.InvariantCulture, out d)) c.Speed = v;
        if (kv.TryGetValue("token", out v)) c.Token = v;
        if (kv.TryGetValue("instruct", out v)) c.Instruct = v;
        return c;
    }

    /// 每个引擎的依赖装在各自的虚拟环境里(Qwen 要 transformers 5.x,与 Kokoro 的 4.x 冲突),按引擎名选
    public string VenvDir() { return Engine.StartsWith("qwen") ? ".venv-qwen" : ".venv"; }

    public string PythonArgs()
    {
        var sb = new StringBuilder("-u -m huaben_voice");
        sb.AppendFormat(" --server \"{0}\" --engine \"{1}\" --voice \"{2}\" --speed {3}", Server, Engine, Voice, Speed);
        if (Token != "") sb.AppendFormat(" --token \"{0}\"", Token);
        if (Instruct != "") sb.AppendFormat(" --instruct \"{0}\"", Instruct.Replace("\"", "'"));
        return sb.ToString();
    }
}
