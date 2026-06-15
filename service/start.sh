#!/bin/bash
# HMR 服务启动脚本（Linux/Mac）
# 如果 HMR 没 pip install，取消下面注释并改成实际路径
# export PYTHONPATH=/path/to/hmr

export HMR_STORAGE_PATH="./hmr_data"
export HMR_HOST="127.0.0.1"
export HMR_PORT="8077"

echo "启动 HMR 服务..."
python server.py
