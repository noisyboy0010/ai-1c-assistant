"""Аналитика 1С через COM-соединение (V83.COMConnector).

Примеры:
  python onec.py ping
  python onec.py meta Documents
  python onec.py query "ВЫБРАТЬ ПЕРВЫЕ 10 Наименование ИЗ Справочник.Контрагенты"
  python onec.py query -f queries\\sales.txt --csv out\\sales.csv
"""
import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path

import pythoncom
import win32com.client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).with_name(".env"))


def connect():
    base = os.environ["ONEC_BASE"]
    s = f'File="{base}";Usr="{os.getenv("ONEC_USER", "")}";Pwd="{os.getenv("ONEC_PWD", "")}";'
    pythoncom.CoInitialize()
    return win32com.client.Dispatch("V83.COMConnector").Connect(s)


def to_py(conn, v):
    """Переводит значение 1С в обычное значение Python."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dt.datetime):
        v = v.replace(tzinfo=None)
        return None if v.year == 1 else v  # пустая дата 1С = 0001-01-01
    return conn.String(v)  # ссылки, перечисления и т.п. -> представление


def run_query(conn, text, params=None):
    q = conn.NewObject("Query")
    q.Text = text
    for k, v in (params or {}).items():
        q.SetParameter(k, v)
    table = q.Execute().Unload()
    cols = [table.Columns.Get(i).Name for i in range(table.Columns.Count())]
    rows = []
    for r in range(table.Count()):
        row = table.Get(r)
        rows.append([to_py(conn, row.Get(c)) for c in range(len(cols))])
    return cols, rows


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    m = sub.add_parser("meta")
    m.add_argument("kind", help="Documents, Catalogs, AccumulationRegisters, InformationRegisters, AccountingRegisters ...")
    q = sub.add_parser("query")
    q.add_argument("text", nargs="?")
    q.add_argument("-f", "--file")
    q.add_argument("--csv")
    q.add_argument("--limit", type=int, default=50, help="сколько строк печатать в консоль")
    a = ap.parse_args()

    conn = connect()

    if a.cmd == "ping":
        md = conn.Metadata
        print(f"OK: {md.Synonym} ({md.Name}), версия {md.Version}")
        return

    if a.cmd == "meta":
        coll = getattr(conn.Metadata, a.kind)
        for i in range(coll.Count()):
            o = coll.Get(i)
            print(f"{o.Name}\t{o.Synonym}")
        return

    text = Path(a.file).read_text(encoding="utf-8") if a.file else a.text
    cols, rows = run_query(conn, text)
    if a.csv:
        Path(a.csv).parent.mkdir(parents=True, exist_ok=True)
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cols)
            w.writerows(rows)
        print(f"{len(rows)} строк -> {a.csv}")
    print("\t".join(cols))
    for r in rows[: a.limit]:
        print("\t".join("" if v is None else str(v) for v in r))
    if len(rows) > a.limit:
        print(f"... всего {len(rows)} строк")


if __name__ == "__main__":
    main()
