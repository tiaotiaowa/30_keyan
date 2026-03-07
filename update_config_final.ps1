# 等待文件稳定
Start-Sleep -Seconds 1

# 读取文件
$file = "C:\Users\60207\.claude.json"
$content = Get-Content $file -Raw

# 查找并替换 pdf-reader 配置块
$searchText = '    "pdf-reader": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@fabriqa.ai/pdf-reader-mcp"
      ],
      "env": {}
    }
  },'

$replaceText = '    "pdf-reader": {
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

# 执行替换
$newContent = $content.Replace($searchText, $replaceText)

# 写回文件
Set-Content $file $newContent -NoNewline

Write-Host "============================================="
Write-Host "配置更新完成！"
Write-Host "============================================="
Write-Host ""
Write-Host "已添加的 MCP 服务器:"
Write-Host "  1. Exa MCP (API Key: 8e7f0292-a70b-4cc7-9de0-ae70e3fac968)"
Write-Host "  2. Freebird MCP"
Write-Host ""
Write-Host "请重启 Claude Code 使配置生效。"
Write-Host "============================================="
