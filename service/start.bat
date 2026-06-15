@echo off
REM HMR 服务启动脚本（Windows）
REM 如果 HMR 没 pip install，把下面 HMR_PATH 改成你的实际路径并取消注释
REM set PYTHONPATH=C:\hmr

set HMR_STORAGE_PATH=./hmr_data
set HMR_HOST=127.0.0.1
set HMR_PORT=8077

echo 启动 HMR 服务...
python server.py
