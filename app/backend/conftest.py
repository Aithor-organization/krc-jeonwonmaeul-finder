"""pytest 경로 설정 + 기본 sample-mode 강제."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

# pytest 훅 인자명이 `config`로 고정돼 있어 앱 모듈은 별칭으로 import한다.
import config as app_config  # noqa: E402  (sys.path 설정 후 import)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: 실제 외부 API를 호출하는 테스트")


@pytest.fixture(autouse=True)
def _force_sample_mode(request):
    """테스트는 기본적으로 sample-mode로 고정한다.

    .env를 source한 셸에서 pytest를 돌리면 KRC_SERVICE_KEY가 잡혀
    전 테스트가 실 API를 호출하게 된다(비결정성 + 쿼터 소모). 실 API를 쓰는
    테스트는 `@pytest.mark.live`를 달아 이 고정에서 빠져나간다.
    """
    if request.node.get_closest_marker("live"):
        yield
        return
    saved = app_config.SAMPLE_MODE
    app_config.SAMPLE_MODE = True
    try:
        yield
    finally:
        app_config.SAMPLE_MODE = saved
