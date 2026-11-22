from __future__ import annotations

"""Read an ЕГЭ 8 statement as a small, checkable model.

The student's program is compared with this model instead of a generic recipe,
so a hint can point at the actual property: "the letter is used once while the
statement allows repeats", "the last letter is not pinned", and so on. Nothing
here knows or guesses the answer: the model only describes what the statement
asks to enumerate.
"""

import re
from dataclasses import dataclass, field

# EGE neighbours: «ЮЯ», «АБ», «АЯ». Yo cannot sit between E and Zh.
TRADITIONAL = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
CURRENT = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
SYMBOLS = "*+-."
GLAS_FULL = "АЕЁИОУЫЭЮЯ"
SOGL_FULL = "БВГДЖЗЙКЛМНПРСТФХЦЧШЩ"

BASES = {
    "двоичн": 2, "троичн": 3, "четверичн": 4, "пятеричн": 5, "шестеричн": 6,
    "семеричн": 7, "восьмеричн": 8, "девятеричн": 9, "десятичн": 10,
    "одиннадцатеричн": 11, "двенадцатеричн": 12, "тринадцатеричн": 13,
    "четырнадцатеричн": 14, "пятнадцатеричн": 15, "шестнадцатеричн": 16,
    "семнадцатеричн": 17, "восемнадцатеричн": 18, "девятнадцатеричн": 19,
    "двадцатеричн": 20,
}

LENGTH_WORDS = {
    "трех": 3, "четырех": 4, "пяти": 5, "шести": 6, "семи": 7, "восьми": 8,
    "девяти": 9, "десяти": 10, "одиннадцати": 11, "двенадцати": 12,
    "тринадцати": 13, "четырнадцати": 14, "пятнадцати": 15,
    "шестнадцати": 16, "семнадцати": 17, "восемнадцати": 18,
    "девятнадцати": 19, "двадцати": 20,
}

ORDINALS = {
    "перв": 1, "втор": 2, "трет": 3, "четверт": 4, "пят": 5, "шест": 6,
    "седьм": 7, "восьм": 8, "девят": 9, "десят": 10,
}


@dataclass
class Spec:
    """What one EGE 8 statement asks a program to enumerate."""

    length: int | None = None
    alphabet: list[str] = field(default_factory=list)
    base: int | None = None
    repeats: str = "any"  # any | once | exact
    source_word: str = ""
    first: list[str] | None = None
    last: list[str] | None = None
    distinct_digits: bool = False
    no_same_neighbours: bool = False
    alternating: bool = False
    alphabetical_neighbours: bool = False
    increasing: str = ""  # strict | weak | non_increasing | decreasing
    banned: dict[int, str] = field(default_factory=dict)
    forced: dict[int, str] = field(default_factory=dict)
    limit_cmp: tuple[str, int] | None = None
    min_double: bool = False
    max_even: int | None = None
    exact_even: int | None = None
    no_leading_zero: bool = False
    ceiling: int | None = None
    last_parity: str = ""
    parity_adjacent: bool = False
    requires_once: bool = False
    requires_double: bool = False
    prints_index: bool = False
    print_count: bool = False
    forbidden_subs: list[str] = field(default_factory=list)
    digit_once: list[str] = field(default_factory=list)
    balanced_vowels: bool = False
    sum_divisible: bool = False
    noun: str = "words"
    item: str = "слово"
    text: str = ""

    @property
    def has_filter(self) -> bool:
        return any(
            (
                self.repeats != "any",
                self.first,
                self.last,
                self.distinct_digits,
                self.no_same_neighbours,
                self.alternating,
                self.alphabetical_neighbours,
                self.increasing,
                self.banned,
                self.forced,
                self.limit_cmp,
                self.min_double,
                self.last_parity,
                self.parity_adjacent,
                self.max_even is not None,
                self.exact_even is not None,
                self.forbidden_subs,
                self.digit_once,
                self.balanced_vowels,
                self.sum_divisible,
            )
        )

    def pool(self) -> tuple[str, str]:
        """Character set the program should iterate over and its kind."""
        if self.alphabet:
            return "".join(self.alphabet), "letters"
        if self.base and self.noun != "numbers" and not re.search(r"\bпятна\w|\bтропин", self.text.lower()):
            return DIGITS[: self.base], "digits"
        if self.base:
            return DIGITS[: self.base], "digits"
        if self.noun == "trails":
            return SYMBOLS, "symbols"
        if self.noun in {"codes", "code_words"}:
            return LATIN, "latin"
        return DIGITS, "digits"

    def first_allowed(self) -> str:
        pool, _kind = self.pool()
        if self.first:
            return "".join(ch for ch in pool if ch in self.first)
        if self.no_leading_zero or self.noun == "numbers":
            return "".join(ch for ch in pool if ch != "0")
        return pool


def parse_spec(statement: str) -> Spec:
    """Describe the objects one EGE 8 statement enumerates."""
    text = " ".join((statement or "").split())
    low = text.lower().replace("\u0451", "\u0435")
    spec = Spec(text=text)
    spec.noun = _noun(low)
    spec.length = _length(low, spec)
    spec.alphabet = _quoted_chain(text) or _listed_letters(text)
    spec.base = _base(low)
    if "\u043e\u043a\u0442\u0435\u0442" in low:
        spec.base = 2
        spec.noun = "codes"
    if "\u043b\u0430\u0442\u0438\u043d\u0441\u043a" in low and "\u0430\u043b\u0444\u0430\u0432\u0438\u0442" in low:
        spec.alphabet = [ch for ch in LATIN]
    spec.item = _item(low, spec)

    spec.repeats, spec.source_word = _repeats(low, text)
    if spec.repeats == "exact" and spec.source_word:
        spec.alphabet = _dedupe(list(spec.source_word))
        spec.length = spec.length or len(spec.source_word)
    if spec.source_word and not spec.alphabet and spec.noun != "numbers":
        spec.alphabet = _dedupe(list(spec.source_word))
    if re.search(r"\u0446\u0438\u0444\u0440\u044b \u0440\u0430\u0437\u043b\u0438\u0447\u043d\u044b|\u0446\u0438\u0444\u0440\u044b \u043d\u0435 \u043f\u043e\u0432\u0442\u043e\u0440\u044f\u044e\u0442\u0441\u044f|\u0440\u0430\u0437\u043b\u0438\u0447\u043d\u044b\u0445 \u0446\u0438\u0444\u0440", low):
        spec.distinct_digits = True

    spec.first, spec.last = _edges(low)
    spec.no_same_neighbours = _same_neighbours_banned(low)
    spec.alphabetical_neighbours = bool(
        re.search(r"\u0441\u043b\u0435\u0434\u0443\u044e\u0442 \u0434\u0440\u0443\u0433 \u0437\u0430 \u0434\u0440\u0443\u0433\u043e\u043c|\u0438\u0434\u0443\u0442 \u0434\u0440\u0443\u0433 \u0437\u0430 \u0434\u0440\u0443\u0433\u043e\u043c", low)
        or "\u0432 \u0442\u0430\u043a\u043e\u043c \u0436\u0435 \u043f\u043e\u0440\u044f\u0434\u043a\u0435" in low
    )
    spec.increasing = _order(low)

    _parse_slots(low, spec)
    _parse_numeric(low, spec)
    _parse_extra(low, text, spec)
    return spec


def _repeats(low: str, text: str) -> tuple[str, str]:
    """Return how often letters may repeat and the word they come from."""
    if re.search(r"\u043f\u0435\u0440\u0435\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u043e\u0439|\u043f\u0435\u0440\u0435\u0441\u0442\u0430\u0432\u043b\u044f|\u043f\u0435\u0440\u0435\u0441\u0442\u0430\u0432\u043b\u044f\u0435\u0442|\u043c\u0435\u043d\u044f\w* \u043c\u0435\u0441\u0442\u0430\u043c\u0438", low):
        return "exact", _source_word(text)
    if re.search(r"\u0441\u0442\u043e\u043b\u044c\u043a\u043e \u0436\u0435 \u0440\u0430\u0437|\u043a\u0430\u0436\u0434\u0443\u044e \u0431\u0443\u043a\u0432\u0443 \u043d\u0443\u0436\u043d\u043e \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0440\u043e\u0432\u043d\u043e|\u043a\u0430\u0436\u0434\u0430\u044f \u0431\u0443\u043a\u0432\u0430 \u0432 \u043d\u0435", low):
        return "exact", _source_word(text)
    if re.search(r"\u043d\u0435 \u043f\u043e\u0432\u0442\u043e\u0440\u044f|\u0431\u0435\u0437 \u043f\u043e\u0432\u0442\u043e\u0440|\u0446\u0438\u0444\u0440\u044b \u0440\u0430\u0437\u043b\u0438\u0447\u043d", low):
        return "once", ""
    return "any", ""


def _same_neighbours_banned(low: str) -> bool:
    return bool(
        re.search(
            r"(?:\u043d\u0435|\u0431\u0435\u0437|\u0438\u0437\u0431\u0435\u0433\u0430\w*)\s+\w+\s*"
            r"(?:\u0441\u043e\u0434\u0435\u0440\u0436\w*|\u043f\u043e\u0432\u0442\u043e\u0440\w*|\u0441\u043b\u043e\u0432\w*)\s+\w*\s*"
            r"(?:\u043e\u0434\u0438\u043d\u0430\u043a\u043e\u0432|\u043f\u043e\u0432\u0442\u043e\u0440\u044f|\u0434\u0432\u0435|\u0434\u0432\u0443\u0445|\u0441\u043e\u0441\u0435\u0434)",
            low,
        )
        or re.search(r"(?:\u043e\u0434\u0438\u043d\u0430\u043a\u043e\u0432\w+|\u043f\u043e\u0432\u0442\u043e\u0440\w+)\s+(?:\w+\s+)?(?:\u0440\u044f\u0434\u043e\u043c|\u0441\u043e\u0441\u0435\u0434)", low)
        or re.search(r"\u0434\u0432\w+\s+\u043f\u043e\u0434\u0440\u044f\u0434\s+\u043e\u0434\u0438\u043d\u0430\u043a\u043e\u0432\w*", low)
        or re.search(r"(?:\u0431\u0435\u0437|\u043d\u0435|\u043d\u0438\u043a\u0430\u043a\u0438\u0445)\s+(?:\w+\s+){0,2}(?:\u043e\u0434\u0438\u043d\u0430\u043a\u043e\u0432\w*|\u043f\u043e\u0432\u0442\u043e\u0440\w*)\s+(?:\u043f\u043e\u0434\u0440\u044f\u0434\s+)?(?:\u0441\u043e\u0441\u0435\u0434\w*|\u043f\u043e\u0434\u0440\u044f\u0434)", low)
        or "\u043e\u0434\u0438\u043d\u0430\u043a\u043e\u0432\u044b\u0445 \u0441\u043e\u0441\u0435\u0434" in low
    )


def _order(low: str) -> str:
    if "\u043d\u0435\u0443\u0431\u044b\u0432\u0430\u043d" in low:
        return "weak"
    if "\u043d\u0435\u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d" in low:
        return "non_increasing"
    if re.search(r"\u0432 \u043f\u043e\u0440\u044f\u0434\u043a\u0435 (?:\u0441\u0442\u0440\u043e\u0433\u043e\u0433\u043e )?\u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d\u0438\u044f|\u043f\u043e \u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d\u0438\u044e", low):
        return "strict"
    if re.search(r"\u0432 \u043f\u043e\u0440\u044f\u0434\u043a\u0435 \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044f|\u043f\u043e \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044e", low):
        return "decreasing"
    return ""


def _parse_extra(low: str, text: str, spec: Spec) -> None:
    for match in re.finditer(r"(?:содержать|содержать ни одного) сочетани\w* ([А-ЯЁ]{2,8})(?![А-ЯЁ])", text):
        spec.forbidden_subs.append(match.group(1))
    for match in re.finditer(r"сочетан\w* ([А-ЯЁ]{2,8})[,.]", text):
        spec.forbidden_subs.append(match.group(1))
    for match in re.finditer(r"(?:не )?содержит (?:ни одного )?сочетани\w* ([А-ЯЁ]{2,8})", text):
        if match.group(0).lower().startswith("не "):
            continue
        spec.forbidden_subs.append(match.group(1))
    match = re.search(r"не более одной цифры (\d)", low)
    if match:
        spec.limit_cmp = ("<=", int(match.group(1)))
        spec.digit_once = [match.group(1)]
    if re.search(r"разряд\w*, кратные 2 и кратные 3, чередуются", low):
        spec.alternating = True
    if re.search(r"количество гласных и согласных (?:букв )?(?:в слове )?(?:совпадает|одинаково)", low):
        spec.balanced_vowels = True
    if re.search(r"кратно сумме цифр", low):
        spec.sum_divisible = True
    if re.search(r"чередуются и", low) and "нечетные и четные цифры чередуются" in low:
        spec.alternating = True


def _length(low: str, spec: Spec) -> int | None:
    match = re.search(
        r"(?<![\d,.])(\d{1,2})\s*-?\s*(?:буквен|значн|символьн|разрядн|цифр|знаков)", low
    )
    if match:
        value = int(match.group(1))
        if 2 <= value <= 20:
            return value
    stems = "|".join(LENGTH_WORDS)
    match = re.search(rf"(?<![\w-])({stems})-?(?:буквен|значн|символьн|разрядн|цифр|значн)\w*", low)
    if match:
        return LENGTH_WORDS[match.group(1)]
    stems = "|".join({"трехзнач": 3, "четырехзнач": 4, "пятизнач": 5, "шестизнач": 6, "семизнач": 7})
    match = re.search(rf"({stems})\w*", low)
    if match:
        return {"трехзнач": 3, "четырехзнач": 4, "пятизнач": 5, "шестизнач": 6, "семизнач": 7}[match.group(1)]
    if re.search(r"троичн\w* (?:четырехзнач|4-знач)", low):
        return 4
    match = re.search(r"состоит из (\d{1,2}) (?:букв|цифр|символов|знаков|блоков)", low)
    if match and 2 <= int(match.group(1)) <= 20:
        return int(match.group(1))
    match = re.search(r"\bдлиной (\d{1,2})\b", low)
    if match and 2 <= int(match.group(1)) <= 20:
        return int(match.group(1))
    if "цифр" in low or "разряд" in low:
        # The first number before those words is the length of the code.
        match = re.search(r"(?<![\d,.])(\d{1,2})(?!\d)", low)
        if match and 2 <= int(match.group(1)) <= 20:
            return int(match.group(1))
    if "не более чем из" in low:
        # "троичная запись не более чем из 12 разрядов": 12 is the ceiling.
        match = re.search(r"не более чем из (\d{1,2})", low)
        if match:
            spec.ceiling = int(match.group(1))
    if "наборов из 0 и 1" in low or "последовательность из нулей" in low:
        match = re.search(r"длиной (\d{1,2})", low)
        if match:
            return int(match.group(1))
    return None


def _noun(low: str) -> str:
    if "тропинк" in low:
        return "trails"
    if "кодов" in low and "слов" in low:
        return "code_words"
    if "слов" in low:
        return "words"
    if "последовательност" in low:
        return "sequences"
    if (re.search(r"\bкод", low) or "сигнал" in low) and not re.search(r"различн\w* слов|\bслов из", low):
        return "codes"
    if re.search(r"систем\w* счислен|\bчисл", low):
        return "numbers"
    return "words"


def _item(low: str, spec: Spec) -> str:
    if spec.noun == "trails":
        return "тропинка"
    if spec.noun == "sequences" and "код" not in low:
        return "последовательность"
    if spec.noun in {"codes", "code_words"} or re.search(r"\bкод", low):
        return "код"
    if spec.noun == "numbers":
        return "число"
    return "слово"


def _base(low: str) -> int | None:
    for stem, value in BASES.items():
        if stem in low:
            return value
    match = re.search(r"основани\w* (\d{1,2})", low)
    if match:
        return int(match.group(1))
    if re.search(r"десятичн\w* (?:систем|запис)", low):
        return 10
    return None


def _quoted_chain(text: str) -> list[str]:
    """Letters quoted as an example of a forbidden or required substring."""
    for match in re.finditer(r'["«“]([^"»”]{2,60})["»”]', text):
        inner = match.group(1)
        before = text[max(0, match.start() - 40) : match.start()].lower()
        if not re.search(r"сочетани|фрагмент|подстрок|например|последовательност", before):
            continue
        chars = [ch.upper() for ch in inner if ch.isalpha()]
        if len(chars) >= 2 and not re.search(r"\d", inner):
            return _dedupe(chars)
    return []


def _listed_letters(text: str) -> list[str]:
    braces = re.search(r"\{([A-ZА-ЯЁ](?:\s*[,;]\s*[A-ZА-ЯЁ])*)\}", text)
    if braces:
        return _dedupe([ch for ch in braces.group(1) if ch.isalpha()])
    match = re.search(r"(?:из букв|алфавит\w*)\s+([A-ZА-ЯЁ](?:\s*[,;]\s*[A-ZА-ЯЁ])+)", text)
    if match:
        return _dedupe([ch for ch in match.group(1) if ch.isalpha()])
    return []


def _source_word(text: str) -> str:
    match = re.search(r"(?:слова|слово|в слове|в слово)\s+([А-ЯЁA-Z]{3,20})\b", text)
    if match:
        return match.group(1)
    match = re.search(r"([А-ЯЁA-Z]{3,20})[,.]?\s+так, что", text)
    if match:
        return match.group(1)
    return ""


def _dedupe(chars: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ch in chars:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def _ordinal(word: str) -> int:
    for stem, value in ORDINALS.items():
        if word.startswith(stem):
            return value
    return 0


def _edges(low: str) -> tuple[list[str] | None, list[str] | None]:
    first: list[str] | None = None
    last: list[str] | None = None

    no_zero = re.search(
        r"не может начинаться с (?:цифры )?0|не может быть нулем|не может быть нолем"
        r"|(?:первая|первой) (?:буква |цифра )?не может быть (?:цифрой )?0"
        r"|начина\w* с нуля",
        low,
    )
    if no_zero:
        first = list(DIGITS[1:])
    if re.search(r"перва\w+ (?:буква\w*|буквы)?\s*(?:кода\s*)?(?:должна быть|—|-)?\s*согласн", low):
        first = list(SOGL_FULL)
    if re.search(r"перва\w+ (?:буква\w*|буквы)?\s*(?:кода\s*)?(?:должна быть|—|-)?\s*гласн", low):
        first = list(GLAS_FULL)
    if re.search(r"последн\w+ (?:буква\w*)?\s*(?:кода\s*)?(?:должна быть|—|-)?\s*гласн", low):
        last = list(GLAS_FULL)
    if re.search(r"последн\w+ (?:буква\w*)?\s*(?:кода\s*)?(?:должна быть|—|-)?\s*согласн", low):
        last = list(SOGL_FULL)

    tail = re.search(
        r"(?:оканчивается|заканчивается|последняя (?:буква|цифра))\s+(?:на\s+)?([0-9a-zа-я])\b", low
    )
    if tail:
        letter = tail.group(1).upper()
        if letter in GLAS_FULL or letter in GLAS_FULL.lower().upper():
            last = list(GLAS_FULL)
        elif letter in DIGITS or letter in LATIN or letter in TRADITIONAL:
            last = [letter]

    head = re.search(r"(?:начинается|начинаются)\s+(?:с\s+)?([0-9a-zа-я])\b", low)
    if head:
        letter = head.group(1).upper()
        if letter in GLAS_FULL:
            first = list(GLAS_FULL)
        elif letter in DIGITS or letter in LATIN or letter in TRADITIONAL:
            if first is None:
                first = [letter]
    return first, last


def _parse_slots(low: str, spec: Spec) -> None:
    """Positions where a letter is forbidden or forced."""
    for match in re.finditer(
        r"(?:на|со|с)\s+(\w+)\s+(?:месте|позиции|позициях|буква\w*)\s+[^.;]{0,50}?"
        r"(не может (?:стоять|быть)|должна (?:стоять|быть|находиться))\s*"
        r"(?:буква\w*|цифра\w*)?\s*([а-яa-z0-9])",
        low,
    ):
        index = _ordinal(match.group(1))
        if not index:
            continue
        verb, letter = match.group(2), match.group(3)
        if "гласн" in letter:
            letter = "е"
        if "согласн" in letter:
            letter = "б"
        if verb.startswith("не"):
            spec.banned[index] = letter.upper()
        else:
            spec.forced[index] = letter.upper()
    for match in re.finditer(r"на (\w+) месте стоит (?:буква |цифра )?([а-яa-z0-9])", low):
        index = _ordinal(match.group(1))
        if index:
            spec.forced[index] = match.group(2).upper()
    if re.search(r"последн\w+ (?:буква\w*)?\s+не может быть (?:буквой )?гласн", low):
        spec.banned[spec.length or 0] = "*G"
    if re.search(r"перва\w+ (?:буква\w*)?\s+не может быть (?:буквой )?гласн", low):
        spec.banned[1] = "*G"
    if re.search(r"перва\w+ (?:буква\w*)?\s+не может быть (?:буквой )?согласн", low):
        spec.banned[1] = "*C"


def _parse_numeric(low: str, spec: Spec) -> None:
    digits = "0123456789"
    if "двоичн" in low or "октет" in low:
        digits = "01"
    elif spec.base:
        digits = DIGITS[: spec.base]

    match = re.search(r"не более (одной|двух|трех|трех|четырех|\d)\s*цифр", low)
    if match:
        word = match.group(1)
        value = {"одной": 1, "двух": 2, "трех": 3, "четырех": 4}.get(word, 0)
        digit = re.search(r"цифры (\d)", low)
        if value or digit:
            spec.limit_cmp = ("<=", int(digit.group(1)) if digit else 0)
    match = re.search(r"не менее (\d+)\s*раз", low)
    if match and int(match.group(1)) <= 2:
        spec.min_double = True
    match = re.search(r"(?:ровно )?(\d+)\s+(?:чет[а-я]* )?цифр\w*,?\s*(?:различн\w+)?", low)
    if re.search(r"встреча\w* не менее двух раз|цифра\w* встречается (?:не менее|минимум) (?:дважды|2|двух)", low):
        spec.min_double = True
    if re.search(r"чет[а-я]*\s+[а-я]+\s+(?:числ|запис|чисел)", low):
        spec.last_parity = "even"
    match = re.search(r"не более (\d+)\s+чет[а-я]*", low)
    if match:
        spec.max_even = int(match.group(1))
    match = re.search(r"ровно (\d+)\s+чет[а-я]*", low)
    if match:
        spec.exact_even = int(match.group(1))
    if re.search(r"количество (?:гласных и согласных|четных и нечетных)", low):
        spec.limit_cmp = spec.limit_cmp or ("balance", 1)
    if re.search(r"(?:чет[а-я]*|неч[её]т[а-я]*)\s+и\s+(?:чет[а-я]*|неч[её]т[а-я]*)[^.]{0,40}чередуются", low) or re.search(
        r"никакие\s+две\s+чет[а-я]*\s+и\s+две\s+неч[её]т[а-я]*", low
    ):
        spec.alternating = True
    if re.search(
        r"(?:две|двух)\s+(?:чет[а-я]*|неч[её]т[а-я]*)\s+или\s+две\s+(?:чет[а-я]*|неч[её]т[а-я]*)[^.]{0,40}"
        r"(?:рядом|подряд|стоят)",
        low,
    ):
        spec.parity_adjacent = True
    if not spec.no_leading_zero and spec.noun == "numbers":
        spec.no_leading_zero = True


# ---------------------------------------------------------------------------
# student's program

@dataclass
class Program:
    """Observable shape of a student program, without running it."""

    iterator: str = ""  # product | permutations | combinations | cartesian | words | product_len
    repeat: int | None = None
    length_filter: bool = False
    has_zero_guard: bool = False
    neighbours: bool = False
    increasing: bool = False
    decreasing: bool = False
    forbidden_subs: list[str] = field(default_factory=list)
    first_letter: str = ""
    last_letter: str = ""
    pools: list[str] = field(default_factory=list)


def analyze(source: str) -> Program:
    program = Program()
    src = source.replace("\r\n", "\n")
    compact = re.sub(r"\s+", "", src)
    pool = re.findall(r"product\(\s*['\"]([^'\"]+)['\"]\s*,\s*repeat\s*=\s*([A-Za-z_]\w*|\d+)", src)
    if pool:
        program.pools = [item[0] for item in pool]
        repeat = pool[0][1]
        program.repeat = int(repeat) if repeat.isdigit() else None
        program.iterator = "product"
    if "product(" in src and not program.iterator:
        program.iterator = "product"
    if "permutations(" in src:
        program.iterator = "permutations"
    if "combinations(" in src and "product(" not in src:
        program.iterator = "combinations"
    loops = re.findall(r"for\s+([A-Za-z_]\w*)\s+in\s+range\(([^)]*)\)", src)
    if loops:
        variables = [item[0] for item in loops]
        words = re.findall(r"join\(\s*\(?\s*([^)]*?)\)?\s*\)", src)
        joined = " ".join(words)
        if all(re.search(rf"\b{re.escape(item)}\b", joined) for item in variables) and len(variables) >= 2:
            if program.iterator != "product":
                program.iterator = program.iterator or "cartesian"

    if re.search(r"len\([^)]*\)\s*(==|!=|<|>|<=|>=)\s*\d+", src) or re.search(
        r"len\([^)]*\)\s*(==|!=)\s*(N|n)\b", src
    ):
        program.length_filter = True

    program.has_zero_guard = bool(re.search(r"\[\s*0\s*\]\s*!=\s*['\"]0['\"]|\[\s*0\s*\]\s*==\s*['\"]0['\"]|startswith\(\s*['\"]0", src))
    program.neighbours = bool(re.search(r"\[\s*i\s*[+-]\s*1\s*\]|zip\(", src)) and bool(
        re.search(r"\[[A-Za-z_]\w*\s*\]\s*==\s*[A-Za-z_]\w*\s*\[", compact) or "foriinrange(1,len" in compact
    )
    program.requires_once = bool(re.search(r"len\(set\([^)]*\)\)\s*==\s*len\(|len\(set\(", src))
    program.requires_double = bool(
        re.search(r"count\([^)]+\)\s*>=\s*2", src) or re.search(r"len\(set\([^)]*\)\)\s*<\s*len\(", src)
    )
    program.any_in = bool(re.search(r"\bany\(", src))
    program.all_in = bool(re.search(r"\ball\(", src))
    program.increasing = bool(re.search(r"\[i\]\s*[<]\s*\[i\s*\+\s*1|<=.*\[i\s*\+\s*1", compact) or "sorted(" in src)
    program.decreasing = bool(re.search(r"\[i\]\s*>\s*\[i\s*\+\s*1", compact))
    for match in re.finditer(r"['\"]([А-ЯЁA-Z]{2,8})['\"]\s*(not\s+)?in\s", src):
        program.forbidden_subs.append(match.group(1))
    if "notin" in compact:
        program.forbidden_subs = list(dict.fromkeys(program.forbidden_subs))

    first = re.search(r"\[\s*0\s*\]\s*(?:==|!=|in)\s*(['\"][^'\"]*['\"]|[A-Za-z_]\w*)", src)
    if first:
        program.first_letter = first.group(1)
    last = re.search(r"\[\s*-1\s*\]\s*(?:==|!=|in)\s*(['\"][^'\"]*['\"]|[A-Za-z_]\w*)", src)
    if last:
        program.last_letter = last.group(1)

    program.print_count = bool(
        re.search(r"print\(\s*(len\(|\d)", src)
        or re.search(r"\b(?:count|cnt|ans|total|res|result|kol|k|c)\w*\s*\+=\s*1\b", src)
        or re.search(r"\breturn\s+(?:count|cnt|ans|total|res|result\w*)", src)
    )
    program.prints_index = bool(re.search(r"enumerate\(|\.index\(|\.find\(", src))
    program.uses_count = bool(re.search(r"\.count\(|collections\.Counter|Counter\(", src))
    for match in re.finditer(r"['\"]([А-ЯЁA-Z0-9])['\"]\s+not\s+in\s+([A-Za-z_]\w*)", src):
        if match.group(1).isupper() or match.group(1).isdigit():
            program.excluded.append(ord(match.group(1)))
    program.word_filters_text = " ".join(
        match.group(0) for match in re.finditer(r"\[[^\]\n]*\]", src) if "for" in match.group(0)
    )
    program.zero_first_only_for_numbers = bool(re.search(r"if\s+[A-Za-z_]\w*\[\s*0\s*\]", src))
    return program


# ---------------------------------------------------------------------------
# model vs program

@dataclass
class Finding:
    """One concrete reason the program counts other objects than the task."""

    title: str
    reason: str
    how: str
    weight: int = 90
    tag: str = ""

    @property
    def detail(self) -> str:
        """One sentence for the hint list; the advice lives in ``how``."""
        return self.reason


def compare(spec: Spec, program: Program, counts_size: bool = False) -> list[Finding]:
    """Differences between the task model and the student's enumeration.

    ``counts_size`` means the statement asks for a count, which is where a
    missing filter shows up as "too many / too few objects".
    """
    found: list[Finding] = []
    pool, kind = spec.pool()
    item = spec.item

    # 1. Which objects are enumerated at all.
    if program.iterator == "permutations" and spec.repeats in {"any", "once"}:
        found.append(
            Finding(
                "Перестановки вместо слов с повторами",
                "permutations берёт каждую букву слова один раз, а в условии буквы "
                + ("могут повторяться" if spec.repeats == "any" else "тоже могут повторяться")
                + ".",
                "Замени `permutations` на `product(алфавит, repeat=n)`.",
                weight=96,
                tag="iterator",
            )
        )
    if program.iterator == "product" and spec.repeats == "exact" and spec.source_word:
        found.append(
            Finding(
                "Нужны перестановки букв слова",
                f"В условии буквы слова {spec.source_word} используются ровно столько раз, сколько они есть в слове, "
                "а product с repeat даёт слова с любыми повторами.",
                f"Возьми `set(permutations('{spec.source_word}'))`: это убирает повторы одинаковых букв.",
                weight=96,
                tag="iterator",
            )
        )
    if program.iterator == "product" and program.repeat is None and spec.length:
        found.append(
            Finding(
                "Не задана длина слова",
                f"В product не хватает repeat: длина слова в условии {spec.length}, а без repeat перебираются только одиночные символы.",
                f"Допиши `repeat={spec.length}`.",
                weight=96,
                tag="iterator",
            )
        )
    if spec.length and program.repeat and program.repeat != spec.length:
        found.append(
            Finding(
                "Другая длина слова",
                f"В условии длина {spec.length}, а product берёт repeat={program.repeat}.",
                f"Поставь `repeat={spec.length}`.",
                weight=96,
                tag="iterator",
            )
        )
    if kind == "letters" and program.pools and program.pools[0].isdigit():
        found.append(
            Finding(
                "Перебираются цифры, а нужны буквы",
                "В условии слова из букв, а в product подставлена строка цифр.",
                f"Перебери буквы алфавита: `product('{''.join(spec.alphabet[:8])}', repeat={spec.length or 'n'})`.",
                weight=95,
                tag="iterator",
            )
        )
    if spec.alphabet and program.pools:
        used = set(program.pools[0])
        wanted = set(spec.alphabet)
        if not used & wanted:
            found.append(
                Finding(
                    "Алфавит не тот",
                    "В product перебирается другой набор символов, чем перечислен в условии.",
                    f"Алфавит из условия: {' '.join(spec.alphabet[:12])}.",
                    weight=94,
                    tag="iterator",
                )
            )
        else:
            extra = sorted(used - wanted)
            missing = sorted(wanted - used)
            if extra and not missing and len(used - wanted) > max(2, len(wanted) // 3):
                found.append(
                    Finding(
                        "В алфавите лишние буквы",
                        f"В product есть буквы, которых нет в условии: {', '.join(extra[:6])}.",
                        f"Оставь в product только {', '.join(spec.alphabet[:12])}.",
                        weight=88,
                        tag="iterator",
                    )
                )
            elif missing:
                found.append(
                    Finding(
                        "В алфавите не хватает букв",
                        f"В product не хватает символов из условия: {', '.join(missing[:6])}.",
                        "Допиши их в строку алфавита.",
                        weight=88,
                        tag="iterator",
                    )
                )
    if program.iterator in {"", "cartesian"} and spec.length:
        found.append(
            Finding(
                "Слово собирается не из букв алфавита",
                "Перебор вложенными циклами по диапазонам чисел не даёт слов из алфавита условия.",
                "Собери слова через product или циклы по строке алфавита.",
                weight=86,
                tag="iterator",
            )
        )

    # 2. Filters inside one word.
    if spec.first and spec.first != list(pool) and not program.first_letter:
        shown = "".join(spec.first[: 6]) + ("..." if len(spec.first) > 6 else "")
        found.append(
            Finding(
                "Не проверено начало слова",
                f"В условии первая буква ограничена ({shown}), а программа этого не проверяет.",
                "Добавь `s[0] in '...'` в условие отбора.",
                weight=95,
                tag="first",
            )
        )
    if spec.last and not program.last_letter:
        shown = "".join(spec.last[: 6]) + ("..." if len(spec.last) > 6 else "")
        found.append(
            Finding(
                "Не проверен конец слова",
                f"В условии последняя буква ограничена ({shown}), а фильтра по `s[-1]` нет.",
                "Добавь `s[-1] in '...'` в условие отбора.",
                weight=95,
                tag="last",
            )
        )
    if spec.no_same_neighbours and not program.neighbours:
        found.append(
            Finding(
                "Не проверены соседние буквы",
                "Запрет на одинаковые соседние буквы в коде не выполняется: пара подряд не проверяется.",
                "Добавь `all(s[i] != s[i + 1] for i in range(len(s) - 1))`.",
                weight=94,
                tag="neighbours",
            )
        )
    if spec.alphabetical_neighbours and not program.neighbours:
        found.append(
            Finding(
                "Пара соседних букв по алфавиту не проверяется",
                "Запрет на пары букв, идущие подряд по алфавиту, в коде не проверяется.",
                "Для каждой пары `s[i] + s[i + 1]` проверь, что она не входит в список запрещённых пар.",
                weight=93,
                tag="neighbours",
            )
        )
    if spec.parity_adjacent and not program.neighbours:
        found.append(
            Finding(
                "Рядом стоят две чётные или две нечётные цифры",
                "Две цифры одной чётности не должны стоять рядом, но пары соседей программа не проверяет.",
                "Добавь `all(int(s[i]) % 2 != int(s[i + 1]) % 2 for i in range(len(s) - 1))`.",
                weight=93,
                tag="neighbours",
            )
        )
    if spec.last_parity == "even" and not program.last_letter:
        found.append(
            Finding(
                "Не проверена последняя цифра",
                "В условии число должно быть чётным, а последняя цифра не проверяется.",
                "Добавь `s[-1] in '02468'` в условие отбора.",
                weight=93,
                tag="last",
            )
        )
    if spec.forbidden_subs:
        text = "".join(program.forbidden_subs)
        missing = [item for item in spec.forbidden_subs if item not in text]
        if missing:
            found.append(
                Finding(
                    "Не проверена запрещённая подстрока",
                    f"В условии слово не должно содержать {', '.join(missing)}, а такой проверки в коде нет.",
                    f"Добавь `'{missing[0]}' not in s` в условие отбора.",
                    weight=90,
                    tag="substring",
                )
            )
    if spec.distinct_digits and not program.requires_once:
        found.append(
            Finding(
                "Цифры могут повторяться",
                "В условии все цифры различны, а повторов внутри числа никто не отсекает.",
                "Добавь `len(set(s)) == len(s)`.",
                weight=93,
                tag="distinct",
            )
        )
    if spec.repeats == "once" and not program.requires_once and spec.distinct_digits is False:
        found.append(
            Finding(
                "Буквы не должны повторяться",
                "В условии каждая буква используется не более одного раза, а проверки на повторы нет.",
                "Добавь `len(set(s)) == len(s)`.",
                weight=92,
                tag="distinct",
            )
        )
    if spec.increasing in {"strict", "weak"} and not (program.increasing or program.decreasing):
        how = (
            "Добавь `all(s[i] < s[i + 1] for i in range(len(s) - 1))`."
            if spec.increasing == "strict"
            else "Добавь `all(s[i] <= s[i + 1] for i in range(len(s) - 1))`."
        )
        found.append(
            Finding(
                "Порядок цифр не проверяется",
                "В условии порядок монотонный (идёт возрастание/неубывание), а код этого не требует.",
                how,
                weight=92,
                tag="order",
            )
        )
    if spec.min_double and not program.requires_double:
        found.append(
            Finding(
                "Не отсеяны слова без повтора",
                "Нужна цифра, которая повторяется, но слова, где все символы разные, остаются в счёте.",
                "Добавь `any(s.count(ch) >= 2 for ch in set(s))`.",
                weight=91,
                tag="double",
            )
        )
    if spec.digit_once and program.uses_count is False:
        found.append(
            Finding(
                f"Ограничение на цифру {spec.digit_once[0]} не проверено",
                f"В условии цифра {spec.digit_once[0]} встречается ограниченное число раз, а фильтра по её количеству нет.",
                f"Добавь `s.count('{spec.digit_once[0]}') <= {spec.limit_cmp[1] if spec.limit_cmp else 1}`.",
                weight=86,
                tag="digit-once",
            )
        )

    # 3. zero as a forbidden first digit.
    if spec.first == list(DIGITS[1:]) and kind == "digits" and not program.has_zero_guard:
        found.append(
            Finding(
                "Число может начинаться с нуля",
                (
                    "Программа считает записи с ведущим нулём, а настоящих чисел столько же, только без них."
                    if counts_size
                    else "Программа разрешает первую цифру 0, а числа с ведущим нулём не считаются."
                ),
                "Добавь `s[0] != '0'` в условие отбора.",
                weight=96,
                tag="zero",
            )
        )

    # 4. Output shape.
    if counts_size and program.print_count is False and spec.noun != "numbers":
        found.append(
            Finding(
                "Печатается слово, а нужно количество",
                "В условии спрашивают «сколько», а программа печатает сам код или слово.",
                "Печатай длину списка: `print(len(answers))`.",
                weight=95,
                tag="output",
            )
        )
    if not counts_size and program.prints_index and not program.print_count:
        found.append(
            Finding(
                "В №8 редко просят номер",
                "Программа печатает номер или слово, хотя по формулировке нужен другой результат — сверь, что просят вывести.",
                "Сверь последний абзаце условия: там сказано, что именно напечатать.",
                weight=70,
                tag="output",
            )
        )
    return found
