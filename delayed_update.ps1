# 等待文件稳定
Write-Host "等待文件稳定..."
Start-Sleep -Seconds 3

# 读取文件
$file = "C:\Users\60207\.claude.json"
$content = Get-Content $file -Raw
Write-Host "文件已读取"

# 查找 pdf-reader 配置
if ($content -match '"pdf-reader":\s*\{[^}]+\}\s+\},\s+"githubRepoPaths"') {
    Write-Host "找到目标位置"

    # 构建新的配置
    $oldBlock = '    "pdf-reader": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@fabriqa.ai/pdf-reader-mcp"
      ],
      "env": {}
    }
  },'

    $newBlock = '    "pdf-reader": {
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

    $newContent = $content.Replace($oldBlock, $newBlock)

    # 备份原文件
    $backupFile = "$file.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $file $backupFile
    Write-Host "已备份到: $backupFile"

    # 写入新内容
    Set-Content $file $newContent -NoNewline
    Write-Host "配置已更新!"

    # 验证
    Start-Sleep -Seconds 1
    $verifyContent = Get-Content $file -Raw
    if ($verifyContent -match '"exa"') {
        Write-Host "✓ Exa MCP 配置成功!"
    } else {
        Write-Host "✗ Exa MCP 配置可能失败"
    }

    if ($verifyContent -match '"freebird"') {
        Write-Host "✓ Freebird MCP 配置成功!"
    } else {
        Write-Host "✗ Freebird MCP 配置可能失败"
    }

} else {
    Write-Host "未找到目标位置，请检查文件格式"
}
