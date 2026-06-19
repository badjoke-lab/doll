"""Run the IMP-012 model-independent continuity acceptance test."""

from __future__ import annotations

import json

from imp_012_common import TEST_ID, check_environment, parse_arguments, utc_now
from imp_012_scenario import run


def main() -> int:
    arguments = parse_arguments()
    try:
        check_environment(arguments)
        report = run(arguments)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "test_id": TEST_ID,
                    "result": "fail",
                    "commit_sha": arguments.commit_sha,
                    "completed_at": utc_now(),
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
