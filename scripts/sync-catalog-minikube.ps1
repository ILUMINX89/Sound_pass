$ErrorActionPreference = 'Stop'
$importerCommit = '5415c9535c073dc7077d170c414b546136344d79'
$image = 'soundpass-catalog-sync:5415c95'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$buildDir = Join-Path ([IO.Path]::GetTempPath()) ('soundpass-catalog-' + [guid]::NewGuid().ToString('N'))

function Invoke-Checked {
    $command = $args[0]
    $arguments = $args | Select-Object -Skip 1
    & $command @arguments
    if ($LASTEXITCODE -ne 0) { throw "Fallo $($args[0]) (codigo $LASTEXITCODE)." }
}

Push-Location $repo
try {
    Invoke-Checked kubectl --context=minikube -n soundpass rollout status statefulset/soundpass-db --timeout=120s
    git rev-parse --verify --quiet "${importerCommit}^{commit}" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Checked git fetch origin $importerCommit
    }

    New-Item -ItemType Directory -Path $buildDir | Out-Null
    $archive = Join-Path $buildDir 'source.tar'
    Invoke-Checked git archive "--output=$archive" $importerCommit backend/Dockerfile backend/requirements.txt backend/src
    Invoke-Checked tar.exe -xf $archive -C $buildDir
    Invoke-Checked minikube image build -t $image (Join-Path $buildDir 'backend')

    Get-Content database/migrations/002_ticketmaster_catalog.sql -Raw |
        kubectl --context=minikube -n soundpass exec -i soundpass-db-0 -- psql -U soundpass_user -d soundpass -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw 'Fallo la migracion de Ticketmaster.' }

    $job = Invoke-Checked kubectl --context=minikube -n soundpass create -f k8s/catalog-sync-job.yaml -o name
    Write-Host "Job: $job"
    kubectl --context=minikube -n soundpass wait --for=condition=complete $job --timeout=10m
    $result = $LASTEXITCODE
    Invoke-Checked kubectl --context=minikube -n soundpass logs $job
    if ($result -ne 0) { throw "El Job $job no se completo dentro del plazo." }
} finally {
    if (Test-Path -LiteralPath $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }
    Pop-Location
}
