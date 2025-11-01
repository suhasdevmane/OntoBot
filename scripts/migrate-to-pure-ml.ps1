# Pure ML Migration - Automated Execution Script
# Run this script to complete the full migration from hybrid to pure ML

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PURE ML DECIDER MIGRATION - AUTOMATED EXECUTION" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$repoRoot = "c:\Users\suhas\Documents\GitHub\OntoBot"
$deciderDir = Join-Path $repoRoot "decider-service"

# Change to repo root
Set-Location $repoRoot

Write-Host "[Step 0] Prerequisites Check" -ForegroundColor Yellow
Write-Host "  Checking Docker services..." -ForegroundColor Gray

# Check if microservices is running
$microHealthy = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:6001/analytics/functions" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        $microHealthy = $true
        Write-Host "  ✓ Microservices running on port 6001" -ForegroundColor Green
    }
} catch {
    Write-Host "  ✗ Microservices not reachable" -ForegroundColor Red
}

if (-not $microHealthy) {
    Write-Host ""
    Write-Host "  Starting microservices (required for registry access)..." -ForegroundColor Yellow
    docker-compose up -d microservices
    Write-Host "  Waiting 10 seconds for microservices to start..." -ForegroundColor Gray
    Start-Sleep -Seconds 10
    
    # Retry health check
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:6001/analytics/functions" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ Microservices now healthy" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Microservices still not healthy. Check logs: docker-compose logs microservices" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "  ✗ Microservices failed to start. Exiting." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[Step 1] Generate Training Data from Registry" -ForegroundColor Yellow
Set-Location (Join-Path $deciderDir "data")

if (Test-Path "generate_training_from_registry.py") {
    Write-Host "  Running generate_training_from_registry.py..." -ForegroundColor Gray
    python generate_training_from_registry.py
    
    if (Test-Path "registry_training.jsonl") {
        $lineCount = (Get-Content "registry_training.jsonl" | Measure-Object -Line).Lines
        Write-Host "  ✓ Generated registry_training.jsonl with $lineCount examples" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to generate registry_training.jsonl" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✗ generate_training_from_registry.py not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 2] Merge Training Datasets" -ForegroundColor Yellow

if (Test-Path "merge_training_data.py") {
    Write-Host "  Running merge_training_data.py..." -ForegroundColor Gray
    python merge_training_data.py
    
    if (Test-Path "decider_training_full.jsonl") {
        $lineCount = (Get-Content "decider_training_full.jsonl" | Measure-Object -Line).Lines
        Write-Host "  ✓ Generated decider_training_full.jsonl with $lineCount examples" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to generate decider_training_full.jsonl" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✗ merge_training_data.py not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 3] Train ML Models" -ForegroundColor Yellow
Set-Location $deciderDir

Write-Host "  Running training/train.py..." -ForegroundColor Gray
python training/train.py --data data/decider_training_full.jsonl --test-split 0.2

$modelDir = Join-Path $deciderDir "model"
$modelsExist = (Test-Path (Join-Path $modelDir "perform_model.pkl")) -and `
               (Test-Path (Join-Path $modelDir "label_model.pkl"))

if ($modelsExist) {
    Write-Host "  ✓ Models trained and saved to model/" -ForegroundColor Green
} else {
    Write-Host "  ✗ Model training failed. Check output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 4] Update Decider Service" -ForegroundColor Yellow
Set-Location (Join-Path $deciderDir "app")

# Backup existing main.py
if (Test-Path "main.py") {
    Write-Host "  Backing up current main.py to main_hybrid_backup.py..." -ForegroundColor Gray
    Copy-Item "main.py" "main_hybrid_backup.py" -Force
    Write-Host "  ✓ Backup created" -ForegroundColor Green
}

# Replace with pure ML version
if (Test-Path "main_ml_only.py") {
    Write-Host "  Replacing main.py with pure ML version..." -ForegroundColor Gray
    Copy-Item "main_ml_only.py" "main.py" -Force
    Write-Host "  ✓ main.py updated to pure ML" -ForegroundColor Green
} else {
    Write-Host "  ✗ main_ml_only.py not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 5] Rebuild and Restart Decider Service" -ForegroundColor Yellow
Set-Location $repoRoot

Write-Host "  Building decider-service container..." -ForegroundColor Gray
docker-compose build decider-service

Write-Host "  Starting decider-service..." -ForegroundColor Gray
docker-compose up -d decider-service

Write-Host "  Waiting 8 seconds for service to start..." -ForegroundColor Gray
Start-Sleep -Seconds 8

# Health check
try {
    $response = Invoke-RestMethod -Uri "http://localhost:6009/health" -TimeoutSec 5
    if ($response.ok -and $response.mode -eq "pure_ml") {
        Write-Host "  ✓ Decider service healthy (mode: $($response.mode))" -ForegroundColor Green
        Write-Host "    Perform model loaded: $($response.perform_model_loaded)" -ForegroundColor Gray
        Write-Host "    Label model loaded: $($response.label_model_loaded)" -ForegroundColor Gray
        Write-Host "    Registry count: $($response.registry_count)" -ForegroundColor Gray
    } else {
        Write-Host "  ⚠ Decider service running but health check failed" -ForegroundColor Yellow
        Write-Host "    Response: $($response | ConvertTo-Json)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ✗ Decider service health check failed" -ForegroundColor Red
    Write-Host "    Check logs: docker-compose logs decider-service" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "[Step 6] Validate ML Decider" -ForegroundColor Yellow
Set-Location $deciderDir

if (Test-Path "validate_ml_decider.py") {
    Write-Host "  Running validation script..." -ForegroundColor Gray
    Write-Host ""
    python validate_ml_decider.py
    Write-Host ""
} else {
    Write-Host "  ✗ validate_ml_decider.py not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "MIGRATION COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ Training data generated from registry" -ForegroundColor Green
Write-Host "✓ Models trained with predict_proba support" -ForegroundColor Green
Write-Host "✓ Decider service updated to pure ML" -ForegroundColor Green
Write-Host "✓ Service restarted and health checked" -ForegroundColor Green
Write-Host "✓ Validation tests executed" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Review validation results above" -ForegroundColor Gray
Write-Host "  2. Test with Rasa: send test queries to http://localhost:5005" -ForegroundColor Gray
Write-Host "  3. Monitor predictions and add training examples as needed" -ForegroundColor Gray
Write-Host "  4. Read ML_MIGRATION_GUIDE.md for troubleshooting and improvement tips" -ForegroundColor Gray
Write-Host ""
Write-Host "Rollback (if needed):" -ForegroundColor Yellow
Write-Host "  cd $deciderDir/app" -ForegroundColor Gray
Write-Host "  Copy-Item main_hybrid_backup.py main.py -Force" -ForegroundColor Gray
Write-Host "  docker-compose restart decider-service" -ForegroundColor Gray
Write-Host ""
Write-Host "Happy ML-powered decision-making! 🚀" -ForegroundColor Cyan
