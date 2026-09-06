<#
.SYNOPSIS
    Read-only MFA posture audit for the Midland tenant.

.DESCRIPTION
    Answers three questions ahead of the 1 Feb 2027 Microsoft-provided SMS/voice
    retirement:

      1. Who is still on legacy per-user MFA?
      2. Who would be BLOCKED after 1 Feb 2027 (phone is their only MFA method)?
      3. Who has no strong method at all?

    Deliberately avoids the Graph signIns API, which requires Entra ID P1/P2.
    Everything here reads per-user authentication state, which is available on
    any tenant. Nothing is written or changed.

.NOTES
    Consent required (delegated, Global Reader is enough):
      UserAuthenticationMethod.Read.All
      User.Read.All
      Policy.Read.All

    perUserMfaState lives on the beta endpoint only. It is the supported
    replacement for the retired MSOnline Get-MsolUser MFA properties.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path (Get-Location) 'mfa-audit')
)

$ErrorActionPreference = 'Stop'

# Methods that survive the Feb 2027 retirement and count as a real second factor.
# phoneAuthenticationMethod (SMS/voice) is deliberately NOT in this list.
$StrongMethods = @(
    'fido2AuthenticationMethod'                            # security keys AND passkeys
    'passwordlessMicrosoftAuthenticatorAuthenticationMethod'
    'microsoftAuthenticatorAuthenticationMethod'
    'softwareOathAuthenticationMethod'
    'windowsHelloForBusinessAuthenticationMethod'
)

function Connect-Audit {
    if (-not (Get-Module -ListAvailable Microsoft.Graph.Authentication)) {
        throw 'Microsoft.Graph module not found. Run: Install-Module Microsoft.Graph -Scope CurrentUser'
    }
    Connect-MgGraph -Scopes @(
        'UserAuthenticationMethod.Read.All'
        'User.Read.All'
        'Policy.Read.All'
    ) -NoWelcome
}

# Graph throttles hard when walking every user. Retry on 429 and 5xx.
function Invoke-GraphWithRetry {
    param([string]$Uri, [int]$MaxAttempts = 5)

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return Invoke-MgGraphRequest -Method GET -Uri $Uri -ErrorAction Stop
        }
        catch {
            $code = $_.Exception.Response.StatusCode.value__
            if ($code -eq 404) { return $null }
            if ($attempt -eq $MaxAttempts -or ($code -ne 429 -and $code -lt 500)) { throw }
            Start-Sleep -Seconds ([Math]::Pow(2, $attempt))
        }
    }
}

function Get-UserPosture {
    param($User)

    $methodsUri = "https://graph.microsoft.com/v1.0/users/$($User.Id)/authentication/methods"
    $methods = (Invoke-GraphWithRetry -Uri $methodsUri).value

    # '#microsoft.graph.fido2AuthenticationMethod' -> 'fido2AuthenticationMethod'
    $types = @($methods | ForEach-Object { ($_.'@odata.type') -replace '^#microsoft\.graph\.', '' })

    $reqUri = "https://graph.microsoft.com/beta/users/$($User.Id)/authentication/requirements"
    $perUser = (Invoke-GraphWithRetry -Uri $reqUri).perUserMfaState

    $hasPhone  = $types -contains 'phoneAuthenticationMethod'
    $hasStrong = @($types | Where-Object { $_ -in $StrongMethods }).Count -gt 0

    [pscustomobject]@{
        UPN             = $User.UserPrincipalName
        DisplayName     = $User.DisplayName
        AccountEnabled  = $User.AccountEnabled
        PerUserMfaState = $perUser
        HasPhone        = $hasPhone
        HasStrong       = $hasStrong
        # The Feb 2027 blocking condition: phone is the ONLY second factor.
        BlockedFeb2027  = ($hasPhone -and -not $hasStrong)
        NoMfaAtAll      = (-not $hasPhone -and -not $hasStrong)
        Methods         = ($types | Where-Object { $_ -ne 'passwordAuthenticationMethod' }) -join ';'
    }
}

Connect-Audit
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host 'Enumerating users...' -ForegroundColor Cyan
$users = Get-MgUser -All -Property Id, UserPrincipalName, DisplayName, AccountEnabled

$results = [System.Collections.Generic.List[object]]::new()
$i = 0
foreach ($user in $users) {
    $i++
    Write-Progress -Activity 'Auditing MFA posture' -Status $user.UserPrincipalName `
        -PercentComplete ($i / $users.Count * 100)
    try   { $results.Add((Get-UserPosture -User $user)) }
    catch { Write-Warning "$($user.UserPrincipalName): $($_.Exception.Message)" }
}
Write-Progress -Activity 'Auditing MFA posture' -Completed

$results | Sort-Object UPN | Export-Csv (Join-Path $OutputDir 'mfa-posture.csv') -NoTypeInformation

# Only enabled accounts matter -- a disabled account cannot be blocked.
$live = $results | Where-Object AccountEnabled

$blocked  = @($live | Where-Object BlockedFeb2027)
$noMfa    = @($live | Where-Object NoMfaAtAll)
$legacy   = @($live | Where-Object { $_.PerUserMfaState -in @('enabled', 'enforced') })

Write-Host ''
Write-Host "Enabled accounts:              $($live.Count)"
Write-Host "Still on legacy per-user MFA:  $($legacy.Count)"   -ForegroundColor Yellow
Write-Host "BLOCKED after 1 Feb 2027:      $($blocked.Count)"  -ForegroundColor Red
Write-Host "No MFA method at all:          $($noMfa.Count)"    -ForegroundColor Red
Write-Host ''

if ($blocked.Count) {
    Write-Host 'Phone is the only second factor for:' -ForegroundColor Red
    $blocked | Select-Object UPN, PerUserMfaState, Methods | Format-Table -AutoSize
}
if ($noMfa.Count) {
    Write-Host 'No MFA method registered:' -ForegroundColor Red
    $noMfa | Select-Object UPN, PerUserMfaState | Format-Table -AutoSize
}

Write-Host "Full results: $(Join-Path $OutputDir 'mfa-posture.csv')" -ForegroundColor Green
