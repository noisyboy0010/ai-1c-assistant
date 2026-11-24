"""Проверка отчёта «Залежавшиеся товары» через COM (только чтение).
   python tools/test_zalezh.py [порог_дней]
Сохраняет готовый отчёт в out/zalezhavshiesya_report.xlsx.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from onec import connect  # noqa: E402

c = connect()
m = c.аз_ЗалежавшиесяТоварыСервер
try:
    p = m.НовыеПараметры()
    if len(sys.argv) > 1:
        p.ПорогДней = int(sys.argv[1])
    t = m.ДанныеОтчета(p)
    pos = [t.Get(i) for i in range(t.Count()) if t.Get(i).Количество > 0]
    neg = [t.Get(i) for i in range(t.Count()) if t.Get(i).Количество < 0]
    print(f"Позиций с остатком: {len(pos)} на {sum(r.Сумма for r in pos):,.2f}; отрицательных: {len(neg)} на {sum(r.Сумма for r in neg):,.2f}")
    buckets = {}
    for r in pos:
        b = buckets.setdefault(r.Срок, [0, 0.0])
        b[0] += 1
        b[1] += float(r.Сумма)
    for k, (n, s) in buckets.items():
        print(f"  {k:22} {n:>4} {s:>14,.2f}")
    print("Топ-5 по сумме:")
    for r in sorted(pos, key=lambda r: -float(r.Сумма))[:5]:
        print(f"  {c.String(r.Номенклатура)[:50]:50} {float(r.Количество):>6} {float(r.Сумма):>12,.2f}  дней: {r.ДнейБезПродаж}")
    td = m.СформироватьОтчет(p)
    out = os.path.abspath("out/zalezhavshiesya_report.xlsx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    td.Write(out, c.SpreadsheetDocumentFileType.XLSX)
    print("Отчёт:", out, "строк:", td.TableHeight)
except Exception as e:  # noqa: BLE001
    info = getattr(e, "excepinfo", None)
    print("ОШИБКА:", info[2] if info else e)
    sys.exit(1)
