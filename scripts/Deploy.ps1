param([Parameter(Mandatory=$true)][string]$BudgetEmail,[string]$StackName='ieai-alp',[string]$Region='us-east-1')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$taskSam=if (Get-Command sam -ErrorAction SilentlyContinue) { (Get-Command sam).Source } else { 'C:/Program Files/Amazon/AWSSAMCLI/bin/sam.cmd' }
& $taskSam validate --lint --template-file infra/template.yaml --region $Region
if ($LASTEXITCODE -ne 0) { throw 'SAM validation failed' }
& $taskSam build --template-file infra/template.yaml
if ($LASTEXITCODE -ne 0) { throw 'SAM build failed' }
& $taskSam deploy --template-file .aws-sam/build/template.yaml --stack-name $StackName --resolve-s3 --s3-prefix $StackName --capabilities CAPABILITY_IAM --region $Region --no-fail-on-empty-changeset --parameter-overrides "AllowedOrigin=http://127.0.0.1:8000" "AppName=$StackName" "BudgetEmail=$BudgetEmail"
if ($LASTEXITCODE -ne 0) { throw 'SAM deployment failed' }
& '.venv/Scripts/python.exe' scripts/cloud_demo.py --region $Region --stack $StackName
