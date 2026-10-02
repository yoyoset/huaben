// 跑 Python 配音程序的子进程,并把它的日志翻译成窗口上的一行状态。
//
// 为什么要"作业对象(Job Object)":启动器被任务管理器结束或崩溃时,普通子进程会留下来继续占着显卡、
// 用户在界面上却看不到它——正是要避免的"黑箱"。把子进程放进"关闭即结束"的作业对象,启动器一没,配音程序跟着没。
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

sealed class Worker
{
    public event Action<string> Line;    // 每一行原始日志
    public event Action<int> Exited;     // 子进程退出码
    Process proc;
    readonly IntPtr job = KillOnCloseJob.Create();

    public bool Running { get { return proc != null && !proc.HasExited; } }

    public void Start(string python, string args, string workDir)
    {
        var psi = new ProcessStartInfo(python, args)
        {
            WorkingDirectory = workDir, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
        };
        // 不设的话 Python 按 GBK 输出、并且整块缓冲,窗口里看到的是乱码、而且要等很久才出现
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        // jieba 加载时打一串 SyntaxWarning(它自己源码里的正则写法),无害但满屏红字像出了事,不显示
        psi.EnvironmentVariables["PYTHONWARNINGS"] = "ignore::SyntaxWarning";
        var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
        p.OutputDataReceived += (s, e) => { if (e.Data != null && Line != null) Line(e.Data); };
        p.ErrorDataReceived += (s, e) => { if (e.Data != null && Line != null) Line(e.Data); };
        p.Exited += (s, e) => { if (Exited != null) Exited(p.ExitCode); };
        p.Start();
        KillOnCloseJob.Assign(job, p.Handle);
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        proc = p;
    }

    public void Stop()
    {
        if (!Running) return;
        try { proc.Kill(); proc.WaitForExit(5000); } catch (InvalidOperationException) { }  // 恰好自己退出了
    }

    /// 日志行 → 状态文字;null = 这一行不改变状态。
    /// 依据的词由 huaben_voice 输出("加载引擎""引擎就绪""开始配""配好""出错了"),tests/test_pc_worker.py 钉住。
    public static string StatusOf(string line, int done)
    {
        int i = line.IndexOf("开始配 ");
        if (i >= 0) return "● 正在配音:" + line.Substring(i + 4);
        if (line.Contains("配好")) return "● 运行中:等下一章(这次已配 " + done + " 章)";
        if (line.Contains("引擎就绪")) return "● 运行中:等待配音任务";
        if (line.Contains("加载引擎")) return "⏳ 正在加载配音模型(约 40 秒)…";
        if (line.Contains("出错了")) return "⚠ 遇到问题,会自动重试(详情看下面的日志)";
        if (line.StartsWith("Traceback")) return "⚠ 配音程序出错(详情看下面的日志)";
        return null;
    }
}

static class KillOnCloseJob
{
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimit
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong R, W, O, RB, WB, OB; }

    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimit
    {
        public BasicLimit Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    const int ExtendedLimitInformation = 9;
    const uint KillOnJobClose = 0x2000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObject(IntPtr attrs, string name);
    [DllImport("kernel32.dll")]
    static extern bool SetInformationJobObject(IntPtr job, int cls, ref ExtendedLimit info, uint size);
    [DllImport("kernel32.dll")]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    public static IntPtr Create()
    {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        var info = new ExtendedLimit();
        info.Basic.LimitFlags = KillOnJobClose;
        SetInformationJobObject(job, ExtendedLimitInformation, ref info, (uint)Marshal.SizeOf(typeof(ExtendedLimit)));
        return job;
    }

    public static void Assign(IntPtr job, IntPtr process) { AssignProcessToJobObject(job, process); }
}
