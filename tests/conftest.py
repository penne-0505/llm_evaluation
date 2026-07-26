"""テスト間でプロセス共有状態を分離する。

`core` のストア類はローカル単一プロセス前提の classmethod シングルトンであり、
設計としては妥当だが、テストプロセスでは 1 プロセスに全テストが同居するため
クラス変数がテストをまたいで蓄積する。

実測した具体例（このファイル追加前）:

- `ProviderRateLimiter._timestamps` は `defaultdict(deque)` のクラス変数。
  `BenchmarkEngine` の subject / judge 呼び出しは毎回 `acquire()` するため、
  stub adapter を使う engine テストでも provider id `"unknown"`
  （`_provider_id_for_model` のフォールバック / 既定 20 req per 60s）へ
  タイムスタンプが積まれ続ける。60 秒窓が埋まると後続テストが実際に待たされ、
  `test_no_fixed_sleep_between_successful_runs` が
  `asyncio.sleep` の呼び出し 0 回を検証できなくなる。
  `tests/test_benchmark_engine.py` を単独実行しても再現するため、
  ファイル間漏れではなくファイル内蓄積であることを確認済み。

そのため、各テストの前後で「テストが書き換えうるプロセス共有状態」を既定へ戻す。
本番挙動は変更しない。ここに足すのは、テストが汚しうる global state に限る。
"""

from __future__ import annotations

import pytest

from core.active_run_registry import ActiveRunRegistry
from core.provider_rate_limiter import ProviderRateLimiter
from core.rate_limit_store import RateLimitStore


def _reset_process_globals() -> None:
    # 窓のタイムスタンプと差し替え済み時計を捨てる。
    # `_lock` も None へ戻るため、次のテストの event loop で作り直される
    # （閉じた loop に束縛された asyncio.Lock を持ち越さない）。
    ProviderRateLimiter.reset_for_tests()
    ActiveRunRegistry.reset_for_tests()
    # 既定は None（AppPaths 側へフォールバック）。
    # テストが tmp path を差したまま失敗しても次テストへ持ち越さない。
    RateLimitStore.FILE_PATH = None


@pytest.fixture(autouse=True)
def reset_shared_process_state():
    """全テストの前後でプロセス共有状態を既定へ戻す。

    autouse かつ引数なしのため、`unittest.TestCase` 派生のテストにも適用される。
    fixture の setup は `setUp()` より前、teardown は `tearDown()` より後に走るので、
    テスト側の明示的な `reset_for_tests()` とは競合しない。
    """
    _reset_process_globals()
    yield
    _reset_process_globals()
