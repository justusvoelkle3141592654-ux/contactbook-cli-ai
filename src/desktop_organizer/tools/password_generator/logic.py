"""Cryptographically secure passwords and passphrases. Nothing is ever stored."""

from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from desktop_organizer.core.paths import resources_dir

AMBIGUOUS = set("Il1O0o|`'\"")
DEFAULT_SYMBOLS = "!#$%&*+-=?@^_~.,:;()[]{}<>/"


@dataclass(frozen=True)
class PasswordOptions:
    length: int = 20
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    symbol_set: str = DEFAULT_SYMBOLS
    exclude_ambiguous: bool = True
    require_each: bool = True


@dataclass(frozen=True)
class PassphraseOptions:
    words: int = 6
    separator: str = "-"
    capitalize: bool = True
    add_number: bool = True
    language: str = "en"


def alphabet_groups(options: PasswordOptions) -> list[str]:
    groups = []
    if options.lower:
        groups.append(string.ascii_lowercase)
    if options.upper:
        groups.append(string.ascii_uppercase)
    if options.digits:
        groups.append(string.digits)
    if options.symbols and options.symbol_set:
        groups.append("".join(dict.fromkeys(options.symbol_set)))
    if options.exclude_ambiguous:
        groups = ["".join(c for c in g if c not in AMBIGUOUS) for g in groups]
    return [g for g in groups if g]


def generate_password(options: PasswordOptions) -> str:
    groups = alphabet_groups(options)
    if not groups:
        raise ValueError("no_characters")
    alphabet = "".join(groups)
    length = max(options.length, len(groups) if options.require_each else 1)
    rng = secrets.SystemRandom()
    while True:
        chars = [secrets.choice(alphabet) for _ in range(length)]
        if not options.require_each or all(any(c in g for c in chars) for g in groups):
            rng.shuffle(chars)
            return "".join(chars)


def password_entropy(options: PasswordOptions) -> float:
    pool = len("".join(alphabet_groups(options)))
    return options.length * math.log2(pool) if pool > 1 else 0.0


@lru_cache(maxsize=4)
def wordlist(language: str) -> tuple[str, ...]:
    path: Path = resources_dir() / "wordlists" / f"{language if language in ('de', 'en') else 'en'}.txt"
    words = tuple(w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip())
    return tuple(dict.fromkeys(words))


def generate_passphrase(options: PassphraseOptions) -> str:
    words = wordlist(options.language)
    chosen = [secrets.choice(words) for _ in range(max(1, options.words))]
    if options.capitalize:
        chosen = [w[:1].upper() + w[1:] for w in chosen]
    if options.add_number:
        position = secrets.randbelow(len(chosen))
        chosen[position] = f"{chosen[position]}{secrets.randbelow(100)}"
    return options.separator.join(chosen)


def passphrase_entropy(options: PassphraseOptions) -> float:
    bits = options.words * math.log2(len(wordlist(options.language)))
    if options.add_number:
        bits += math.log2(100) + math.log2(max(1, options.words))
    return bits


def strength(bits: float) -> str:
    """very_weak, weak, fair, strong, very_strong (thresholds follow common guidance)."""
    if bits < 28:
        return "very_weak"
    if bits < 36:
        return "weak"
    if bits < 60:
        return "fair"
    if bits < 100:
        return "strong"
    return "very_strong"


def crack_time_label(bits: float, guesses_per_second: float = 1e10) -> tuple[str, int]:
    """Rough average time for an offline attack: (unit key, amount)."""
    seconds = 2 ** (bits - 1) / guesses_per_second
    for unit, size in (("years", 31_557_600), ("days", 86_400), ("hours", 3600), ("minutes", 60)):
        if seconds >= size:
            amount = seconds / size
            if unit == "years" and amount >= 1e6:
                return "millions_of_years", 0
            return unit, int(amount)
    return "seconds", int(seconds)
