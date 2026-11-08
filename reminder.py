"""Independent source and PyInstaller reminder entry point (no GUI or Ollama)."""
from app.reminder.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
