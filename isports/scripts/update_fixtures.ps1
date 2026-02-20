$ProjectDir = "d:\LCC\iSports\isports"
$VenvDir = "d:\LCC\iSports\env"

Write-Host "Starting iSports Fixture Update..." -ForegroundColor Cyan

cd $ProjectDir

if (Test-Path "$VenvDir\Scripts\activate.ps1") {
    & "$VenvDir\Scripts\Activate.ps1"
} else {
    Write-Host "Warning: Virtual environment not found at $VenvDir" -ForegroundColor Yellow
}

python manage.py seed_sports_data --no-logos

Write-Host "Update Complete!" -ForegroundColor Green
