#requires -Version 5.1
<# Convert a genuine DOCX into legacy binary DOC using installed Microsoft Word.
   No HTML renaming, no installation, no overwriting existing outputs. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputDoc)
$ErrorActionPreference='Stop'
$src=(Resolve-Path -LiteralPath $InputDocx).ProviderPath
$dst=[IO.Path]::GetFullPath($OutputDoc)
if([IO.Path]::GetExtension($src) -ine '.docx'){throw 'Input must be a genuine .docx file.'}
if([IO.Path]::GetExtension($dst) -ine '.doc'){throw 'Output must have the .doc extension.'}
if(Test-Path -LiteralPath $dst){throw 'Output already exists; refusing to overwrite.'}
if(-not(Test-Path -LiteralPath (Split-Path -Parent $dst))){throw 'Output parent directory must already exist.'}
$word=$null;$doc=$null
try{
  $word=New-Object -ComObject Word.Application
  $word.Visible=$false
  $word.DisplayAlerts=0
  $doc=$word.Documents.Open($src,$false,$true)
  # wdFormatDocument=0: real Word 97-2003 binary .doc.
  $doc.SaveAs2($dst,0)
  $doc.Close(0)
  Write-Output "Created: $dst"
}catch{
  throw ('Conversion failed. This command requires an existing Windows Microsoft Word installation: '+$_.Exception.Message)
}finally{
  if($doc){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)}
  if($word){$word.Quit();[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)}
}
