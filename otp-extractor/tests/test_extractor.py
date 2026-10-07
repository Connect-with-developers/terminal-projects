from extractor import best_code, extract_otp


def test_six_digit():
    assert best_code("Your Devin verification code is 482913. Expires in 10 min.") == "482913"


def test_dashed():
    assert best_code("Login code: ABC-123, do not share.") == "ABC-123"


def test_ignores_year():
    r = extract_otp("Copyright 2025. Your OTP is 778899.", top_k=5)
    assert r[0]["code"] == "778899"


def test_no_code():
    assert best_code("Hello, see you tomorrow!") is None
