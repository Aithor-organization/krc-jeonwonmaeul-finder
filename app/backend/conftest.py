"""pytest 경로 설정 — backend 모듈을 sys.path에 추가."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
