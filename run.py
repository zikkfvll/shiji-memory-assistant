import argparse
import os
from pathlib import Path
import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='拾记本地原型；默认仅本机可访问')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).parent / 'data')
    args = parser.parse_args()
    os.environ['MEMORY_DATA_DIR'] = str(args.data_dir.resolve())
    uvicorn.run('backend.app:create_app', factory=True, host='127.0.0.1', port=args.port, access_log=False)
