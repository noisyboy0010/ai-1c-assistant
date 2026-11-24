"""Проверка разбора Excel модулем расширения через COM (только чтение, документы не создаются).
   python tools/test_parse.py [файл.xlsx]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from onec import connect  # noqa: E402

path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "samples/счета_пример.xlsx")
c = connect()
m = c.зиэ_ЗагрузкаСчетовСервер
try:
    addr = c.PutToTempStorage(c.NewObject("BinaryData", path))
    data = m.ПрочитатьФайл(addr, os.path.basename(path))
    hdr = m.НайтиСтрокуЗаголовка(data)
    print("Строка заголовков:", hdr)
    mp = m.АвтоСопоставление(m.ЗаголовкиКолонок(data, hdr))
    for f in m.ОписаниеПолей():
        print(f"  {f.Представление:26} <- {c.String(mp.Get(f.Имя)) or '—'}")
    org = c.Catalogs.Организации.FindByDescription(os.environ.get("ONEC_TEST_ORG", "Моя организация"))
    t = m.РазобратьСтроки(data, hdr, mp, org)
    print()
    for i in range(t.Count()):
        r = t.Get(i)
        print(f"{int(r.НомерСтрокиФайла):>3} {r.КлючСчета:9} {c.String(r.Дата)[:10]} {r.ИНН:12} {r.Номенклатура[:38]:38} "
              f"{r.Количество:>4} x {r.Цена:>9} = {r.Сумма:>9} {r.СтавкаНДС:8} | {'✓' if r.Загружать else '✗'} {r.Статус}")
except Exception as e:  # noqa: BLE001
    info = getattr(e, "excepinfo", None)
    print("ОШИБКА:", info[2] if info else e)
    sys.exit(1)
