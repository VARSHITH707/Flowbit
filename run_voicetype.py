"""Entry point used by PyInstaller (the package's own __main__ uses relative imports)."""
import sys

from voicetype.app import main

if __name__ == "__main__":
    sys.exit(main())
