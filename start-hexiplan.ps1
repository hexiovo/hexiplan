#requires -Version 5.1
[CmdletBinding()]
param([string]$ProjectPath='', [string]$Task='', [string]$TaskFile='', [string]$RunId='', [switch]$Resume, [switch]$CheckOnly, [string]$CodexPath='')
$ErrorActionPreference='Stop'
$script=Join-Path $PSScriptRoot 'tools\launch.py'
$a=@($script)
if($ProjectPath){$a+=@('--project',$ProjectPath)}
if($Task){$a+=@('--task',$Task)}
if($TaskFile){$a+=@('--task-file',$TaskFile)}
if($RunId){$a+=@('--run-id',$RunId)}
if($Resume){$a+='--resume'}
if($CheckOnly){$a+='--check-only'}
if($CodexPath){$a+=@('--codex-path',$CodexPath)}
if(Get-Command py -ErrorAction SilentlyContinue){ & py -3 @a }
elseif(Get-Command python -ErrorAction SilentlyContinue){ & python @a }
else{throw 'Python 3.10+ not found. No software was installed.'}
exit $LASTEXITCODE
