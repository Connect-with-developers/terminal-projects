"""Auto-generated project file."""
from __future__ import annotations

"""Main app for: Create a todo task manager with:
- class TodoList with methods add(title), complete(task_id), remove(task_id), list_all("""
from store import load, save

def main() -> str:
    """Entry point."""
    data = load()
    save(data)
    return "ok"

if __name__ == "__main__":
    print(main())
