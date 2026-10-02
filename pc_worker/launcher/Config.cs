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
    public string Engine = "kokoro-zh";
    public string Voice = "zf_001";
    public string Speed = "1.0";
    public string Token = "";
    public string Path;

    const string Template =
        "# 话本配音设置。改完点窗口里的「重新启动」生效。以 # 开头的行是说明。\r\n" +
        "\r\n" +
        "# 话本服务器地址\r\n" +
        "server={0}\r\n" +
        "# 配音引擎:kokoro-zh(显卡上的中文模型)\r\n" +
        "engine={1}\r\n" +
        "# 音色:zf_ 开头是女声(如 zf_001 zf_002 zf_017),zm_ 开头是男声(如 zm_009 zm_010)。\r\n" +
        "# 编号不连续,写了不存在的会在日志里报错;完整列表见 pc_worker\\README.md\r\n" +
        "voice={2}\r\n" +
        "# 语速倍率:1.0 正常,1.2 快一些\r\n" +
        "speed={3}\r\n" +
        "# 服务器设了配音令牌(HUABEN_VOICE_WORKER_TOKEN)才需要填\r\n" +
        "token={4}\r\n";

    public static LauncherConfig Load(string path)
    {
        var c = new LauncherConfig { Path = path };
        if (!File.Exists(path))
        {
            File.WriteAllText(path, string.Format(Template, c.Server, c.Engine, c.Voice, c.Speed, c.Token), new UTF8Encoding(false));
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
        return c;
    }

    public string PythonArgs()
    {
        var sb = new StringBuilder("-u -m huaben_voice");
        sb.AppendFormat(" --server \"{0}\" --engine \"{1}\" --voice \"{2}\" --speed {3}", Server, Engine, Voice, Speed);
        if (Token != "") sb.AppendFormat(" --token \"{0}\"", Token);
        return sb.ToString();
    }
}
