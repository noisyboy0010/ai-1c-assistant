"""Тесты разбора вопросов про данные 1С. База 1С для них не нужна.

    python test_data1c.py

Проверяет: какие вопросы уходят в данные 1С, а какие в инструкции; как понимаются даты и периоды;
как находится контрагент по названию с другим окончанием.
"""
import datetime as dt
import sys

import data1c
import eval as rag_eval

sys.stdout.reconfigure(encoding="utf-8")

TODAY = dt.date(2026, 11, 14)
calls = []
data1c.debts = lambda **k: calls.append(("debts", k)) or "DATA"
data1c.sales = lambda a, b, label: calls.append(("sales", a, b)) or "DATA"
data1c.stock = lambda q: calls.append(("stock", q)) or "DATA"
data1c.stale = lambda days=90: calls.append(("stale", days)) or "DATA"

fails = 0


def check(cond, msg):
    global fails
    if not cond:
        fails += 1
        print("ОШИБКА:", msg)


# 1. Вопросы по инструкциям не должны уходить в данные
for q in [q for q, _ in rag_eval.TUNE_ON + rag_eval.TEST_ON] + rag_eval.TUNE_OFF + rag_eval.TEST_OFF:
    check(data1c.route(q, TODAY) is None, f"вопрос по инструкции ушёл в данные: {q}")

# 2. Вопросы про данные — в нужную функцию с нужными параметрами
CASES = [
    ("кто нам должен?", ("debts", {"on": None, "contractor_question": None, "overdue_only": False})),
    ("дебиторка", ("debts", {"on": None, "contractor_question": None, "overdue_only": False})),
    ("просроченные долги", ("debts", {"on": None, "contractor_question": None, "overdue_only": True})),
    ("кто был должен на 1 января 2024", ("debts", {"on": dt.date(2024, 1, 1), "contractor_question": None, "overdue_only": False})),
    ("долги на 01.11", ("debts", {"on": dt.date(2026, 11, 1), "contractor_question": None, "overdue_only": False})),
    ("сколько должен Ромашка", ("debts", {"on": None, "contractor_question": "сколько должен Ромашка", "overdue_only": False})),
    ("продажи за октябрь", ("sales", dt.date(2026, 10, 1), dt.date(2026, 10, 31))),
    ("продажи за декабрь", ("sales", dt.date(2025, 12, 1), dt.date(2025, 12, 31))),  # декабрь ещё не наступил — прошлый год
    ("выручка за 2023 год", ("sales", dt.date(2023, 1, 1), dt.date(2023, 12, 31))),
    ("продажи за прошлый месяц", ("sales", dt.date(2026, 10, 1), dt.date(2026, 10, 31))),
    ("продажи с 01.02 по 15.02", ("sales", dt.date(2026, 2, 1), dt.date(2026, 2, 15))),
    ("залежавшиеся товары", ("stale", 90)),
    ("какие товары не продаются больше 365 дней", ("stale", 365)),
    ("остаток масло гур", ("stock", "остаток масло гур")),
]
for q, expected in CASES:
    calls.clear()
    r = data1c.route(q, TODAY)
    check(r == "DATA" and calls and calls[0] == expected, f"{q}: ждали {expected}, получили {calls[:1] or r}")

check("За какой период" in (data1c.route("покажи продажи", TODAY) or ""), "без периода бот должен переспросить")

# 3. Поиск контрагента по названию
names = ['ООО "РОМАШКА"', "СЕВЕРНАЯ ГЭС-2 АО", "ТехСнабКомплект ООО", "ИП Петров Иван Сергеевич"]
check(data1c.match_names("долг северной гэс", names) == ["СЕВЕРНАЯ ГЭС-2 АО"], "окончание: «северной»")
check(data1c.match_names("должен ли техснабкомплект", names) == ["ТехСнабКомплект ООО"], "регистр букв")
check(data1c.match_names("сколько должен Петров", names) == ["ИП Петров Иван Сергеевич"], "фамилия ИП")
check(data1c.match_names("сколько должна Незабудка", names) == [], "несуществующий контрагент")

# 4. Формат денег
check(data1c.rub(1250000) == "1 250 000 ₽", data1c.rub(1250000))
check(data1c.rub(215817.52) == "215 817,52 ₽", data1c.rub(215817.52))

print("Все тесты пройдены" if not fails else f"Ошибок: {fails}")
sys.exit(1 if fails else 0)
