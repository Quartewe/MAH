import sys

from typing import List
from pathlib import Path

from maa.resource import Resource
from maa.tasker import Tasker, LoggingLevelEnum


def check(dirs: List[Path]) -> bool:
    resource = Resource()

    print(f"[DEBUG] Checking {len(dirs)} directories...")

    for dir in dirs:
        print(f"[DEBUG] Checking {dir}...")
        status = resource.post_bundle(dir).wait().status
        if not status.succeeded:
            print(f"[DEBUG] Failed to check {dir}.")
            return False

    print("[DEBUG] All directories checked.")
    return True


def main():
    if len(sys.argv) < 2:
        print("[DEBUG] Usage: python check_resource.py <directories...>")
        sys.exit(1)

    Tasker.set_stdout_level(LoggingLevelEnum.All)

    dirs = [Path(arg) for arg in sys.argv[1:]]
    if not check(dirs):
        sys.exit(1)


if __name__ == "__main__":
    main()
