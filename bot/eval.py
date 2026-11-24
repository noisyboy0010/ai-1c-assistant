"""Проверка качества поиска: для каждого вопроса известно, в каком файле ответ.

    python eval.py            # гибрид (BM25 + векторы)
    python eval.py --bm25     # только BM25, для сравнения

Два набора:
- «настройка» — на этих вопросах подбирались пороги, цифры по ним оптимистичны;
- «контроль» — вопросы, которые при настройке не использовались. Честная оценка — по ним.

Для каждого набора считает hit@1 / hit@3 (нужный файл первым / в первых трёх),
сколько вопросов по теме бот берётся отвечать и как часто отказывает на вопросы не по теме.
"""
import sys

from rag import SURE_RELEVANCE, Index, load_chunks, relevance, relevant

sys.stdout.reconfigure(encoding="utf-8")

TUNE_ON = [
    ("Где найти загрузку счетов из Excel?", "zagruzka-schetov-iz-excel.md"),
    ("Какие колонки обязательны в файле со счетами?", "zagruzka-schetov-iz-excel.md"),
    ("Ошибка ИНН должен содержать 10 или 12 цифр, что делать?", "zagruzka-schetov-iz-excel.md"),
    ("Если загрузить тот же файл второй раз, будут дубли?", "zagruzka-schetov-iz-excel.md"),
    ("Что будет, если покупателя нет в базе?", "zagruzka-schetov-iz-excel.md"),
    ("Как несколько строк попадают в один счёт?", "zagruzka-schetov-iz-excel.md"),
    ("Не удалось сохранить временный файл", "ustanovka-rasshireniy.md"),
    ("Как установить расширение cfe?", "ustanovka-rasshireniy.md"),
    ("Почему после установки не видно команды?", "ustanovka-rasshireniy.md"),
    ("Как обновить расширение до новой версии?", "ustanovka-rasshireniy.md"),
    ("Где отчёт по залежавшимся товарам?", "otchet-zalezhavshiesya-tovary.md"),
    ("Как считаются дни без продаж?", "otchet-zalezhavshiesya-tovary.md"),
    ("Что значат отрицательные остатки в отчёте?", "otchet-zalezhavshiesya-tovary.md"),
    ("Какой порог дней по умолчанию?", "otchet-zalezhavshiesya-tovary.md"),
    ("Что делать с товарами, которые лежат больше года?", "otchet-zalezhavshiesya-tovary.md"),
    ("Как выгрузить дебиторскую задолженность в CSV?", "analitika-cherez-com.md"),
    ("COM перестал работать после обновления платформы", "analitika-cherez-com.md"),
    ("Какая роль нужна для внешнего соединения?", "analitika-cherez-com.md"),
    ("Как проверить подключение к базе?", "analitika-cherez-com.md"),
    ("где отчёт по залежавшимся", "otchet-zalezhavshiesya-tovary.md"),
    ("ошибка ИНН", "zagruzka-schetov-iz-excel.md"),
    ("безопасный режим", "ustanovka-rasshireniy.md"),
    ("дубли счетов", "zagruzka-schetov-iz-excel.md"),
    ("обновить расширение", "ustanovka-rasshireniy.md"),
    ("не грузится файл эксель", "zagruzka-schetov-iz-excel.md"),
]

TUNE_OFF = [
    "Как приготовить борщ?",
    "Какая погода завтра в Москве?",
    "Кто выиграл чемпионат мира по футболу?",
    "Как рассчитать зарплату в ЗУП?",
    "Как закрыть месяц в бухгалтерии?",
    "Как сдать декларацию по НДС?",
    "Как закрыть месяц?",
    "Как настроить ЭДО?",
    "Как начислить отпуск?",
    "Как выставить УПД?",
    "Как настроить обмен с сайтом?",
    "Как распечатать счёт?",
    "Где посмотреть остатки на складе?",
]

# Контрольные вопросы: не использовались при подборе порогов.
TEST_ON = [
    ("Можно загрузить счета из файла csv?", "zagruzka-schetov-iz-excel.md"),
    ("Excel съел ноль в начале ИНН", "zagruzka-schetov-iz-excel.md"),
    ("сколько дней товар должен лежать чтобы попасть в отчёт", "otchet-zalezhavshiesya-tovary.md"),
    ("какие товары пора распродавать", "otchet-zalezhavshiesya-tovary.md"),
    ("куда пропала кнопка после установки доработки", "ustanovka-rasshireniy.md"),
    ("надо ли удалять старую версию расширения", "ustanovka-rasshireniy.md"),
    ("как сохранить результат запроса в файл", "analitika-cherez-com.md"),
    ("скрипт не подключается к базе, ошибка доступа", "analitika-cherez-com.md"),
    ("как поменять колонку если программа выбрала не ту", "zagruzka-schetov-iz-excel.md"),
    ("что значит прочерк в днях без продаж", "otchet-zalezhavshiesya-tovary.md"),
]

TEST_OFF = [
    "Как оформить больничный?",
    "Как создать новую организацию?",
    "Как сделать резервную копию базы?",
    "Как настроить кассу для розницы?",
    "Как посчитать амортизацию основных средств?",
    "Посоветуй хороший фильм",
]


def run(idx, on, off, title):
    print(f"\n===== {title} =====")
    h1 = h3 = answered = 0
    for q, expected in on:
        found = [h.chunk.source for h in idx.hybrid(q, 3)]
        ok1 = bool(found) and found[0] == expected
        ok3 = expected in found
        ans = bool(relevant(idx, q))
        h1 += ok1
        h3 += ok3
        answered += ans
        mark = ("OK " if ok1 else "~  " if ok3 else "ПРОМАХ") if ans else "ОТКАЗ"
        if mark != "OK ":
            print(f"{mark} {q}  ->  {found[0] if found else '-'}  (релевантность {relevance(idx, q):.2f})")
    refused = grey = 0
    for q in off:
        ans = bool(relevant(idx, q))
        refused += not ans
        if ans and idx.vectors is not None and relevance(idx, q) < SURE_RELEVANCE:
            grey += 1  # фрагменты уйдут в Claude, решает модель; без Claude — с пометкой «может не быть»
        elif ans:
            print(f"ЛОЖНЫЙ не по теме: {q}  (релевантность {relevance(idx, q):.2f})")
    n = len(on)
    print(f"hit@1: {h1}/{n}   hit@3: {h3}/{n}   отвечает по теме: {answered}/{n}   "
          f"не по теме: отказ {refused}, серая зона {grey}, уверенно-ложно {len(off) - refused - grey} из {len(off)}")


def main():
    idx = Index(load_chunks(), use_vectors="--bm25" not in sys.argv)
    print("Режим:", "гибрид BM25 + векторы" if idx.vectors else "только BM25")
    run(idx, TUNE_ON, TUNE_OFF, "Набор для настройки")
    run(idx, TEST_ON, TEST_OFF, "Контрольный набор")
    return 0


if __name__ == "__main__":
    sys.exit(main())
