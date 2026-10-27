param([string]$AwsProfile, [string]$Region='us-east-1')
$ErrorActionPreference='Stop'
if (-not $AwsProfile) { throw 'Pass the explicitly selected AWS profile. No profile is assumed.' }
if ($AwsProfile -ieq 'chakra') { throw 'The CHAKRA AWS profile is excluded from Sandhata work. Use a future separate AWS profile.' }
$template=Join-Path $PSScriptRoot 'foundation.json'
aws sts get-caller-identity --profile $AwsProfile --region $Region --query '{Account:Account,Arn:Arn}' --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS identity could not be verified.' }
aws cloudformation validate-template --profile $AwsProfile --region $Region --template-body "file://$template" --query '{Description:Description,Capabilities:Capabilities,Parameters:Parameters[*].ParameterKey}' --output json
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation validation failed.' }
Write-Output 'Read-only validation complete. No stack or billable infrastructure was created.'
