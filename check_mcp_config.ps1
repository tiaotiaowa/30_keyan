$lines = Get-Content 'C:\Users\60207\.claude.json'
$found = $false
for($i=0; $i -lt $lines.Count; $i++) {
    if($lines[$i] -match '"pdf-reader"') {
        Write-Host "Found pdf-reader at line $i"
        for($j=$i; $j -lt [Math]::Min($i+30, $lines.Count); $j++) {
            Write-Host $lines[$j]
        }
        $found = $true
        break
    }
}

if(-not $found) {
    Write-Host "pdf-reader configuration not found"
}
