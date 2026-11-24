"""Ответы на вопросы по данным 1С:Бухгалтерии через COM-соединение (только чтение).

Бот не пользуется старыми выгрузками: на каждый вопрос делается свежий запрос к базе,
поэтому в ответ попадает всё, что проведено к этой минуте.

Что умеет (вопрос → функция):
  «кто нам должен», «дебиторка»                → debts()
  «сколько должен Ромашка», «долг по Ромашке»  → debts(contractor=...)
  «просроченные долги»                         → debts(overdue_only=True)
  «… на 1 ноября», «… на 01.11.2026»           → любой из отчётов о долге на дату
  «продажи за октябрь», «выручка за 2025»      → sales()
  «остаток товара фильтр масляный»             → stock()
  «залежавшиеся товары»                        → stale()

    python data1c.py "кто нам должен"
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
ENV_FILE = Path(os.getenv("ONEC_ENV", ROOT.parent / "1c-tools" / ".env"))
MAX_LINES = 15  # сколько строк списка показывать в Telegram

MONTHS = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]


# ---------- подключение ----------

_conn = None


def connect():
    """Одно COM-соединение на процесс. Пароль берётся из 1c/.env (в git не попадает)."""
    global _conn
    if _conn is not None:
        return _conn
    import pythoncom
    import win32com.client
    from dotenv import dotenv_values

    env = dotenv_values(ENV_FILE)
    s = f'File="{env["ONEC_BASE"]}";Usr="{env.get("ONEC_USER", "")}";Pwd="{env.get("ONEC_PWD", "")}";'
    pythoncom.CoInitialize()
    _conn = win32com.client.Dispatch("V83.COMConnector").Connect(s)
    return _conn


def reset():
    global _conn
    _conn = None


def to_py(conn, v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dt.datetime):
        v = v.replace(tzinfo=None)
        return None if v.year == 1 else v
    return conn.String(v)


def query(text: str, params: dict | None = None) -> list[dict]:
    conn = connect()
    q = conn.NewObject("Query")
    q.Text = text
    for k, v in (params or {}).items():
        q.SetParameter(k, v)
    table = q.Execute().Unload()
    cols = [table.Columns.Get(i).Name for i in range(table.Columns.Count())]
    return [{c: to_py(conn, table.Get(r).Get(i)) for i, c in enumerate(cols)} for r in range(table.Count())]


# ---------- форматирование ----------

def rub(x: float) -> str:
    s = f"{abs(x):,.2f}".replace(",", " ").replace(".", ",")
    s = s[:-3] if s.endswith(",00") else s
    return ("−" if x < 0 else "") + s + " ₽"


def ddmmyyyy(d: dt.date) -> str:
    return d.strftime("%d.%m.%Y")


def next_day(d: dt.date) -> dt.datetime:
    """Остатки 1С на момент «начало следующего дня» = с учётом всех документов дня d."""
    return dt.datetime.combine(d + dt.timedelta(days=1), dt.time())


# ---------- разбор дат и периодов в вопросе ----------

def _month(word: str) -> int | None:
    word = word.lower()
    for i, m in enumerate(MONTHS, 1):
        if word.startswith(m) and (m != "ма" or word in ("май", "мая", "мае", "маю")):
            return i
    return None


def parse_date(text: str, today: dt.date) -> dt.date | None:
    """«на 1 ноября», «на 01.11.2026», «на 1 ноября 2025», «на вчера»."""
    t = text.lower()
    if re.search(r"\bна\s+вчера\b", t):
        return today - dt.timedelta(days=1)
    m = re.search(r"\bна\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", t)
    if m:
        y = int(m.group(3)) if m.group(3) else today.year
        y = y + 2000 if y < 100 else y
        return dt.date(y, int(m.group(2)), int(m.group(1)))
    m = re.search(r"\bна\s+(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?", t)
    if m and _month(m.group(2)):
        y = int(m.group(3)) if m.group(3) else today.year
        return dt.date(y, _month(m.group(2)), int(m.group(1)))
    return None


def parse_period(text: str, today: dt.date) -> tuple[dt.date, dt.date, str] | None:
    """«за октябрь», «за октябрь 2025», «за прошлый месяц», «за этот месяц», «за 2025 год», «с 01.10 по 31.10»."""
    t = text.lower()
    m = re.search(r"\bс\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\s+по\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", t)
    if m:
        y1 = int(m.group(3) or today.year)
        y2 = int(m.group(6) or y1)
        y1, y2 = (y1 + 2000 if y1 < 100 else y1), (y2 + 2000 if y2 < 100 else y2)
        a, b = dt.date(y1, int(m.group(2)), int(m.group(1))), dt.date(y2, int(m.group(5)), int(m.group(4)))
        return a, b, f"с {ddmmyyyy(a)} по {ddmmyyyy(b)}"

    def month_range(y, mo):
        a = dt.date(y, mo, 1)
        b = (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1))
        return a, b

    if re.search(r"(прошл|предыдущ)\w*\s+месяц", t):
        first = today.replace(day=1) - dt.timedelta(days=1)
        a, b = month_range(first.year, first.month)
        return a, b, f"за {ddmmyyyy(a)}–{ddmmyyyy(b)}"
    if re.search(r"(этот|текущ|этом)\w*\s+месяц", t):
        a = today.replace(day=1)
        return a, today, f"с {ddmmyyyy(a)} по {ddmmyyyy(today)}"
    m = re.search(r"\bза\s+([а-я]+)(?:\s+(\d{4}))?", t)
    if m and _month(m.group(1)):
        mo = _month(m.group(1))
        y = int(m.group(2)) if m.group(2) else (today.year if mo <= today.month else today.year - 1)
        a, b = month_range(y, mo)
        return a, b, f"за {m.group(1)} {y}"
    m = re.search(r"\bза\s+(\d{4})(?:\s*г)?", t)
    if m:
        y = int(m.group(1))
        return dt.date(y, 1, 1), dt.date(y, 12, 31), f"за {y} год"
    if re.search(r"(этот|текущ)\w*\s+год|с начала года", t):
        a = dt.date(today.year, 1, 1)
        return a, today, f"с {ddmmyyyy(a)} по {ddmmyyyy(today)}"
    return None


# ---------- поиск названий ----------

_NAME_NOISE = re.compile(r'\b(ооо|оао|зао|пао|ао|ип|гу|фгуп|муп|ук)\b|["«»“”\'().,]', re.I)


def _name_words(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-zа-яё0-9-]+", _NAME_NOISE.sub(" ", name.lower())) if len(w) > 2]


def match_names(question: str, names: list[str]) -> list[str]:
    """Названия, слова которых встречаются в вопросе (с учётом окончаний: «Ромашки» ~ «Ромашка»)."""
    q = question.lower().replace("ё", "е")
    q_words = re.findall(r"[a-zа-я0-9-]+", q)
    scored = []
    for n in names:
        words = [w.replace("ё", "е") for w in _name_words(n)]
        if not words:
            continue
        matched = [w for w in words if any(qw.startswith(w[:max(4, len(w) - 2)]) for qw in q_words)]
        if matched:
            longest = max(map(len, matched))
            scored.append((len(matched) / len(words), len(matched), longest, n))
    if not scored:
        return []
    best = max(s[0] for s in scored)
    # одного совпавшего слова хватает, если оно длинное и редкое (фамилия, «Ромашка»)
    return [n for share, hit, longest, n in sorted(scored, reverse=True)
            if share == best and (share >= 0.5 or hit >= 2 or longest >= 6)]


# ---------- отчёты ----------

DEBT_QUERY = """
ВЫБРАТЬ
    О.Организация КАК Организация,
    О.Субконто1 КАК Контрагент,
    О.Субконто2 КАК Договор,
    О.Субконто3 КАК Документ,
    ВЫБОР КОГДА О.Субконто3 ССЫЛКА Документ.РеализацияТоваровУслуг ТОГДА "Реализация"
         КОГДА О.Субконто3 ССЫЛКА Документ.ПоступлениеНаРасчетныйСчет ТОГДА "Оплата"
         ИНАЧЕ "Прочее" КОНЕЦ КАК Тип,
    ЕСТЬNULL(О.Субконто3.Дата, ДАТАВРЕМЯ(1, 1, 1)) КАК ДатаДокумента,
    ВЫБОР КОГДА О.Субконто2 ССЫЛКА Справочник.ДоговорыКонтрагентов И О.Субконто2.УстановленСрокОплаты
         ТОГДА О.Субконто2.СрокОплаты ИНАЧЕ 0 КОНЕЦ КАК СрокОплатыДней,
    О.СуммаОстатокДт - О.СуммаОстатокКт КАК Сальдо
ИЗ
    РегистрБухгалтерии.Хозрасчетный.Остатки(&Период,
        Счет В ИЕРАРХИИ (ЗНАЧЕНИЕ(ПланСчетов.Хозрасчетный.РасчетыСПокупателями)), , ) КАК О
"""

UNPOSTED_QUERY = """
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Количество, ЕСТЬNULL(СУММА(Д.СуммаДокумента), 0) КАК Сумма
ИЗ Документ.РеализацияТоваровУслуг КАК Д
ГДЕ НЕ Д.Проведен И НЕ Д.ПометкаУдаления И Д.Дата < &Период
"""


def debts(on: dt.date | None = None, contractor_question: str | None = None, overdue_only: bool = False) -> str:
    now = dt.datetime.now()
    day = on or now.date()
    period = next_day(day) if on else now
    rows = query(DEBT_QUERY, {"Период": period})
    stamp = f"на конец дня {ddmmyyyy(day)}" if on else f"на {now:%d.%m.%Y %H:%M}"

    for r in rows:
        d = r["ДатаДокумента"].date() if r["ДатаДокумента"] else None
        r["Срок"] = d + dt.timedelta(days=int(r["СрокОплатыДней"] or 0)) if d else None
        # просрочка — только у неоплаченных реализаций; списания с р/с, корректировки и т.п. просрочкой не считаем
        r["Просрочка"] = (day - r["Срок"]).days if r["Срок"] and r["Тип"] == "Реализация" else 0

    head = ""
    if contractor_question:
        names = sorted({r["Контрагент"] for r in rows})
        found = match_names(contractor_question, names)
        if not found:
            return (f"Не нашёл такого покупателя среди тех, у кого есть расчёты по счёту 62 {stamp}. "
                    "Если долга нет, контрагента здесь и не будет. Попробуйте написать название иначе.")
        if len(found) > 3:
            return "Под это название подходят несколько контрагентов, уточните:\n" + "\n".join(f"• {n}" for n in found[:10])
        rows = [r for r in rows if r["Контрагент"] in found]
        head = ", ".join(found) + "\n"

    if overdue_only:
        rows = [r for r in rows if r["Сальдо"] > 0 and r["Просрочка"] > 0]

    by = {}
    for r in rows:
        key = (r["Организация"], r["Контрагент"])
        a = by.setdefault(key, {"сальдо": 0.0, "просрочено": 0.0, "макс": 0, "строки": []})
        a["сальдо"] += r["Сальдо"]
        if r["Сальдо"] > 0 and r["Просрочка"] > 0:
            a["просрочено"] += r["Сальдо"]
            a["макс"] = max(a["макс"], r["Просрочка"])
        a["строки"].append(r)

    debtors = {k: v for k, v in by.items() if round(v["сальдо"], 2) > 0}
    prepaid = {k: v for k, v in by.items() if round(v["сальдо"], 2) < 0}
    total = sum(v["сальдо"] for v in debtors.values())
    total_over = sum(v["просрочено"] for v in debtors.values())

    title = "Просроченный долг покупателей" if overdue_only else "Долг покупателей"
    if not debtors and not prepaid:
        return f"{head}{title} {stamp}: долгов нет."
    lines = [f"{head}{title} {stamp}: {rub(total)}"]
    if not overdue_only and total_over:
        lines.append(f"из них просрочено: {rub(total_over)}")
    orgs = sorted({k[0] for k in debtors})

    if contractor_question and len(debtors) + len(prepaid) <= 3:
        # подробно по документам
        for (org, name), v in list(debtors.items()) + list(prepaid.items()):
            lines.append(f"\n{name} ({org}): {rub(v['сальдо'])}")
            for r in sorted(v["строки"], key=lambda r: r["ДатаДокумента"] or dt.datetime.min):
                over = f", просрочка {r['Просрочка']} дн." if r["Сальдо"] > 0 and r["Просрочка"] > 0 else ""
                lines.append(f"• {r['Документ'] or r['Договор']}: {rub(r['Сальдо'])}{over}")
    else:
        top = sorted(debtors.items(), key=lambda kv: -kv[1]["сальдо"])
        for i, ((org, name), v) in enumerate(top[:MAX_LINES], 1):
            org_note = f" [{org}]" if len(orgs) > 1 else ""
            over = f" (просрочено {rub(v['просрочено'])}, до {v['макс']} дн.)" if v["просрочено"] and not overdue_only else ""
            if overdue_only:
                over = f" (до {v['макс']} дн.)"
            lines.append(f"{i}. {name}{org_note} — {rub(v['сальдо'] if not overdue_only else v['просрочено'])}{over}")
        if len(top) > MAX_LINES:
            rest = sum(v["сальдо"] for _, v in top[MAX_LINES:])
            lines.append(f"… и ещё {len(top) - MAX_LINES} на {rub(rest)}")
        if prepaid and not overdue_only:
            lines.append(f"\nПереплаты / авансы покупателей: {rub(sum(v['сальдо'] for v in prepaid.values()))} "
                         f"({len(prepaid)} контрагентов). В сумму долга они не входят.")

    unposted = query(UNPOSTED_QUERY, {"Период": period})[0]
    if unposted["Количество"]:
        lines.append(f"\n⚠ Есть непроведённые реализации: {int(unposted['Количество'])} шт. на {rub(unposted['Сумма'])}. "
                     "В долг они не попали.")
    lines.append("\nСчёт 62, срок оплаты — по договору (если не задан, считается с даты документа).")
    return "\n".join(lines)


SALES_QUERY = """
ВЫБРАТЬ Д.Контрагент КАК Контрагент, КОЛИЧЕСТВО(*) КАК Документов, СУММА(Д.СуммаДокумента) КАК Сумма
ИЗ Документ.РеализацияТоваровУслуг КАК Д
ГДЕ Д.Проведен И Д.Дата МЕЖДУ &Начало И &Конец
СГРУППИРОВАТЬ ПО Д.Контрагент
УПОРЯДОЧИТЬ ПО Сумма УБЫВ
"""


def sales(a: dt.date, b: dt.date, label: str) -> str:
    rows = query(SALES_QUERY, {"Начало": dt.datetime.combine(a, dt.time()),
                               "Конец": dt.datetime.combine(b, dt.time(23, 59, 59))})
    if not rows:
        last = query("ВЫБРАТЬ МАКСИМУМ(Дата) КАК Д ИЗ Документ.РеализацияТоваровУслуг ГДЕ Проведен")[0]["Д"]
        tail = f" Последняя проведённая реализация в базе — {ddmmyyyy(last)}." if last else ""
        return f"Продаж {label} нет.{tail}"
    total = sum(r["Сумма"] for r in rows)
    docs = sum(int(r["Документов"]) for r in rows)
    lines = [f"Продажи {label}: {rub(total)} ({docs} док.)"]
    for i, r in enumerate(rows[:MAX_LINES], 1):
        lines.append(f"{i}. {r['Контрагент']} — {rub(r['Сумма'])}")
    if len(rows) > MAX_LINES:
        lines.append(f"… и ещё {len(rows) - MAX_LINES} покупателей")
    lines.append("\nПо проведённым документам «Реализация», суммы с НДС.")
    return "\n".join(lines)


STOCK_QUERY = """
ВЫБРАТЬ О.Субконто1 КАК Номенклатура, СУММА(О.КоличествоОстатокДт) КАК Количество, СУММА(О.СуммаОстатокДт) КАК Сумма
ИЗ РегистрБухгалтерии.Хозрасчетный.Остатки(&Период, Счет В ИЕРАРХИИ (ЗНАЧЕНИЕ(ПланСчетов.Хозрасчетный.Товары)), , ) КАК О
ГДЕ О.Субконто1.Наименование ПОДОБНО &Маска СПЕЦСИМВОЛ "~"
СГРУППИРОВАТЬ ПО О.Субконто1
УПОРЯДОЧИТЬ ПО Сумма УБЫВ
"""

STOCK_WORDS = re.compile(r"\b(какой|какие|сколько|остат\w*|товар\w*|на\s+склад\w*|склад\w*|есть|ли|у\s+нас|нас|по|на|у)\b", re.I)


def stock(question: str) -> str:
    rest = STOCK_WORDS.sub(" ", question.lower())
    rest = re.sub(r"[?!.,«»\"]", " ", rest)
    words = [w for w in rest.split() if len(w) > 2]
    if not words:
        return "Напишите, какой товар искать, например: «остаток товара масло моторное»."
    # ищем по первым буквам слов, чтобы «фильтры» нашли «фильтр»
    stems = [re.sub(r"[%_~\[\]]", "", w)[:max(4, len(w) - 2)] for w in words]
    mask = "%" + "%".join(stems) + "%"
    rows = query(STOCK_QUERY, {"Период": dt.datetime.now(), "Маска": mask})
    if not rows:
        return f"Товаров по запросу «{' '.join(words)}» на остатке нет (или такого товара нет в базе)."
    lines = [f"Остаток на складе (счёт 41), {dt.datetime.now():%d.%m.%Y %H:%M}:"]
    for r in rows[:MAX_LINES]:
        q = r["Количество"]
        q = int(q) if q == int(q) else round(q, 3)
        warn = " ⚠ минус: списано больше, чем пришло (ошибка учёта)" if q < 0 else ""
        lines.append(f"• {r['Номенклатура']} — {str(q).replace('.', ',')} ед., {rub(r['Сумма'])}{warn}")
    if len(rows) > MAX_LINES:
        lines.append(f"… и ещё {len(rows) - MAX_LINES} позиций, уточните название")
    return "\n".join(lines)


def stale(days: int = 90) -> str:
    text = (ROOT.parent / "1c-tools" / "queries" / "zalezhavshiesya.txt").read_text(encoding="utf-8")
    rows = query(text)
    today = dt.date.today()
    items = []
    for r in rows:
        ref = r["ПоследнийРасход"] or r["ПоследнийПриход"]
        d = (today - ref.date()).days if ref else None
        if d is None or d >= days:
            items.append((d, r))
    if not items:
        return f"Товаров без продаж дольше {days} дней нет."
    total = sum(r["Сумма"] for _, r in items)
    items.sort(key=lambda x: -x[1]["Сумма"])
    lines = [f"Без продаж {days}+ дней: {len(items)} позиций на {rub(total)}"]
    for d, r in items[:MAX_LINES]:
        lines.append(f"• {r['Номенклатура']} — {rub(r['Сумма'])}, {'движений нет' if d is None else f'{d} дн.'}")
    if len(items) > MAX_LINES:
        lines.append(f"… и ещё {len(items) - MAX_LINES}. Полный список — отчёт «Залежавшиеся товары» в 1С (Склад → Отчеты).")
    return "\n".join(lines)


# ---------- маршрутизация вопроса ----------

def route(question: str, today: dt.date | None = None) -> str | None:
    """Ответ по данным 1С или None, если вопрос не про данные (тогда ищем в инструкциях)."""
    today = today or dt.date.today()
    t = question.lower().replace("ё", "е")
    # «как / где / почему / что значит / ошибка / отчёт» — это вопрос про работу в 1С, отвечают инструкции
    if INSTRUCTION.search(t):
        return None

    if re.search(r"долж|долг|задолж|дебитор|не оплатил|не заплатил", t):
        on = parse_date(t, today)
        overdue = bool(re.search(r"просроч", t))
        # название контрагента — это то, что осталось после служебных слов и дат
        leftover = [w for w in re.findall(r"[a-zа-я0-9-]+", DEBT_WORDS.sub(" ", t)) if len(w) > 2]
        return debts(on=on, contractor_question=question if leftover else None, overdue_only=overdue)
    if re.search(r"продаж|продал|выручк|реализац\w* за|отгруз", t):
        p = parse_period(t, today)
        if not p:
            return "За какой период? Например: «продажи за октябрь», «продажи за прошлый месяц», «продажи за 2025 год»."
        return sales(*p)
    if re.search(r"залеж|неликвид|не продает|не продаются|без продаж|лежит на складе", t):
        m = re.search(r"(\d+)\s*(дн|дня|дней)", t)
        return stale(int(m.group(1)) if m else 90)
    if re.search(r"остат|на складе", t):
        return stock(question)
    return None


INSTRUCTION = re.compile(
    r"^\s*(как|где|почему|зачем|что\s+(значит|значат|делать|такое)|можно\s+ли|надо\s+ли|нужно\s+ли)\b"
    r"|ошибк|инструкц|отчет|csv|выгруз|загруз|настро|установ|чтобы\s+попасть")

_MONTH_WORDS ="|".join(m + r"\w*" for m in MONTHS if m != "ма") + "|мая|май"
DEBT_WORDS = re.compile(
    r"\b(кто|что|какой|какие|какая|сколько|нам|нас|мне|все|всех|список|покажи|скажи|выведи|дай|по|на|у|от|за|был|были|была|"
    r"есть|ли|сейчас|сегодня|вчера|итог\w*|общ\w*|сумм\w*|долж\w*|долг\w*|задолж\w*|дебитор\w*|просроч\w*|"
    r"покупател\w*|клиент\w*|контрагент\w*|не|оплатил\w*|заплатил\w*|год\w*|г|\d+[.\d]*|" + _MONTH_WORDS + r")\b", re.I)


def safe_route(question: str) -> str | None:
    """route() с понятной ошибкой вместо падения бота."""
    try:
        return route(question)
    except Exception as e:  # COM рвётся, если 1С обновили или база заблокирована
        reset()
        return f"Не получилось получить данные из 1С: {e}. Проверьте, что база доступна, и спросите ещё раз."


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "кто нам должен"
    print(route(q) or "(вопрос не про данные 1С — бот будет искать в инструкциях)")
