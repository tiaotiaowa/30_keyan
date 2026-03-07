$file = "C:\Users\60207\.claude.json"
$text = Get-Content $file -Raw

$old = '    "pdf-reader": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@fabriqa.ai/pdf-reader-mcp"
      ],
      "env": {}
    }
  },'

$new = '    "pdf-reader": {
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

$result = $text.Replace($old, $new)
$result | Set-Content $file -NoNewline

Write-Host "Done"
