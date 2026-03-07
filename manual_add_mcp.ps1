# 读取文件内容
$content = Get-Content "C:\Users\60207\.claude.json" -Raw

# 定义要查找和替换的文本
$oldText = '      "pdf-reader": {
        "type": "stdio",
        "command": "npx",
        "args": [
          "@fabriqa.ai/pdf-reader-mcp"
        ],
        "env": {}
      }
    },
    "githubRepoPaths": {'

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
    },
    "githubRepoPaths": {'

# 执行替换
$newContent = $content.Replace($oldText, $newText)

# 写回文件
Set-Content "C:\Users\60207\.claude.json" $newContent -NoNewline

Write-Host "MCP configuration added successfully!"
Write-Host "Exa and Freebird MCP servers are now configured."
