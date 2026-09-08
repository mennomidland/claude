<#
.SYNOPSIS
  Creates and configures the Midland-ScanIngest app registration for the scanner
  mail routine (docs/routines/06-scan-mailbox.md).

.DESCRIPTION
  Does everything the routine needs, in one run:

    1. app registration + service principal
    2. Mail.ReadWrite and Sites.Selected application permissions
    3. admin consent for both
    4. a client secret
    5. an ApplicationAccessPolicy restricting mail to automation@ only
    6. write permission on the jobs site only
    7. verification of 5 and 6, and the three environment variables to set

  Idempotent: re-running finds what exists and fills in what does not. The only
  thing it cannot skip is the client secret, which cannot be read back after
  creation -- see -NewSecret.

  WHY THIS IS A SCRIPT AND NOT AUTOMATED: steps 1-3 need directory-write rights
  and interactive admin consent. An app-only credential cannot grant itself
  those, by design, so this has to run as a human admin. Everything after
  consent is then automatable, and the scan routine itself needs no admin rights.

.NOTES
  Requires, as a Global Administrator (or Application Administrator + Exchange
  Administrator + SharePoint Administrator):

    Install-Module Microsoft.Graph, ExchangeOnlineManagement, PnP.PowerShell

  Role IDs are resolved by NAME from Microsoft Graph's own service principal
  rather than hardcoded as GUIDs -- the GUIDs are stable in practice but
  resolving them means a typo fails loudly instead of granting the wrong thing.

.EXAMPLE
  ./provision_scan_app.ps1
  ./provision_scan_app.ps1 -WhatIf          # show what would change
  ./provision_scan_app.ps1 -NewSecret       # rotate the secret on an existing app
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$AppName    = 'Midland-ScanIngest',
    [string]$Mailbox    = 'automation@midlandind.com.au',
    [string]$JobsSite   = 'https://midlandind.sharepoint.com/sites/jobs',
    # A mailbox the policy must NOT permit. Proving a denial is the only check
    # that shows the restriction actually bit; a lone "Granted" does not.
    [string]$ControlMailbox = 'menno@midlandind.com.au',
    [switch]$NewSecret
)

$ErrorActionPreference = 'Stop'
$GraphAppId = '00000003-0000-0000-c000-000000000000'   # Microsoft Graph, well-known
$Roles      = @('Mail.ReadWrite', 'Sites.Selected')

function Step($n, $text) { Write-Host "`n[$n] $text" -ForegroundColor Cyan }
function Ok($text)       { Write-Host "    OK   $text" -ForegroundColor Green }
function Skip($text)     { Write-Host "    --   $text (already done)" -ForegroundColor DarkGray }
function Warn($text)     { Write-Host "    !!   $text" -ForegroundColor Yellow }

# --- 1. app registration ----------------------------------------------------

Step 1 "App registration '$AppName'"
Connect-MgGraph -Scopes 'Application.ReadWrite.All','AppRoleAssignment.ReadWrite.All' `
                -NoWelcome

$app = Get-MgApplication -Filter "displayName eq '$AppName'" -ErrorAction SilentlyContinue |
       Select-Object -First 1
if ($app) {
    Skip "app exists, appId $($app.AppId)"
} elseif ($PSCmdlet.ShouldProcess($AppName, 'Create app registration')) {
    $app = New-MgApplication -DisplayName $AppName -SignInAudience 'AzureADMyOrg' `
        -Notes 'Scanner mail -> Completed Jobs ingest. See repo docs/routines/06-scan-mailbox.md'
    Ok "created, appId $($app.AppId)"
} else { return }

$sp = Get-MgServicePrincipal -Filter "appId eq '$($app.AppId)'" -ErrorAction SilentlyContinue |
      Select-Object -First 1
if ($sp) {
    Skip 'service principal exists'
} elseif ($PSCmdlet.ShouldProcess($AppName, 'Create service principal')) {
    $sp = New-MgServicePrincipal -AppId $app.AppId
    Ok 'service principal created'
}

# --- 2 + 3. permissions and consent -----------------------------------------

Step 2 "Application permissions: $($Roles -join ', ')"
$graphSp = Get-MgServicePrincipal -Filter "appId eq '$GraphAppId'"
$existing = @(Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id)

foreach ($roleName in $Roles) {
    $role = $graphSp.AppRoles | Where-Object { $_.Value -eq $roleName -and $_.AllowedMemberTypes -contains 'Application' }
    if (-not $role) { throw "Microsoft Graph exposes no application role named '$roleName'" }

    if ($existing | Where-Object { $_.AppRoleId -eq $role.Id }) {
        Skip "$roleName"
        continue
    }
    if ($PSCmdlet.ShouldProcess($roleName, 'Grant application permission (admin consent)')) {
        New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id `
            -PrincipalId $sp.Id -ResourceId $graphSp.Id -AppRoleId $role.Id | Out-Null
        Ok "$roleName granted and consented"
    }
}
Warn 'Mail.ReadWrite now reaches EVERY mailbox until step 5 lands. Do not stop here.'

# --- 4. secret --------------------------------------------------------------

Step 4 'Client secret'
$secret = $null
if ($NewSecret -or -not $app.PasswordCredentials) {
    if ($PSCmdlet.ShouldProcess($AppName, 'Add client secret')) {
        $cred = Add-MgApplicationPassword -ApplicationId $app.Id -PasswordCredential @{
            DisplayName   = 'scan-ingest routine'
            # 12 months. Shorter than the default and paired with a diary note,
            # per the rotation caveat in docs/routines/04-graph-access.md.
            EndDateTime   = (Get-Date).AddMonths(12)
        }
        $secret = $cred.SecretText
        Ok "secret created, expires $($cred.EndDateTime.ToString('yyyy-MM-dd'))"
    }
} else {
    Warn "app already has a secret; its value cannot be read back. Use -NewSecret to rotate."
}

# --- 5. restrict mail to the one mailbox ------------------------------------

Step 5 "Restrict mail access to $Mailbox"
Connect-ExchangeOnline -ShowBanner:$false
$policy = Get-ApplicationAccessPolicy -ErrorAction SilentlyContinue |
          Where-Object { $_.AppId -eq $app.AppId }
if ($policy) {
    Skip "policy exists, scope $($policy.ScopeName)"
} elseif ($PSCmdlet.ShouldProcess($Mailbox, 'Create ApplicationAccessPolicy')) {
    New-ApplicationAccessPolicy -AppId $app.AppId -PolicyScopeGroupId $Mailbox `
        -AccessRight RestrictAccess `
        -Description "Scan ingest routine - $Mailbox only" | Out-Null
    Ok 'policy created'
}

# --- 6. write on the jobs site only -----------------------------------------

Step 6 "Write permission on $JobsSite"
Connect-PnPOnline -Url $JobsSite -Interactive
$granted = Get-PnPAzureADAppSitePermission -ErrorAction SilentlyContinue |
           Where-Object { $_.Apps -match $app.AppId }
if ($granted) {
    Skip "site permission exists ($($granted.Roles))"
} elseif ($PSCmdlet.ShouldProcess($JobsSite, 'Grant Write')) {
    # Write, not Read: the routine creates folders and uploads files. This is a
    # SITE-level grant -- Graph has no per-library granularity -- so it covers
    # every library on the jobs site, not only Completed Jobs.
    Grant-PnPAzureADAppSitePermission -AppId $app.AppId -DisplayName $AppName `
        -Site $JobsSite -Permissions Write | Out-Null
    Ok 'write granted on the jobs site'
}

# --- 7. verify and report ---------------------------------------------------

Step 7 'Verification'
if ($WhatIfPreference) { Warn '-WhatIf: nothing was changed, nothing to verify'; return }

Write-Host '    Waiting 30s for the access policy to propagate...' -ForegroundColor DarkGray
Start-Sleep -Seconds 30

$allow = Test-ApplicationAccessPolicy -Identity $Mailbox -AppId $app.AppId
$deny  = Test-ApplicationAccessPolicy -Identity $ControlMailbox -AppId $app.AppId
Write-Host "    $Mailbox -> $($allow.AccessCheckResult)  (want: Granted)"
Write-Host "    $ControlMailbox -> $($deny.AccessCheckResult)  (want: Denied)"

if ($allow.AccessCheckResult -eq 'Granted' -and $deny.AccessCheckResult -eq 'Denied') {
    Ok 'mail access is working AND contained'
} else {
    Warn 'NOT both Granted and Denied. Policy propagation can take a few minutes -'
    Warn 'wait and re-run Test-ApplicationAccessPolicy before assuming failure.'
    Warn 'Do not leave it unresolved: until Denied appears, the app can read every mailbox.'
}

Write-Host "`nSet these on the Midland cloud environment:" -ForegroundColor Cyan
Write-Host "  SCAN_GRAPH_TENANT_ID=$((Get-MgContext).TenantId)"
Write-Host "  SCAN_GRAPH_CLIENT_ID=$($app.AppId)"
if ($secret) {
    Write-Host "  SCAN_GRAPH_CLIENT_SECRET=$secret"
    Warn 'The secret is shown once and cannot be retrieved again. Copy it now.'
} else {
    Write-Host '  SCAN_GRAPH_CLIENT_SECRET=<existing secret, or re-run with -NewSecret>'
}
Write-Host "`nThen: python3 tools/scan_ingest.py --self-test" -ForegroundColor Cyan
