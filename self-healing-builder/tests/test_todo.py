import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generated"))
from todo import TodoList

def test_add():
    t = TodoList()
    item = t.add("Write code")
    assert item["title"] == "Write code"
    assert item["done"] is False

def test_complete():
    t = TodoList()
    t.add("A")
    assert t.complete(1) is True
    assert t.list_all()[0]["done"] is True

def test_remove():
    t = TodoList()
    t.add("A")
    assert t.remove(1) is True
    assert len(t.list_all()) == 0

def test_complete_missing():
    t = TodoList()
    assert t.complete(99) is False
