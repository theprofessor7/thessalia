# Installation de Thessalia sous Windows (à relancer sans risque, par exemple après une mise à jour).
# Double-cliquer sur installer.bat, qui lance ce script.
#   -Lecteur oui|non : installer ou non le lecteur d'écriture (TrOCR, ~2 Go) sans poser la question
param([ValidateSet("", "oui", "non")][string]$Lecteur = "")

$ErrorActionPreference = "Continue"   # codes de retour vérifiés un par un
Set-Location -LiteralPath $PSScriptRoot

function Arret($message) {
    Write-Host ""
    Write-Host "ÉCHEC : $message" -ForegroundColor Red
    exit 1
}

Write-Host "=== Thessalia : installation dans $PSScriptRoot"
if ($PSScriptRoot.Contains('$')) {
    Arret "le chemin du dossier contient « $ », ce que l'installation de Python refuse. Cloner Thessalia ailleurs, par exemple C:\Thessalia."
}

# 1. Python 3.10 ou plus récent (lanceur « py » de python.org, sinon « python »)
$python = $null
foreach ($c in @("py -3", "python")) {
    $exe, $opt = $c.Split(" ")
    try {
        $v = & $exe @($opt | Where-Object { $_ }) -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -and [version]$v -ge [version]"3.10") { $python = @($exe) + @($opt | Where-Object { $_ }); break }
    } catch {}
}
if (-not $python) {
    Arret "Python 3.10 ou plus récent est introuvable. L'installer depuis https://www.python.org/downloads/ (cocher « Add python.exe to PATH »), puis relancer."
}
Write-Host "Python $v trouvé."

# 2. Environnement propre à Thessalia (.venv), sans toucher au reste du PC
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Création de l'environnement .venv…"
    & $python[0] @($python | Select-Object -Skip 1) -m venv .venv
    if ($LASTEXITCODE -ne 0) { Arret "création de .venv impossible" }
}
$py = ".venv\Scripts\python.exe"

# 3. Thessalia et l'application ; le lecteur d'écriture est facultatif (gros téléchargement)
if (-not $Lecteur) {
    $deja = & $py -c "import importlib.util as u; print(bool(u.find_spec('torch') and u.find_spec('transformers')))" 2>$null
    if ($deja -eq "True") { $Lecteur = "oui" }
    else {
        Write-Host ""
        Write-Host "Lecteur d'écriture (réponses courtes lues automatiquement) : ~2 Go à télécharger."
        Write-Host "Sans lui, tout fonctionne, les réponses courtes se corrigent à la main dans l'outil."
        $r = Read-Host "L'installer ? (o/N)"
        $Lecteur = if ($r -match "^[oOyY]") { "oui" } else { "non" }
    }
}
$extras = if ($Lecteur -eq "oui") { "serveur,trocr" } else { "serveur" }
Write-Host "Installation des bibliothèques ($extras), quelques minutes…"
# Comptes Windows gérés de l'école (« $IM7000-… ») : un « $ » dans le dossier temporaire fait échouer
# setuptools (« invalid variable ») ; on travaille dans un dossier temporaire à nous, sans « $ »
$tmp = Join-Path $PSScriptRoot ".venv\tmp"
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TEMP = $tmp; $env:TMP = $tmp
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -e ".[$extras]"
if ($LASTEXITCODE -ne 0) { Arret "pip install a échoué (connexion internet ? message ci-dessus)" }

# 4. Contrôle : l'application démarre-t-elle ?
& $py -c "import flask, typst, cv2, pymupdf; from thessalia.serve import create_app; create_app([], 'data/correction.sqlite', examens='examens')"
if ($LASTEXITCODE -ne 0) { Arret "l'application ne se charge pas (message ci-dessus)" }

Write-Host ""
Write-Host "Installation terminée. Pour lancer Thessalia : double-cliquer sur Thessalia.bat" -ForegroundColor Green
Write-Host "Facultatif, pour la préparation de nuit (code manuscrit) : Ollama, voir docs\MODE_EMPLOI.md"
