' IDEye - Silent Launcher (Zero console flash)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

venvPython = scriptDir & "\venv\Scripts\pythonw.exe"
If fso.FileExists(venvPython) Then
    WshShell.Run """" & venvPython & """ main.py", 0, False
Else
    WshShell.Run "pythonw.exe main.py", 0, False
End If
Set fso = Nothing
Set WshShell = Nothing
