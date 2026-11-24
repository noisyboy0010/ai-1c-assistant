"""RAG-ассистент по инструкциям 1С.

Ищет ответ в папке docs (md, txt, pdf, docx) и отвечает с указанием источника.
Поиск гибридный: BM25 с русским стеммингом (точные слова) + векторный поиск по смыслу
(эмбеддинги, модель potion-multilingual-128M, работает на процессоре). Результаты
объединяются методом RRF. Если пакет fastembed не установлен, работает только BM25.
Ответ: Claude API, если задан ключ; без ключа выдаёт найденные фрагменты инструкций.

    python rag.py ask "Где найти загрузку счетов из Excel?"
    python rag.py chat
    python rag.py index
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import requests
import snowballstemmer

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
MODEL = os.getenv("RAG_MODEL", "claude-sonnet-5-5")
API_URL = os.getenv("RAG_API_URL", "https://api.anthropic.com/v1/messages")
TOP_K = 4
MIN_COVERAGE = 0.4  # только BM25: лучший фрагмент должен покрывать 40% веса слов вопроса
# Гибрид: релевантность = покрытие слов + VEC_WEIGHT × близость по смыслу.
# На наборе для настройки вопросы по теме и не по теме пересекаются в зоне 1.0–1.3, поэтому:
# - ниже MIN_RELEVANCE — уверенный отказ («в инструкциях нет»);
# - от MIN_RELEVANCE до SURE_RELEVANCE — «серая зона»: фрагменты отдаём, решает Claude
#   (без Claude пользователь видит пометку, что точного ответа может не быть);
# - от SURE_RELEVANCE — уверенный ответ.
VEC_WEIGHT = 2.0
MIN_RELEVANCE = 0.9
SURE_RELEVANCE = 1.3
EMB_MODEL = os.getenv("RAG_EMB_MODEL", "minishlab/potion-multilingual-128M")
RRF_K = 60
CHUNK_CHARS = 1200
PREFIX = 5  # обрезка основы слова: «загрузить», «загрузка» → «загру», «обновить», «обновление» → «обнов»



STOP = set("""и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня
еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя
ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда
кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда
можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя
впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это как-то также
почему сколько каком какие каких который которые нужно the a an of to in is are and or for on""".split())

_ru = snowballstemmer.stemmer("russian")
_en = snowballstemmer.stemmer("english")


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zа-яё0-9]+", text.lower().replace("ё", "е"))
    out = []
    for w in words:
        if w in STOP or len(w) < 2 and not w.isdigit():
            continue
        stem = _ru.stemWord(w) if re.search("[а-я]", w) else _en.stemWord(w)
        out.append(stem[:PREFIX] if PREFIX else stem)
    return out


# ---------- загрузка документов ----------

@dataclass
class Chunk:
    source: str   # имя файла
    section: str  # заголовок раздела
    text: str


def read_file(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in (".md", ".txt"):
        return path.read_text(encoding="utf-8")
    if suf == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    if suf == ".docx":
        import docx
        d = docx.Document(path)
        lines = []
        for p in d.paragraphs:
            style = (p.style.name or "").lower()
            if style.startswith("heading") or style.startswith("заголовок"):
                level = 1 if style.rstrip().endswith(" 1") else 2  # «Заголовок 1» — название документа
                lines.append("#" * level + " " + p.text)
            else:
                lines.append(p.text)
        return "\n\n".join(lines)
    return ""


def split_long(text: str) -> list[str]:
    """Режет длинный раздел по абзацам на куски до CHUNK_CHARS."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            parts.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


def chunk_document(name: str, text: str) -> list[Chunk]:
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else Path(name).stem
    chunks = []
    # делим по заголовкам ## (и ###); вступление до первого заголовка — свой раздел
    pieces = re.split(r"^(#{2,3}\s+.+)$", text, flags=re.M)
    intro = re.sub(r"^#\s+.+$", "", pieces[0], flags=re.M).strip()
    sections = [(title, intro)] if intro else []
    for i in range(1, len(pieces), 2):
        sections.append((pieces[i].lstrip("#").strip(), pieces[i + 1].strip()))
    for head, body in sections:
        if not body:
            continue
        for part in split_long(body):
            label = title if head == title else f"{title} → {head}"
            chunks.append(Chunk(name, label, part))
    return chunks


def load_chunks(folder: Path = DOCS) -> list[Chunk]:
    chunks = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() in (".md", ".txt", ".pdf", ".docx") and path.is_file():
            chunks += chunk_document(path.name, read_file(path))
    return chunks


# ---------- поиск ----------

class Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75, use_vectors: bool = True):
        self.chunks = chunks
        self.k1, self.b = k1, b
        # заголовок раздела учитываем дважды: он точнее всего говорит, о чём кусок
        self.docs = [tokens(c.section) * 2 + tokens(c.text) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.vectors = None
        if use_vectors:
            try:
                self.vectors = Vectors(chunks)
            except ImportError:
                pass  # fastembed не установлен — работаем только на BM25

    def search(self, query: str, k: int = TOP_K) -> list[tuple[float, Chunk, float]]:
        """Оценка = BM25 × покрытие запроса.

        Покрытие — какая доля «веса» слов вопроса нашлась во фрагменте. Слова, которых нет
        во всей базе (например «зарплата», если про ЗУП инструкций нет), получают максимальный вес.
        Так вопрос не по теме не цепляется за одно общее слово вроде «бухгалтерия».
        """
        q = list(dict.fromkeys(tokens(query)))
        if not q:
            return []
        max_idf = max(self.idf.values(), default=1.0)
        weight = {t: self.idf.get(t, max_idf) for t in q}
        total = sum(weight.values())
        scored = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = cov = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                    cov += weight[t]
            if s > 0:
                scored.append((s * cov / total, self.chunks[i], cov / total))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]

    # ---------- гибрид ----------

    def hybrid(self, query: str, k: int = TOP_K) -> list[Hit]:
        """BM25 + векторный поиск, объединение по рангам (Reciprocal Rank Fusion)."""
        bm = self.search(query, len(self.chunks))
        cov_by = {id(c): cov for _, c, cov in bm}
        rrf: dict[int, float] = {}
        for rank, (_, c, _) in enumerate(bm):
            rrf[id(c)] = 1 / (RRF_K + rank + 1)
        vec = self.vectors.similarity(query) if self.vectors else None
        if vec is not None:
            order = sorted(range(len(self.chunks)), key=lambda i: -vec[i])
            for rank, i in enumerate(order):
                c = self.chunks[i]
                rrf[id(c)] = rrf.get(id(c), 0) + 1 / (RRF_K + rank + 1)
        hits = [Hit(rrf.get(id(c), 0), c, cov_by.get(id(c), 0.0), float(vec[i]) if vec is not None else 0.0)
                for i, c in enumerate(self.chunks) if id(c) in rrf]
        hits.sort(key=lambda h: -h.score)
        return hits[:k]


@dataclass
class Hit:
    score: float     # итоговая оценка RRF
    chunk: Chunk
    coverage: float  # доля веса слов вопроса, найденная во фрагменте (BM25)
    vec: float       # косинусная близость по смыслу (0, если векторов нет)


class Vectors:
    """Эмбеддинги фрагментов; кэшируются в .cache, пересчитываются только при изменении текстов."""

    def __init__(self, chunks: list[Chunk]):
        import hashlib

        import numpy as np
        from fastembed import TextEmbedding

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        self.np = np
        self.model = TextEmbedding(EMB_MODEL, cache_dir=str(ROOT / ".models"))
        texts = [f"{c.section}. {c.text}" for c in chunks]
        key = hashlib.sha1((EMB_MODEL + "\x00".join(texts)).encode("utf-8")).hexdigest()[:16]
        cache = ROOT / ".cache" / f"emb_{key}.npy"
        if cache.exists():
            m = np.load(cache)
        else:
            m = np.array(list(self.model.embed(texts)), dtype=np.float32)
            m /= np.linalg.norm(m, axis=1, keepdims=True)
            cache.parent.mkdir(exist_ok=True)
            for old in cache.parent.glob("emb_*.npy"):
                old.unlink()
            np.save(cache, m)
        self.matrix = m

    def similarity(self, query: str):
        v = next(iter(self.model.embed([query])))
        v = v / self.np.linalg.norm(v)
        return self.matrix @ v


# ---------- ответ ----------

SYSTEM = """Ты помощник пользователей 1С. Отвечай только по фрагментам инструкций, которые даны ниже.
Правила:
- Если ответа во фрагментах нет, так и скажи: «В инструкциях этого нет», и посоветуй обратиться к администратору 1С. Не придумывай.
- Пиши коротко и простыми словами, по шагам, если это действие.
- В конце укажи источники в квадратных скобках номерами фрагментов, например [1], [3]."""


def read_secret(env: str, target: str) -> str | None:
    """Секрет из переменной окружения или из Диспетчера учётных данных Windows (общие учётные данные)."""
    if os.getenv(env):
        return os.getenv(env)
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class CRED(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                        ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]
        p = ctypes.POINTER(CRED)()
        adv = ctypes.windll.advapi32
        if not adv.CredReadW(target, 1, 0, ctypes.byref(p)):
            return None
        blob = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
        adv.CredFree(p)
        try:
            return blob.decode("utf-16-le")
        except UnicodeDecodeError:
            return blob.decode("utf-8")
    except Exception:
        return None


def api_key() -> str | None:
    return read_secret("ANTHROPIC_API_KEY", "RAG1C_Anthropic")


def relevance(index: Index, question: str) -> float:
    """Насколько вопрос про содержимое инструкций: лучшее покрытие слов + вес × лучшая близость по смыслу."""
    hits = index.hybrid(question, len(index.chunks))
    if not hits:
        return 0.0
    cov = max(h.coverage for h in hits)
    if index.vectors is None:
        return cov
    return cov + VEC_WEIGHT * max(h.vec for h in hits)


def relevant(index: Index, question: str) -> list[tuple[float, Chunk]]:
    """Фрагменты для ответа. Пусто, если вопрос не про содержимое инструкций."""
    threshold = MIN_RELEVANCE if index.vectors is not None else MIN_COVERAGE
    if relevance(index, question) < threshold:
        return []
    hits = index.hybrid(question)
    best = hits[0].score
    return [(h.score, h.chunk) for h in hits if h.score >= 0.6 * best]


def context_block(hits: list[tuple[float, Chunk]]) -> str:
    return "\n\n".join(f"[{i}] {c.section} ({c.source})\n{c.text}" for i, (_, c) in enumerate(hits, 1))


def sources(hits) -> str:
    return "\n".join(f"[{i}] {c.section} — {c.source}" for i, (_, c) in enumerate(hits, 1))


def answer(index: Index, question: str) -> str:
    hits = relevant(index, question)
    if not hits:
        return "В инструкциях этого нет. Обратитесь к администратору 1С."
    key = api_key()
    if not key:
        top = hits[:2]
        body = "\n\n".join(f"[{i}] {c.section}\n{c.text}" for i, (_, c) in enumerate(top, 1))
        unsure = index.vectors is not None and relevance(index, question) < SURE_RELEVANCE
        head = ("Точного ответа в инструкциях может не быть. Ближайшее по смыслу:" if unsure
                else "Подходящие места из инструкций:")
        return "(Нейросеть не подключена.) " + head + "\n\n" + body + "\n\nИсточники:\n" + sources(top)
    r = requests.post(API_URL, timeout=60, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        data=json.dumps({
            "model": MODEL, "max_tokens": 800, "system": SYSTEM,
            "messages": [{"role": "user", "content": f"Фрагменты инструкций:\n\n{context_block(hits)}\n\nВопрос: {question}"}],
        }))
    if r.status_code != 200:
        return f"Ошибка Claude API {r.status_code}: {r.text[:300]}"
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    return text.strip() + "\n\nИсточники:\n" + sources(hits)


_INDEX: Index | None = None


def get_index() -> Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(load_chunks())
    return _INDEX


def main():
    ap = argparse.ArgumentParser(description="RAG-ассистент по инструкциям 1С")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="задать один вопрос")
    a.add_argument("question")
    s = sub.add_parser("search", help="показать найденные фрагменты и их оценки")
    s.add_argument("question")
    sub.add_parser("chat", help="диалог в консоли")
    sub.add_parser("index", help="статистика базы знаний")
    args = ap.parse_args()

    idx = get_index()
    if args.cmd == "index":
        files = Counter(c.source for c in idx.chunks)
        print(f"Фрагментов: {len(idx.chunks)}, файлов: {len(files)}")
        for f, n in files.items():
            print(f"  {f}: {n}")
        print("Векторный поиск:", f"включён ({EMB_MODEL})" if idx.vectors else "выключен (нет пакета fastembed)")
        print("Claude API:", "подключён" if api_key() else "не подключён (ответ — фрагменты инструкций)")
    elif args.cmd == "search":
        thr = f"отказ ниже {MIN_RELEVANCE}, уверенно от {SURE_RELEVANCE}" if idx.vectors else f"порог {MIN_COVERAGE}"
        print(f"Релевантность вопроса: {relevance(idx, args.question):.2f} ({thr})")
        for h in idx.hybrid(args.question):
            print(f"{h.score:.4f}  слова {h.coverage:.0%}  смысл {h.vec:.2f}  {h.chunk.section}  ({h.chunk.source})")
    elif args.cmd == "ask":
        print(answer(idx, args.question))
    else:
        print("Задайте вопрос по 1С. Пустая строка — выход.")
        while True:
            try:
                q = input("\n> ").strip()
            except EOFError:
                break
            if not q:
                break
            print(answer(idx, q))


if __name__ == "__main__":
    main()
