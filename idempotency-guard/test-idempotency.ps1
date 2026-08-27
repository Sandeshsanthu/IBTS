param([string]$BaseUrl = "http://localhost:8080")

$pass = 0; $fail = 0
$run  = Get-Date -Format "yyyyMMddHHmmss"   # unique per run — avoids stale key collisions
$key1 = "txn-test-$run-001"
$key2 = "txn-test-$run-002"

Write-Host "`nRun ID : $run" -ForegroundColor DarkGray
Write-Host "Key 1  : $key1" -ForegroundColor DarkGray
Write-Host "Key 2  : $key2`n" -ForegroundColor DarkGray

function Assert-Pass { param([string]$Label)
    Write-Host "  [PASS] $Label" -ForegroundColor Green; $script:pass++ }

function Assert-Fail { param([string]$Label, [string]$Detail = "")
    Write-Host "  [FAIL] $Label $Detail" -ForegroundColor Red; $script:fail++ }

function Invoke-Api {
    param([string]$Uri, [string]$Method = "GET", [string]$Body = $null, [hashtable]$Headers = @{})
    $p = @{ Uri=$Uri; Method=$Method; ContentType="application/json"; Headers=$Headers; ErrorAction="Stop" }
    if ($Body) { $p.Body = $Body }
    return Invoke-RestMethod @p
}

function Test-Case { param([string]$Id, [string]$Desc)
    Write-Host "[$Id] $Desc" -ForegroundColor Cyan }

# T01
Test-Case "T01" "Health check"
try {
    $r = Invoke-Api -Uri "$BaseUrl/actuator/health"
    if ($r.status -eq "UP") { Assert-Pass "status=UP" } else { Assert-Fail "Expected UP" $r.status }
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T02
Test-Case "T02" "First request - new key"
$body1 = "{`"transactionRefId`":`"REF-$run-001`"}"
try {
    $r = Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body $body1 `
         -Headers @{ "X-Idempotency-Key"=$key1; "X-Caller-Service"="payment-router" }
    if ($r.duplicate -eq $false -and $r.status -eq "PROCESSING") { Assert-Pass "duplicate=false status=PROCESSING" }
    else { Assert-Fail "Unexpected response" ($r | ConvertTo-Json -Compress) }
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T03
Test-Case "T03" "Replay same key - expect 409 while PROCESSING"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body $body1 `
         -Headers @{ "X-Idempotency-Key"=$key1; "X-Caller-Service"="payment-router" }
    Assert-Fail "Expected 409 but got 200"
} catch {
    $resp = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($resp.duplicate -eq $true -and $resp.status -eq "PROCESSING") { Assert-Pass "duplicate=true status=PROCESSING" }
    else { Assert-Fail "Wrong body on 409" $_.ErrorDetails.Message }
}

# T04
Test-Case "T04" "Complete transaction"
$payload   = "{`"txnId`":`"TXN-$run`",`"auth`":`"APPROVED`"}"
$completeBody = "{`"transactionId`":`"$key1`",`"finalStatus`":`"SUCCESS`",`"responsePayload`":`"$($payload -replace '"','\"')`"}"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/complete" -Method POST -Body $completeBody
    Assert-Pass "204 No Content"
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T05
Test-Case "T05" "Replay after SUCCESS - expect 409 + cached payload"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body $body1 `
         -Headers @{ "X-Idempotency-Key"=$key1; "X-Caller-Service"="payment-router" }
    Assert-Fail "Expected 409 but got 200"
} catch {
    $resp = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($resp.duplicate -eq $true -and $resp.status -eq "SUCCESS" -and $resp.responsePayload) {
        Assert-Pass "duplicate=true status=SUCCESS responsePayload returned"
    } else { Assert-Fail "Wrong body on 409" $_.ErrorDetails.Message }
}

# T06
Test-Case "T06" "Double complete - expect 204 silent skip"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/complete" -Method POST -Body $completeBody
    Assert-Pass "204 No Content - skipped cleanly"
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T07
Test-Case "T07" "Different key - independent transaction"
$body2 = "{`"transactionRefId`":`"REF-$run-002`"}"
try {
    $r = Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body $body2 `
         -Headers @{ "X-Idempotency-Key"=$key2; "X-Caller-Service"="payment-router" }
    if ($r.duplicate -eq $false -and $r.status -eq "PROCESSING") { Assert-Pass "duplicate=false status=PROCESSING" }
    else { Assert-Fail "Unexpected response" ($r | ConvertTo-Json -Compress) }
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T08
Test-Case "T08" "Missing X-Idempotency-Key - expect 422"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body $body1 `
         -Headers @{ "X-Caller-Service"="payment-router" }
    Assert-Fail "Expected 422 but got 200"
} catch {
    $resp = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($resp.status -eq 422 -and $resp.message -like "*X-Idempotency-Key*") { Assert-Pass "422 X-Idempotency-Key: Field required" }
    else { Assert-Fail "Wrong error body" $_.ErrorDetails.Message }
}

# T09
Test-Case "T09" "Missing transactionRefId - expect 422"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/check" -Method POST -Body "{}" `
         -Headers @{ "X-Idempotency-Key"="txn-test-$run-003"; "X-Caller-Service"="payment-router" }
    Assert-Fail "Expected 422 but got 200"
} catch {
    $resp = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($resp.status -eq 422 -and $resp.message -like "*transactionRefId*") { Assert-Pass "422 transactionRefId: Field required" }
    else { Assert-Fail "Wrong error body" $_.ErrorDetails.Message }
}

# T10
Test-Case "T10" "Complete unknown key - expect 204 graceful skip"
$ghostBody = "{`"transactionId`":`"txn-ghost-$run`",`"finalStatus`":`"SUCCESS`"}"
try {
    Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/complete" -Method POST -Body $ghostBody
    Assert-Pass "204 No Content - graceful skip"
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# T11
Test-Case "T11" "Debug scan - verify this run keys in DynamoDB"
try {
    $records = Invoke-Api -Uri "$BaseUrl/api/v1/idempotency/debug/records"
    $rec1 = $records | Where-Object { $_.idempotencyKey -eq $key1 }
    $rec2 = $records | Where-Object { $_.idempotencyKey -eq $key2 }
    if ($rec1.status -eq "SUCCESS"    -and $rec1.expiresAt -gt 0) { Assert-Pass "$key1 SUCCESS + TTL set" }
    else { Assert-Fail "$key1 not found or wrong status" }
    if ($rec2.status -eq "PROCESSING" -and $rec2.expiresAt -gt 0) { Assert-Pass "$key2 PROCESSING + TTL set" }
    else { Assert-Fail "$key2 not found or wrong status" }
} catch { Assert-Fail "Request failed" $_.Exception.Message }

# Summary
$total = $pass + $fail
Write-Host "`n======================================" -ForegroundColor White
Write-Host " RESULTS: $pass/$total passed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Yellow" })
if ($fail -gt 0) { Write-Host " $fail test(s) FAILED - review output above" -ForegroundColor Red }
else             { Write-Host " All tests passed - service is healthy" -ForegroundColor Green }
Write-Host "======================================" -ForegroundColor White
