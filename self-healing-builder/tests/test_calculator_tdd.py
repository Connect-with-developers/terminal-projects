import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))
from calculator import add, divide
def test_tdd_add():
    assert add(2, 3) == 5
def test_tdd_divide():
    assert divide(10, 2) == 5
