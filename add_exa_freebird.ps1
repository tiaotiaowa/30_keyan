$file = "C:\Users\60207\.claude.json"
$content = Get-Content $file -Raw

# 查找并替换 pdf-reader 配置块
$oldPattern = '(?s)      "pdf-reader": \{[^}]+\}    \},'
$newText = '      "pdf-reader": {
        "type": "stdio",
        "command": "npx",
        "args": [
          "@fabriqa.ai/pdf-reader-mcp"
        ],
        "env": {}
      },
      "exa": {
        "type": "stdio",
        "command": "npx",
        "args": [
          "-y",
          "exa-mcp-server"
        ],
        "env": {
          "EXA_API_KEY": "8e7f0292-a70b-4cc7-9de0-ae70e3fac968"
        }
      },
      "freebird": {
        "type": "stdio",
        "command": "npx",
        "args": [
          "-y",
          "@dannyboy2042/freebird-mcp"
        ]
      }
    },'

$content = $content -replace $oldPattern, $newText
Set-Content $file $content -NoNewline

Write-Host "Exa and Freebird MCP configurations added successfully!"
Write-Host "Please restart Claude Code for changes to take effect."
