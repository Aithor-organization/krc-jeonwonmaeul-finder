"""Vercel 배포 진입점.

Vercel Python 런타임은 진입점을 정해진 위치에서만 찾는다 —
프로젝트 루트의 app.py/index.py/server.py/main.py/wsgi.py/asgi.py,
또는 src/·app/·api/ 바로 안 (https://vercel.com/docs/functions/runtimes/python).

실제 앱은 app/backend/main.py로 한 단계 더 깊어서 검색 대상이 아니다.
그렇다고 Root Directory를 app/backend로 잡으면 app/frontend가 루트 밖으로
나가 화면이 통째로 빠지므로, Root은 저장소 루트로 두고 이 파일이 다리를 놓는다.

app/backend를 sys.path에 넣는 이유: main.py가 `import config`처럼 평평한
임포트를 쓰기 때문. 로컬 실행(`uvicorn main:app`)과 동일한 조건을 만든다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent / "app" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402  (sys.path 조정 후에만 임포트 가능)

__all__ = ["app"]
