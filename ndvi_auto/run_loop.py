import os
import subprocess
import time


def main() -> None:
    interval_minutes = int(os.getenv("UPDATE_INTERVAL_MINUTES", "1440"))
    interval_seconds = max(60, interval_minutes * 60)

    while True:
        try:
            subprocess.run(
                ["python", "/app/download_and_publish.py"],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"[ERROR] Update failed: {exc}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
