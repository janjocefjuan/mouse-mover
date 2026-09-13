' Run this once to create a "Marksman" shortcut on your Desktop and in your
' Start Menu, both pointing at Marksman.vbs in this same folder.

Option Explicit

Dim fso, shell, scriptDir, target, link

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
target = scriptDir & "\Marksman.vbs"

If Not fso.FileExists(target) Then
    MsgBox "Could not find Marksman.vbs next to this installer.", vbCritical, "Marksman"
    WScript.Quit 1
End If

Set link = shell.CreateShortcut(shell.SpecialFolders("Desktop") & "\Marksman.lnk")
link.TargetPath = "wscript.exe"
link.Arguments = """" & target & """"
link.WorkingDirectory = scriptDir
link.Description = "Marksman"
link.Save

Set link = shell.CreateShortcut(shell.SpecialFolders("Programs") & "\Marksman.lnk")
link.TargetPath = "wscript.exe"
link.Arguments = """" & target & """"
link.WorkingDirectory = scriptDir
link.Description = "Marksman"
link.Save

MsgBox "Done. 'Marksman' now appears on your Desktop and in your Start Menu search.", _
       vbInformation, "Marksman"
