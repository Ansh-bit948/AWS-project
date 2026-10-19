$ErrorActionPreference = 'Stop'
$reportPath = Join-Path $PSScriptRoot '..\docs\AWS_Cloud_Project_Report.docx'
$reportPath = [System.IO.Path]::GetFullPath($reportPath)
$pdfPath = [System.IO.Path]::ChangeExtension($reportPath, '.pdf')
$wordApp = $null
$reportDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $reportDoc = $wordApp.Documents.Open($reportPath, $false, $false)
    $reportDoc.Fields.Update() | Out-Null
    $reportDoc.Repaginate()
    foreach ($contents in $reportDoc.TablesOfContents) { $contents.Update() }
    $reportDoc.Repaginate()
    $reportDoc.Save()
    $reportDoc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('Pages: ' + $reportDoc.ComputeStatistics(2))
    Write-Output ('Word: ' + $reportPath)
    Write-Output ('PDF: ' + $pdfPath)
} finally {
    if ($null -ne $reportDoc) { $reportDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
    if ($null -ne $reportDoc) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($reportDoc) }
    if ($null -ne $wordApp) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) }
}
