$BASE_URL = "http://localhost:8084"
$API_KEY  = "ibts-api-key-dev"
$global:PASS = 0
$global:FAIL = 0
$global:TXN_ID = $null

function Write-Pass($msg) { Write-Host "  [PASS] $msg" -ForegroundColor Green; $global:PASS++ }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red;  $global:FAIL++ }
function Write-Section($msg) { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan }

$HDR = @{ "x-api-key" = $API_KEY; "Content-Type" = "application/json" }

# --- 1. Health ---
Write-Section "Health Check"
try {
    $r = Invoke-WebRequest "$BASE_URL/actuator/health" -UseBasicParsing -EA Stop
    if ($r.StatusCode -eq 200) { Write-Pass "GET /actuator/health -> 200" }
    else { Write-Fail "GET /actuator/health -> $($r.StatusCode)" }
} catch { Write-Fail "Health -> $($_.Exception.Message)" }

# --- 2. Happy-path POST /api/v1/payments ---
Write-Section "Happy-Path Payment"
$IDEM = "idem-$(Get-Random)"
$BODY = @{
    payer_vpa       = "alice@ibts"
    payee_vpa       = "bob@ibts"
    amount_paise    = 25000
    idempotency_key = $IDEM
    remarks         = "test"
} | ConvertTo-Json
try {
    $r = Invoke-WebRequest "$BASE_URL/api/v1/payments" `
         -Method POST `
         -Headers ($HDR + @{ "x-idempotency-key"=$IDEM }) `
         -Body $BODY -UseBasicParsing -EA Stop
    if ($r.StatusCode -in 200,201) {
        Write-Pass "POST /api/v1/payments -> $($r.StatusCode)"
        $global:TXN_ID = ($r.Content | ConvertFrom-Json).txn_id
        Write-Host "    txn_id = $global:TXN_ID" -ForegroundColor DarkGray
    } else { Write-Fail "POST /api/v1/payments -> $($r.StatusCode)" }
} catch { Write-Fail "POST /api/v1/payments -> $($_.Exception.Message)" }

# --- 3. Idempotency (replay same key) ---
Write-Section "Idempotency"
try {
    $r = Invoke-WebRequest "$BASE_URL/api/v1/payments" `
         -Method POST `
         -Headers ($HDR + @{ "x-idempotency-key"=$IDEM }) `
         -Body $BODY -UseBasicParsing -EA Stop
    if ($r.StatusCode -in 200,201) { Write-Pass "Duplicate key -> $($r.StatusCode) (idempotent)" }
    else { Write-Fail "Duplicate key -> $($r.StatusCode)" }
} catch { Write-Fail "Idempotency -> $($_.Exception.Message)" }

# --- 4. GET by txn_id ---
Write-Section "GET Payment by ID"
if ($global:TXN_ID) {
    try {
        $r = Invoke-WebRequest "$BASE_URL/api/v1/payments/$global:TXN_ID" -Headers $HDR -UseBasicParsing -EA Stop
        if ($r.StatusCode -eq 200) { Write-Pass "GET /payments/$global:TXN_ID -> 200" }
        else { Write-Fail "GET /payments/$global:TXN_ID -> $($r.StatusCode)" }
    } catch { Write-Fail "GET by ID -> $($_.Exception.Message)" }
} else { Write-Fail "Skipped - no txn_id captured from happy-path" }

# --- 5. GET non-existent -> 404 ---
Write-Section "GET Non-existent Payment"
try {
    Invoke-WebRequest "$BASE_URL/api/v1/payments/no-such-txn-9999" -Headers $HDR -UseBasicParsing -EA Stop | Out-Null
    Write-Fail "Expected 404 but got 200"
} catch {
    $c = $_.Exception.Response.StatusCode.value__
    if ($c -eq 404) { Write-Pass "Non-existent -> 404" }
    else { Write-Fail "Non-existent -> $c (expected 404)" }
}

# --- 6. Missing API key -> 401/403 ---
Write-Section "Auth - Missing API Key"
try {
    Invoke-WebRequest "$BASE_URL/api/v1/payments" `
         -Method POST `
         -Headers @{ "Content-Type"="application/json" } `
         -Body $BODY -UseBasicParsing -EA Stop | Out-Null
    Write-Fail "Expected 401/403 but got 200"
} catch {
    $c = $_.Exception.Response.StatusCode.value__
    if ($c -in 401,403) { Write-Pass "No API key -> $c" }
    else { Write-Fail "No API key -> $c (expected 401 or 403)" }
}

# --- 7. Invalid payload -> 422 ---
Write-Section "Validation - Bad Payload"
try {
    Invoke-WebRequest "$BASE_URL/api/v1/payments" `
         -Method POST `
         -Headers ($HDR + @{ "x-idempotency-key"="idem-bad-$(Get-Random)" }) `
         -Body "{}" -UseBasicParsing -EA Stop | Out-Null
    Write-Fail "Expected 422 but got 200"
} catch {
    $c = $_.Exception.Response.StatusCode.value__
    if ($c -eq 422) { Write-Pass "Bad payload -> 422" }
    else { Write-Fail "Bad payload -> $c (expected 422)" }
}

# --- 8. IP rate-limit (burst 15 rapid requests) ---
Write-Section "Rate Limiting"
$RL_HIT = $false
for ($i = 0; $i -lt 15; $i++) {
    try {
        Invoke-WebRequest "$BASE_URL/api/v1/payments" `
             -Method POST `
             -Headers ($HDR + @{ "x-idempotency-key"="idem-rl-$i-$(Get-Random)" }) `
             -Body $BODY -UseBasicParsing -EA Stop | Out-Null
    } catch {
        $c = $_.Exception.Response.StatusCode.value__
        if ($c -eq 429) { Write-Pass "Rate limit triggered on request $($i+1) -> 429"; $RL_HIT = $true; break }
    }
}
if (-not $RL_HIT) { Write-Fail "429 never triggered after 15 rapid requests (check RL config)" }

# --- Summary ---
Write-Host ""
Write-Host "========================================" -ForegroundColor White
$rc = if ($global:FAIL -eq 0) { "Green" } else { "Yellow" }
Write-Host "  Results:  $global:PASS passed   $global:FAIL failed" -ForegroundColor $rc
Write-Host "========================================" -ForegroundColor White
Write-Host ""
