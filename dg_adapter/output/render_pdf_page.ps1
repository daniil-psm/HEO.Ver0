param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("count", "render")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$PdfPath,

    [int]$Page = 1,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Wait-WinRtResult {
    param($Operation, [Type]$ResultType)

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

function Wait-WinRtAction {
    param($Operation)

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            -not $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    $task = $method.Invoke($null, @($Operation))
    $task.Wait()
}

$storageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$pdfDocumentType = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$memoryStreamType = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]

$file = Wait-WinRtResult ($storageFileType::GetFileFromPathAsync($PdfPath)) $storageFileType
$document = Wait-WinRtResult ($pdfDocumentType::LoadFromFileAsync($file)) $pdfDocumentType

if ($Mode -eq "count") {
    Write-Output $document.PageCount
    exit 0
}

if ($Page -lt 1 -or $Page -gt $document.PageCount) {
    throw "Seite $Page liegt außerhalb des Dokuments mit $($document.PageCount) Seiten."
}
if (-not $OutputPath) {
    throw "Für das Rendern muss ein Ausgabepfad angegeben werden."
}

$pdfPage = $document.GetPage($Page - 1)
$memoryStream = New-Object $memoryStreamType
Wait-WinRtAction ($pdfPage.RenderToStreamAsync($memoryStream))
$inputStream = $memoryStream.GetInputStreamAt(0)
$sourceStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($inputStream)
$destinationStream = [System.IO.File]::Create($OutputPath)
try {
    $sourceStream.CopyTo($destinationStream)
}
finally {
    $destinationStream.Dispose()
    $sourceStream.Dispose()
    $inputStream.Dispose()
    $memoryStream.Dispose()
    $pdfPage.Dispose()
}

Write-Output $OutputPath
