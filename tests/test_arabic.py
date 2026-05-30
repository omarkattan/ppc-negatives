from negative_keywords.arabic import contains_arabic, normalise, tokens


def test_digit_folding():
    assert normalise("اشتري ٣ ابواب") == normalise("اشتري 3 ابواب")


def test_alef_folding():
    # أحمد and احمد should normalise to the same key
    assert normalise("أحمد") == normalise("احمد")


def test_taa_marbuta_folding():
    assert normalise("شركة") == normalise("شركه")


def test_diacritics_and_tatweel_stripped():
    assert normalise("عــــطر") == "عطر"
    assert normalise("عَطْر") == "عطر"


def test_contains_arabic():
    assert contains_arabic("buy عطور")
    assert not contains_arabic("buy perfume")


def test_tokens_mixed_script():
    toks = tokens("buy عطور dubai 2024")
    assert "buy" in toks and "dubai" in toks and "2024" in toks
    assert any(contains_arabic(t) for t in toks)
