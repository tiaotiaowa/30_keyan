$content = Get-Content "C:\Users\60207\.claude.json" -Raw

Write-Host "检查 Exa MCP 配置..."
if ($content -match '"exa"') {
    Write-Host "✓ 成功：Exa MCP 已配置"
} else {
    Write-Host "✗ 失败：Exa MCP 未配置"
}

Write-Host "`n检查 Freebird MCP 配置..."
if ($content -match '"freebird"') {
    Write-Host "✓ 成功：Freebird MCP 已配置"
} else {
    Write-Host "✗ 失败：Freebird MCP 未配置"
}

Write-Host "`n检查 API Key..."
if ($content -match '8e7f0292-a70b-4cc7-9de0-ae70e3fac968') {
    Write-Host "✓ 成功：API Key 已配置"
} else {
    Write-Host "✗ 失败：API Key 未配置"
}
