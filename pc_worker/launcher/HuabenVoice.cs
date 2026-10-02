// 话本配音启动器:双击 pc_worker\HuabenVoice.exe → 一个看得见的窗口 + 右下角托盘图标,里面跑 Python 配音程序。
//
// 为什么不是命令行(2026-10-02 用户要求):命令行窗口看不出"在不在跑、在干什么、能不能关",像黑箱。
// 这里窗口上一行写清当前状态,下面是完整日志;关窗口 = 停止配音(正在配一章时会先问);最小化 = 收进托盘继续跑。
// 编译:launcher\build.cmd(用 Windows 自带的 .NET Framework 编译器,不用装任何东西)。
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Program
{
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    [STAThread]
    static void Main()
    {
        bool first;
        // 只允许一个:开两个会把模型加载两遍、抢同一块显卡
        using (new Mutex(true, "HuabenVoiceLauncher", out first))
        {
            if (!first)
            {
                MessageBox.Show("话本配音已经在运行了。\n看屏幕右下角托盘里的话本图标(灯),双击它打开窗口。", "话本配音");
                return;
            }
            SetProcessDPIAware();
            Application.EnableVisualStyles();
            Application.Run(new MainForm());
        }
    }
}

sealed class MainForm : Form
{
    readonly string baseDir = AppDomain.CurrentDomain.BaseDirectory;
    readonly Label status = new Label { Dock = DockStyle.Top, Font = new Font("Microsoft YaHei UI", 12f, FontStyle.Bold), Padding = new Padding(8, 6, 8, 0) };
    readonly Label detail = new Label { Dock = DockStyle.Top, Font = new Font("Microsoft YaHei UI", 9f), ForeColor = Color.DimGray, Padding = new Padding(10, 0, 8, 0) };
    readonly TextBox log = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill, Font = new Font("Microsoft YaHei UI", 9f), BackColor = Color.White };
    readonly Button restart = new Button { Text = "重新启动", AutoSize = true, Enabled = false };
    readonly NotifyIcon tray = new NotifyIcon();
    readonly Worker worker = new Worker();
    LauncherConfig cfg;
    StreamWriter logFile;
    int done;
    bool busy, stopping, toldAboutTray;

    public MainForm()
    {
        Text = "话本配音";
        Icon = LoadIcon(32);
        ClientSize = new Size(760, 480);
        MinimumSize = new Size(520, 320);

        var stop = new Button { Text = "停止配音并退出", AutoSize = true };
        var hide = new Button { Text = "收进托盘(继续配音)", AutoSize = true };
        var web = new Button { Text = "打开话本", AutoSize = true };
        var settings = new Button { Text = "改设置(音色/语速)", AutoSize = true };
        var bar = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(6) };
        bar.Controls.AddRange(new Control[] { stop, hide, restart, web, settings });
        Controls.Add(log);
        Controls.Add(bar);
        Controls.Add(detail);
        Controls.Add(status);
        // 高度按字体算:进程声明了高 DPI 感知,写死像素高度在 150% 缩放下会把字截掉(第一次实测就截了)
        status.Height = status.Font.Height + 14;
        detail.Height = detail.Font.Height + 6;

        stop.Click += (s, e) => Close();
        hide.Click += (s, e) => ToTray();
        restart.Click += (s, e) => StartWorker();
        web.Click += (s, e) => Process.Start(cfg.Server);
        settings.Click += (s, e) => Process.Start("notepad.exe", "\"" + cfg.Path + "\"");

        tray.Icon = LoadIcon(16);
        tray.Visible = true;
        tray.DoubleClick += (s, e) => ShowWindow();
        var menu = new ContextMenuStrip();
        menu.Items.Add("打开窗口", null, (s, e) => ShowWindow());
        menu.Items.Add("打开话本", null, (s, e) => Process.Start(cfg.Server));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("停止配音并退出", null, (s, e) => { ShowWindow(); Close(); });
        tray.ContextMenuStrip = menu;

        worker.Line += line => BeginInvoke(new Action(() => OnLine(line)));
        worker.Exited += code => BeginInvoke(new Action(() => OnExited(code)));
        Resize += (s, e) => { if (WindowState == FormWindowState.Minimized) ToTray(); };
        Shown += (s, e) => StartWorker();
    }

    static Icon LoadIcon(int size)
    {
        using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("huaben.ico"))
            return new Icon(s, new Size(size, size));
    }

    void StartWorker()
    {
        cfg = LauncherConfig.Load(Path.Combine(baseDir, "HuabenVoice.ini"));
        string python = Path.Combine(baseDir, cfg.VenvDir(), "Scripts", "python.exe");
        detail.Text = string.Format("服务器 {0}  ·  音色 {1}  ·  语速 {2}  ·  日志另存在 logs 文件夹", cfg.Server, cfg.Voice, cfg.Speed);
        if (!File.Exists(python))
        {
            SetStatus("■ 找不到 Python 环境:" + python + "(安装步骤见 pc_worker\\README.md)");
            restart.Enabled = true;
            return;
        }
        OpenLogFile();
        done = 0; busy = stopping = false; restart.Enabled = false;
        SetStatus("⏳ 正在启动配音程序…");
        Append("—— 启动:" + python + " " + cfg.PythonArgs().Replace(cfg.Token == "" ? "\u0000" : cfg.Token, "***"));
        worker.Start(python, cfg.PythonArgs(), baseDir);
    }

    void OnLine(string line)
    {
        Append(line);
        if (line.Contains("开始配 ")) busy = true;
        if (line.Contains("配好")) { done++; busy = false; }
        string s = Worker.StatusOf(line, done);
        if (s != null) SetStatus(s);
    }

    void OnExited(int code)
    {
        busy = false;
        restart.Enabled = true;
        if (stopping) return;
        SetStatus("■ 配音程序已停止(退出码 " + code + "),可以点「重新启动」;原因看下面的日志");
        Append("—— 配音程序退出,退出码 " + code);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (busy && e.CloseReason == CloseReason.UserClosing &&
            MessageBox.Show("正在配音的这一章会中断(下次开启时重新配这一章)。确定停止配音并退出吗?", "话本配音",
                            MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK)
        {
            e.Cancel = true;
            return;
        }
        stopping = true;
        worker.Stop();
        tray.Visible = false;  // 不清掉的话托盘里会残留一个点了没反应的图标
        if (logFile != null) logFile.Dispose();
        base.OnFormClosing(e);
    }

    void ToTray()
    {
        Hide();
        if (toldAboutTray) return;
        toldAboutTray = true;
        tray.ShowBalloonTip(5000, "话本配音还在后台运行", "双击右下角的话本图标打开窗口;右键可以停止配音并退出。", ToolTipIcon.Info);
    }

    void ShowWindow()
    {
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
    }

    void SetStatus(string s)
    {
        status.Text = s;
        string tip = "话本配音 · " + s.TrimStart('●', '⏳', '⚠', '■', ' ');
        tray.Text = tip.Length > 63 ? tip.Substring(0, 62) + "…" : tip;  // 托盘提示最长 63 字符,超了会抛异常
    }

    void Append(string line)
    {
        string stamped = DateTime.Now.ToString("HH:mm:ss ") + line;
        if (log.TextLength > 200000) log.Text = log.Text.Substring(100000);  // 常年开着也不让窗口越来越卡
        log.AppendText(stamped + Environment.NewLine);
        if (logFile != null) logFile.WriteLine(stamped);
    }

    void OpenLogFile()
    {
        if (logFile != null) return;
        string dir = Path.Combine(baseDir, "logs");
        Directory.CreateDirectory(dir);
        logFile = new StreamWriter(Path.Combine(dir, "voice-" + DateTime.Now.ToString("yyyyMMdd") + ".log"), true, new UTF8Encoding(false));
        logFile.AutoFlush = true;
    }
}
