from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.email import EmailService


def main() -> int:
    ok, message = EmailService().check_connection()
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
