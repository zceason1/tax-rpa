import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from tax_rpa.jobs.retention import RetentionCleaner, RetentionPolicy, RetentionReport


def cleanup_artifacts(
    artifacts_root: str | Path = Path("artifacts"),
    *,
    policy: RetentionPolicy | None = None,
    now: Callable[[], datetime] | None = None,
) -> RetentionReport:
    """按保留策略清理过期产物目录。"""
    root = Path(artifacts_root)
    combined = RetentionReport()
    cleanup_roots = _cleanup_roots(root)
    for cleanup_root in cleanup_roots:
        report = RetentionCleaner(cleanup_root, policy=policy, now=now).cleanup()
        combined.deleted_jobs.extend(report.deleted_jobs)
        combined.preserved_jobs.extend(report.preserved_jobs)
        combined.skipped_jobs.extend(report.skipped_jobs)
    return combined


def _cleanup_roots(root: Path) -> list[Path]:
    """计算需要参与清理的新版和旧版产物根目录。"""
    jobs_root = root / "jobs"
    if root.name == "jobs":
        return [root]
    return [jobs_root, root]


def parse_args() -> argparse.Namespace:
    """解析命令行参数，返回入口函数使用的参数对象。"""
    parser = argparse.ArgumentParser(
        description="Delete expired RPA artifact evidence according to retention policy."
    )
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Artifact root containing jobs/ and legacy person_import_* runs.",
    )
    parser.add_argument(
        "--success-days",
        type=int,
        default=30,
        help="Days to retain succeeded artifacts.",
    )
    parser.add_argument(
        "--failed-days",
        type=int,
        default=90,
        help="Days to retain failed artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    """命令行入口，解析参数并触发对应业务流程。"""
    args = parse_args()
    report = cleanup_artifacts(
        args.artifacts_root,
        policy=RetentionPolicy(
            success_days=args.success_days,
            failed_days=args.failed_days,
        ),
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
