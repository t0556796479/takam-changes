from app.core.normalize import normalize


def test_punctuation_quotes_and_dashes_are_ignored():
    assert normalize("''הרכב''/''כלי הרכב'' - בהתאם.") == normalize('"הרכב" כלי הרכב, בהתאם')


def test_niqqud_and_direction_marks_are_ignored():
    assert normalize("גנֵיבת‏ הרכב") == normalize("גניבת הרכב")


def test_real_wording_change_is_kept():
    assert normalize("בדיווח אודות") != normalize("בדיווח על אודות")
