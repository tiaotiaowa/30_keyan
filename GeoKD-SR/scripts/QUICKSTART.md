# 快速开始 - Qwen2.5模型下载

## 一行命令开始下载

```bash
cd D:\30_keyan\GeoKD-SR\scripts && python download_models.py
```

## 国内用户推荐（使用镜像加速）

```bash
cd D:\30_keyan\GeoKD-SR\scripts && set HF_ENDPOINT=https://hf-mirror.com && python download_models.py
```

## 交互提示

1. 选择模型：输入 `0` 下载所有，或 `1`、`2` 选择单个
2. 等待下载：会显示进度条
3. 自动验证：下载完成后自动测试

## 预计时间

- 1.5B模型（3GB）：5-10分钟
- 7B模型（14GB）：20-40分钟

## 下载位置

```
D:/30_keyan/GeoKD-SR/models/
├── Qwen2.5-1.5B-Instruct/
└── Qwen2.5-7B-Instruct/
```

## 验证环境

```bash
python test_download.py
```

## 详细文档

- `README.md` - 完整说明
- `USAGE.md` - 执行指南
- `PROJECT_SUMMARY.md` - 项目总结

## 状态

✓ 环境就绪
✓ 脚本已创建
✓ 等待执行
