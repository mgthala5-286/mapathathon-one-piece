$itemIds = @(
  'S2B_MSIL2A_20260929T050649_R019_T43PGK_20260929T091314',
  'S2C_MSIL2A_20260904T050651_R019_T43PGK_20260904T095815',
  'S2B_MSIL2A_20260422T050649_R019_T43PGK_20260422T085149',
  'S2A_MSIL2A_20260320T051241_R019_T43PGK_20260320T102809'
)
$labels = @('2026-09-29','2026-09-04','2026-04-22','2026-03-20')
$bands = @('B03','B04','B08','B11')
$bbox = '77.42%2C8.64%2C77.60%2C8.75'
$outDir = Join-Path (Get-Location) 'imagery_crop'
New-Item -ItemType Directory -Force $outDir | Out-Null
for($i=0; $i -lt $itemIds.Count; $i++) {
  $item = $itemIds[$i]
  $label = $labels[$i]
  foreach($band in $bands) {
    $out = Join-Path $outDir ("{0}_{1}.png" -f $label,$band)
    if(Test-Path $out) { continue }
    $url = 'https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/' + $bbox + '/1024x640.png?collection=sentinel-2-l2a&item=' + $item + '&assets=' + $band + '&asset_bidx=' + $band + '%7C1&nodata=0&rescale=0%2C10000'
    curl.exe -L --fail --silent --show-error --output $out $url
    Start-Sleep -Seconds 2
  }
  $out = Join-Path $outDir ("{0}_TCI.png" -f $label)
  if(Test-Path $out) { continue }
  $url = 'https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/' + $bbox + '/1024x640.png?collection=sentinel-2-l2a&item=' + $item + '&assets=visual&asset_bidx=visual%7C1%2C2%2C3&nodata=0'
  curl.exe -L --fail --silent --show-error --output $out $url
}
