@echo off
chcp 65001 >nul
rem 编译话本配音启动器 -> pc_worker\HuabenVoice.exe
rem 用 Windows 自带的 .NET Framework 4 编译器(C# 5 语法),不需要装 Visual Studio 或任何依赖。
setlocal
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:winexe /optimize+ /codepage:65001 ^
  /win32icon:"%~dp0huaben.ico" /resource:"%~dp0huaben.ico",huaben.ico ^
  /r:System.Windows.Forms.dll /r:System.Drawing.dll ^
  /out:"%~dp0..\HuabenVoice.exe" ^
  "%~dp0HuabenVoice.cs" "%~dp0Worker.cs" "%~dp0Config.cs"
if errorlevel 1 (echo 编译失败 & exit /b 1)
echo 已生成 %~dp0..\HuabenVoice.exe
