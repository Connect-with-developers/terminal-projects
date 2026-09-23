import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))
from _tdd1 import is_palindrome
def test_tdd_pal():
    assert is_palindrome("Racecar") is True
