' Marksman - one-click, silent launcher for mouse_mover.py
' Runs with no console window and starts minimized to the system tray.

Option Explicit

Dim fso, shell, scriptDir, appScript, searchDir, pywExe, depth

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
appScript = scriptDir & "\mouse_mover.py"

If Not fso.FileExists(appScript) Then
    MsgBox "Could not find mouse_mover.py next to Marksman.vbs." & vbCrLf & _
           "Expected it at: " & appScript, vbCritical, "Marksman"
    WScript.Quit 1
End If

' Look upward for a portable WinPython "python" folder containing pythonw.exe
searchDir = scriptDir
pywExe = ""
For depth = 1 To 5
    searchDir = fso.GetParentFolderName(searchDir)
    If searchDir = "" Then Exit For
    If fso.FileExists(searchDir & "\python\pythonw.exe") Then
        pywExe = searchDir & "\python\pythonw.exe"
        Exit For
    End If
Next

If pywExe = "" Then
    MsgBox "Could not locate pythonw.exe in a parent 'python' folder." & vbCrLf & _
           "Make sure this launcher stays somewhere under your WinPython folder.", _
           vbCritical, "Marksman"
    WScript.Quit 1
End If

' 0 = hidden window, False = don't wait for it to exit
shell.Run """" & pywExe & """ """ & appScript & """ --minimized", 0, False
