' IDEye - Silent Launcher (Zero console flash)
Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "pythonw.exe main.py", 0, False
Set WshShell = Nothing
