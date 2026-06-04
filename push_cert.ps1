# Push mitmproxy cert len MuMu sau khi da chay mitmweb lan dau
$certSrc = "$env:USERPROFILE\.mitmproxy\mitmproxy-ca-cert.cer"

if (-not (Test-Path $certSrc)) {
    Write-Host "[ERR] Chua co cert. Hay chay start_capture.bat truoc (doi 3 giay roi tat)." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Tim thay cert: $certSrc" -ForegroundColor Green
adb -s "127.0.0.1:7555" push $certSrc "/sdcard/mitmproxy-ca-cert.cer"
Write-Host ""
Write-Host "Cert da push len MuMu!" -ForegroundColor Green
Write-Host "Trong MuMu, vao: Settings -> Security -> Install Certificate" -ForegroundColor Yellow
Write-Host "Chon file: /sdcard/mitmproxy-ca-cert.cer" -ForegroundColor Yellow
Write-Host "Ten tuy chon: mitmproxy" -ForegroundColor Yellow
