import string

import pytest

from desktop_organizer.tools.password_generator.logic import (
    AMBIGUOUS,
    PassphraseOptions,
    PasswordOptions,
    crack_time_label,
    generate_passphrase,
    generate_password,
    passphrase_entropy,
    password_entropy,
    strength,
    wordlist,
)


def test_password_length_and_groups() -> None:
    for _ in range(200):
        pw = generate_password(PasswordOptions(length=12))
        assert len(pw) == 12
        assert any(c in string.ascii_lowercase for c in pw)
        assert any(c in string.ascii_uppercase for c in pw)
        assert any(c in string.digits for c in pw)
        assert not set(pw) & AMBIGUOUS


def test_only_digits_and_no_groups() -> None:
    pw = generate_password(PasswordOptions(length=8, lower=False, upper=False, symbols=False))
    assert pw.isdigit()
    with pytest.raises(ValueError):
        generate_password(PasswordOptions(lower=False, upper=False, digits=False, symbols=False))


def test_custom_symbols_are_respected() -> None:
    options = PasswordOptions(length=40, lower=False, upper=False, digits=False, symbol_set="#+")
    assert set(generate_password(options)) <= {"#", "+"}


def test_passwords_differ() -> None:
    assert len({generate_password(PasswordOptions()) for _ in range(50)}) == 50


def test_entropy_and_strength() -> None:
    bits = password_entropy(PasswordOptions(length=20))
    assert 120 < bits < 135
    assert strength(bits) == "very_strong"
    assert strength(30) == "weak"
    assert crack_time_label(20) == ("seconds", 0)
    assert crack_time_label(200)[0] == "millions_of_years"


@pytest.mark.parametrize("language", ["de", "en"])
def test_passphrase(language: str) -> None:
    options = PassphraseOptions(words=5, separator="-", language=language)
    phrase = generate_passphrase(options)
    assert phrase.count("-") == 4
    assert len(wordlist(language)) >= 7000
    assert passphrase_entropy(options) > 60
