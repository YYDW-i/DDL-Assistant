"""Absolute imports are required by the frozen executable."""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
