$content = Get-Content "C:\Users\60207\.claude.json" -Raw

if ($content -match '"exa"') {
    Write-Host "✓ Exa MCP configuration found!"
} else {
    Write-Host "✗ Exa MCP configuration NOT found"
}

if ($content -match '"freebird"') {
    Write-Host "✓ Freebird MCP configuration found!"
} else {
    Write-Host "✗ Freebird MCP configuration NOT found"
}

# 搜索 mcpServers 部分来验证
if ($content -match '"mcpServers":\s*\{[^}]*"exa"') {
    Write-Host "✓ Exa is in mcpServers section!"
} else {
    Write-Host "✗ Exa is NOT in mcpServers section"
}
