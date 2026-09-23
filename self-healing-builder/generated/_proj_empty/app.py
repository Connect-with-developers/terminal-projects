"""Auto-generated project file."""
from __future__ import annotations

"""Main app for: """
from store import load, save

def main() -> str:
    """Entry point."""
    data = load()
    save(data)
    return "ok"

if __name__ == "__main__":
    print(main())
