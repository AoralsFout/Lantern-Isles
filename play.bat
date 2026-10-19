@echo off
setlocal
set "GODOT=D:\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64.exe"
if not exist "%GODOT%" (
  echo 未找到 Godot 4.7.2：%GODOT%
  echo 请修改 play.bat 中的 GODOT 路径，或在 Godot 编辑器中打开本目录。
  pause
  exit /b 1
)
start "" "%GODOT%" --path "%~dp0"
