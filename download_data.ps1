# Analog Finder - data download script (run from the "D:\NASA APP" folder)
# Usage: right-click > Run with PowerShell, or in PowerShell:  cd "D:\NASA APP"; .\download_data.ps1
# Add -Moon to also fetch the 8 GB Moon elevation file:  .\download_data.ps1 -Moon
param([switch]$Moon)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$data = Join-Path $root "data\raw"
New-Item -ItemType Directory -Force -Path $data | Out-Null

$files = @(
  @{ name = "mars_mola_dem_463m.tif";   url = "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif" },   # ~2 GB
  @{ name = "mars_tes_albedo_7410m.tif"; url = "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif" }  # ~16 MB
)
if ($Moon) {
  $files += @{ name = "moon_lola_dem_118m.tif"; url = "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif" }  # ~8 GB, pixel x 0.5 = metres
}

foreach ($f in $files) {
  $out = Join-Path $data $f.name
  Write-Host "`n==> $($f.name)" -ForegroundColor Cyan
  # curl.exe ships with Windows 10/11. -C - resumes if the download was interrupted.
  curl.exe -L --fail --retry 5 --retry-delay 5 -C - -o $out $f.url
  if ($LASTEXITCODE -ne 0) { Write-Host "Failed: $($f.url) - just run the script again to resume." -ForegroundColor Red }
}

# Quick test of NASA POWER (no key needed): Atacama climatology
Write-Host "`n==> NASA POWER test (Atacama)" -ForegroundColor Cyan
$power = "https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M,PRECTOTCORR,RH2M,ALLSKY_SRF_ALB&community=RE&longitude=-69.92&latitude=-24.08&format=JSON"
try {
  Invoke-WebRequest -Uri $power -OutFile (Join-Path $data "power_test_atacama.json") -UseBasicParsing
  Write-Host "POWER OK -> data\raw\power_test_atacama.json" -ForegroundColor Green
} catch { Write-Host "POWER request failed: $_" -ForegroundColor Red }

Write-Host "`nDone. Files in $data" -ForegroundColor Green
Get-ChildItem $data | Format-Table Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}
