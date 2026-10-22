<#
.SYNOPSIS
    Adds a folder to the user PATH (used by install_current_version.bat --add-path).

.DESCRIPTION
    Replaces `setx Path ...`, which truncates the value to 1024 characters. The rest of the user
    PATH is kept as it is, including its registry type: entries such as %USERPROFILE%\... keep
    expanding. Only the user PATH is changed, never the system one.
    With -WhatIf it only reports what it would do and changes nothing.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File add_user_path.ps1 -Folder "C:\Python\Scripts" -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Folder
)

$ErrorActionPreference = 'Stop'

function Get-ComparablePath([string]$Entry) {
    return [Environment]::ExpandEnvironmentVariables($Entry.Trim().Trim('"')).TrimEnd('\')
}

$Folder = $Folder.Trim().Trim('"').TrimEnd('\')
$target = Get-ComparablePath $Folder

$current = ''
$kind = [Microsoft.Win32.RegistryValueKind]::ExpandString  # the Windows default for the user PATH
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment')
if ($key) {
    try {
        if ($key.GetValueNames() -contains 'Path') {
            $current = [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            $kind = $key.GetValueKind('Path')
        }
    }
    finally {
        $key.Close()
    }
}

$entries = @($current -split ';' | Where-Object { $_.Trim() -ne '' })
if ($entries | Where-Object { (Get-ComparablePath $_) -ieq $target }) {
    Write-Output 'La ruta ya existe en el PATH de usuario.'
    exit 0
}

$kept = $current.TrimEnd(';')
$newPath = if ($kept) { "$kept;$Folder" } else { $Folder }

if ($PSCmdlet.ShouldProcess("PATH de usuario ($kind, $($newPath.Length) caracteres)", "Anadir $Folder")) {
    $writable = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment')
    try {
        $writable.SetValue('Path', $newPath, $kind)
    }
    finally {
        $writable.Close()
    }
    # Like setx, tell running programs (Explorer, new terminals) that the environment changed:
    # removing a variable that does not exist broadcasts WM_SETTINGCHANGE and changes nothing.
    [Environment]::SetEnvironmentVariable('PYEXAMGENERATOR_PATH_REFRESH', $null, 'User')
    Write-Output 'PATH de usuario actualizado. Abre una nueva terminal para verlo.'
}
