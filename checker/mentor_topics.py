from __future__ import annotations

from pathlib import Path

from checker.models import Problem

_PACKS = Path(__file__).resolve().parent / "mentor_packs"


def _pack_namespace(tag: str) -> dict:
    path = _PACKS / f"{tag}.py"
    if not path.is_file():
        return {}
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}
    namespace: dict = {}
    try:
        exec(compile(source, str(path), "exec"), namespace, namespace)
    except Exception:
        return {}
    return namespace


def pack_guide(problem: Problem) -> str:
    parts: list[str] = []
    for tag in problem.tags:
        guide = _pack_namespace(tag).get("GUIDE") or ""
        if isinstance(guide, str) and guide.strip():
            parts.append(guide.strip())
    return "\n".join(parts)


def pack_notes(problem: Problem, source: str) -> str:
    parts: list[str] = []
    for tag in problem.tags:
        fn = _pack_namespace(tag).get("notes")
        if not callable(fn):
            continue
        try:
            text = fn(problem, source)
        except Exception:
            continue
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)

# Short checklists. The model still has to point at a fragment of the
# student's current code. These lines only say which mismatch to look for.


def topic_guide(problem: Problem) -> str:
    tags = set(problem.tags)
    blocks: list[str] = []
    if "ege2" in tags:
        blocks.append(
            "ЕГЭ 2. Печатают четыре буквы столбцов. "
            "Импликация — это p <= q, не ==. Дизъюнкция — это or. "
            "Пустые клетки перебирает product([0, 1]), порядок столбцов — permutations. "
            "Одинаковые строки фрагмента отбрасывают: если написано >= 1, look — `>= 1`, instead — == числу строк. Цикл в instead не пиши. "
            "Печать без пробелов и подписи. Если в print есть слово «ответ», look — это слово, instead — печать только четырёх букв."
        )
    if "ege5" in tags:
        blocks.append(
            "ЕГЭ 5. Печатают 1 или 0, не True/False: print(int(...)). "
            "«И» — and, «или» — or. «Ровно одно» — (A) != (B), не or и не and. "
            "«Ровно два» — sum((A, B, C)) == 2. Отрезки соединяют or. "
            "Модуль — abs. Остаток — x % d == r или x % d in (...)."
        )
    if "ege8" in tags:
        blocks.append(
            "ЕГЭ 8. Перебор слов или кодов. Повторы разрешены — product, не permutations. "
            "Если написано permutations, а повторы разрешены, look — permutations, instead — product. Это fixable, не dead_end. "
            "Буквы ровно из слова — permutations этого слова. "
            "Алфавит и длина repeat берутся из условия, не из чужих цифр. "
            "Ведущий ноль: если алфавит содержит 0 и нет проверки первой цифры, допиши word[0] != '0' в условие. Комментарий вместо этой проверки запрещён. "
            "Соседи: s[i] и s[i+1]. «Сколько» — print(len(...)), не само слово."
        )
    if "ege9" in tags:
        blocks.append(
            "ЕГЭ 9. Таблица в файле. Разделитель бери из строки «Ввод»: если там точка с запятой, "
            "split(',') и split() меняют на split(';'). "
            "Читают open(...), не input(). Два условия вместе — and в той же строке if, без for. "
            "Пары с равными суммами у четырёх отсортированных чисел: a[0] + a[-1] == a[1] + a[2]. "
            "«Только одно из двух» — != , не or. "
            "Повтор ровно дважды: instead без цикла, `2 in Counter(row).values()`, не len(set) < len. "
            "Медиана — элемент sorted, не исходного списка."
        )
    if "ege13" in tags:
        blocks.append(
            "ЕГЭ 13. Адрес — четыре части 0..255, ведущий ноль запрещён у многозначной части. "
            "Сеть — ip & mask, не |. Узел — ip & ~mask, не последний октет сам по себе. "
            "Нули считают в 32 битах f'{n:032b}', не в bin(n). "
            "Маска — сплошные единицы слева, без дыр."
        )
    if "ege14" in tags:
        blocks.append(
            "ЕГЭ 14. Цифры в основании b снимают циклом n % b и n //= b. "
            "str(n) и bin(n) — это десятичная и двоичная запись, не основание b. "
            "int(s, b) читает из системы, а не пишет в неё. "
            "«Оканчивается на d» — n % b == d. "
            "«От A до B включительно» — range(A, B + 1). Если написано range(A, B), look — B, instead — B + 1."
        )
    if "ege15" in tags:
        blocks.append(
            "ЕГЭ 15. Отрезок — a <= x <= b, не ==. Импликация A ? P — (not A) or P. "
            "Длина отрезка — b - a, не b - a + 1. "
            "Нельзя печатать одно угаданное A: нужен перебор x и all(...). "
            "ДЕЛ(n, A) — n % A == 0, не A % n == 0."
        )
    if "ege16" in tags:
        blocks.append(
            "ЕГЭ 16. База и ветки копируют формулу из условия, включая каждый член. "
            "Если формула идёт через F(n+1), вызовы пишут f(n+1) и f(n+2), не f(n-1). "
            "Базу if n == 1 не заменяй на порог, если у этой ветки другое возвращаемое число. "
            "Чёт и нечёт не меняют местами: меняют всю правую часть ветки, а не n-2 на n-1. "
            "Если просят последние цифры — печатают f(n) % 10**k, не всё число."
        )
    if "ege17" in tags:
        blocks.append(
            "ЕГЭ 17. Отрезок [L; R] — range(L, R + 1). "
            "input() меняют на open('имя-файла'), не на имя файла в кавычках. "
            "combinations меняют на zip(data, data[1:]). "
            "«Не делится» — x % d != 0, не == 0. Несколько «не делится» соединяют and. "
            "Последняя цифра — abs(x) % 10. "
            "В ответе два числа: сначала количество, потом минимум или максимум."
        )
    if "ege18" in tags:
        blocks.append(
            "ЕГЭ 18. Таблица из файла. Это fixable, не dead_end. print не трогай. "
            "Старт удваивают в присваивании стартовой клетки: допиши * 2. "
            "Вправо и вверх — значение клетки без * 2. Диагональ — с * 2. "
            "Если * 2 стоит на ходе вправо или вверх, убери эту двойку."
        )
    if tags & {"ege19", "ege20", "ege21"}:
        blocks.append(
            "ЕГЭ 19–21. Две кучи. Ход — прибавить или умножить одну кучу, как в условии. Конец: a + b >= порог, не ==. "
            "Если под концом игры стоит return 1, look — return 1, instead — return 0. Строку if не переписывай. "
            "Ход «прибавь N»: чужое + 1 меняют на + N из условия. Формулу длины победы не трогай. "
            "Квантор меняют одним словом: look — any или all, instead — другое слово, без for. "
            "№19 печатает min, не max. №20 и №21 — max."
        )
    if "ege23" in tags:
        blocks.append(
            "ЕГЭ 23. Каждая команда условия — отдельный вызов: прибавь N это f(x+N), умножь на N это f(x*N). "
            "Если сумма f(...) написана без return, look — эта сумма, instead — return и та же сумма. Это fixable, не dead_end. "
            "Если команд три, в return три слагаемых. Не заменяй строку на ту же с другими пробелами. "
            "Старт A и финиш B: печатают f(A). f(другое) меняют на f(A). "
            "Больше цели — return 0, ровно цель — return 1. Обязательная точка K: f(A,K) * f(K,B). "
            "Если проверка цели стоит не на финише из условия, look — чужое число, instead — финиш. "
            "В объяснении напиши: в условии нужно получить финиш, а в коде проверка на другое число."
        )
    if "ege24" in tags:
        blocks.append(
            "ЕГЭ 24. Это fixable, не dead_end. Цикл в instead писать нельзя. "
            "Если есть input(), меняют именно input() на open('имя-файла').read().strip(). "
            "Не заменяй print на print(best) и не придумывай новое имя. "
            "s.count(...) — не длина подряд. look — count, instead — слова «длину подряд», без for. "
            "Символ не подошёл — счётчик обнуляют или начинают заново, если символ годится в начало. "
            "Печатают длину числом, не кусок строки."
        )
    if "ege25" in tags:
        blocks.append(
            "ЕГЭ 25. Отрезок [A; B] — range(A, B + 1). "
            "Делители ищут до корня и добавляют парный x // i один раз, если i*i == x. "
            "«Кроме самого числа» — верх range до x, не до x+1. "
            "range до 10**9 меняют на range(10) для каждой неизвестной цифры, не на одно число. "
            "Знак ? — любая цифра 0..9. Условие == '5' для этой цифры убирают: instead — True. "
            "Если просят число и частное — print(n, n // d), не один n."
        )
    extra = pack_guide(problem)
    if extra:
        blocks.append(extra)
    if not blocks:
        return ""
    return "Правила этого номера, сверяй с кодом ученика:\n" + "\n".join(blocks)
