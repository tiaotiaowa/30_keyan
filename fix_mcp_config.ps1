$file = "C:\Users\60207\.claude.json"
$lines = Get-Content $file

# 找到需要插入的位置
$newLines = @()
for($i=0; $i -lt $lines.Count; $i++) {
    $newLines += $lines[$i]

    # 在 pdf-reader 的 "env": {} } 之后，  }, 之前插入新配置
    if($lines[$i] -match '"env": \{\}') {
        # 检查后面两行是否是 } 和 },
        if($i+2 -lt $lines.Count -and $lines[$i+1] -match '^\s*\}\s*,\s*$' -and $lines[$i+2] -match '^  "githubRepoPaths"') {
            # 在这里插入新配置
            $indent = "      "
            $newLines += "    },"
            $newLines += "$indent`"exa`": {"
            $newLines += "$indent  `"type`": `"stdio`","
            $newLines += "$indent  `"command`": `"npx`","
            $newLines += "$indent  `"args`": ["
            $newLines += "$indent    `"-y`","
            $newLines += "$indent    `"exa-mcp-server`""
            $newLines += "$indent  ],"
            $newLines += "$indent  `"env`": {"
            $newLines += "$indent    `"EXA_API_KEY`": `"8e7f0292-a70b-4cc7-9de0-ae70e3fac968`""
            $newLines += "$indent  }"
            $newLines += "$indent},"
            $newLines += "$indent`"freebird`": {"
            $newLines += "$indent  `"type`": `"stdio`","
            $newLines += "$indent  `"command`": `"npx`","
            $newLines += "$indent  `"args`": ["
            $newLines += "$indent    `"-y`","
            $newLines += "$indent    `"@dannyboy2042/freebird-mcp`""
            $newLines += "$indent  ]"
            $newLines += "$indent}"
        }
    }
}

# 备份原文件
Copy-Item $file "$file.backup"

# 写入新内容
$newLines | Set-Content $file

Write-Host "Configuration updated successfully!"
Write-Host "Backup saved to: $file.backup"
