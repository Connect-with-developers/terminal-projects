import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generated"))
from palindrome import is_palindrome, count_vowels

def test_palindrome_true():
    assert is_palindrome("Racecar") is True

def test_palindrome_false():
    assert is_palindrome("hello") is False

def test_palindrome_sentence():
    assert is_palindrome("A man a plan a canal Panama") is True

def test_vowels():
    assert count_vowels("hello") == 2
