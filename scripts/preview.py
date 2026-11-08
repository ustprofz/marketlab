"""Optional authoring preview. Production uses the uvicorn command in render.yaml."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if (ROOT / ".deps").is_dir():
    sys.path.insert(0, str(ROOT / ".deps"))
import uvicorn

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0")
parser.add_argument("--port", type=int, default=3000)
parser.add_argument("--strictPort", action="store_true")
args = parser.parse_args()
uvicorn.run("backend.main:app", host=args.host, port=args.port)
