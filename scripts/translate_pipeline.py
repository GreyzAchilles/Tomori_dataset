#!/usr/bin/env python3
"""翻译流水线辅助脚本：提取（extract）与回填（merge）。

extract:
  读取 20_corpus_cleaned/ 下的日文 jsonl，生成带全局行号索引的翻译批次文件
  （99_logs/translate_work/batches/batch_NN.json，每批 batch_size 行），
  并输出 manifest（99_logs/translate_work/manifest.json）记录每个 i 对应的源文件与 id。

merge:
  读取收集到的翻译结果（JSON 数组 [{"i":..,"zh":..}]），校验覆盖率后：
  - 生成 <base>.ja.jsonl（原始日文版副本）
  - 生成 <base>.zh.jsonl（text=中文翻译, text_ja=日文原文, 其余字段不变）

用法：
  python translate_pipeline.py extract [file1.jsonl file2.jsonl ...]   # 缺省用 DEFAULT_SOURCES
  python translate_pipeline.py merge <translations.json|glob>
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEANED = ROOT / "20_corpus_cleaned"
WORK = ROOT / "99_logs" / "translate_work"
BATCHES = WORK / "batches"

DEFAULT_SOURCES = [
    "fanmade_tomori_quotes_bv1jaclz8erb.jsonl",
    "game_tomori_garupa_dryvoice.jsonl",
]
BATCH_SIZE = 50


def extract(sources=None):
    sources = sources or DEFAULT_SOURCES
    BATCHES.mkdir(parents=True, exist_ok=True)
    manifest = []
    i = 0
    for fname in sources:
        recs = [json.loads(l) for l in (CLEANED / fname).read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in recs:
            i += 1
            manifest.append({"i": i, "file": fname, "id": r["id"], "text": r["text"]})
    n_batches = (len(manifest) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        chunk = manifest[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
        payload = [{"i": m["i"], "text": m["text"]} for m in chunk]
        (BATCHES / f"batch_{b + 1:02d}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    WORK.joinpath("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"extracted {len(manifest)} lines -> {n_batches} batches (size={BATCH_SIZE}) -> {BATCHES}")


def parse_translations(raw):
    """容错解析：剥代码围栏，优先整段 JSON，失败则正则逐条提取。"""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
        return {int(d["i"]): str(d["zh"]).strip() for d in data if str(d.get("zh", "")).strip()}
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        pass
    out = {}
    for m in re.finditer(r'"i"\s*:\s*(\d+)\s*,\s*"zh"\s*:\s*"((?:[^"\\]|\\.)*)"', raw):
        try:
            zh = json.loads(f'"{m.group(2)}"')
        except json.JSONDecodeError:
            zh = m.group(2)
        if zh.strip():
            out[int(m.group(1))] = zh.strip()
    return out


def merge(translations_path):
    manifest = json.loads(WORK.joinpath("manifest.json").read_text(encoding="utf-8"))
    translations = {}
    # 支持多个结果文件合并传入（glob 模式）
    paths = sorted(Path().glob(translations_path)) if any(c in translations_path for c in "*?[") else [Path(translations_path)]
    for p in paths:
        chunk = parse_translations(p.read_text(encoding="utf-8"))
        print(f"  parsed {p.name}: {len(chunk)} translations")
        for k, v in chunk.items():
            translations.setdefault(k, v)

    missing = [m["i"] for m in manifest if m["i"] not in translations]
    if missing:
        print(f"ERROR: missing {len(missing)} translations: {missing[:20]}{'...' if len(missing) > 20 else ''}")
        sys.exit(1)

    by_file = {}
    for m in manifest:
        by_file.setdefault(m["file"], []).append(m)
    for fname, items in by_file.items():
        recs = [json.loads(l) for l in (CLEANED / fname).read_text(encoding="utf-8").splitlines() if l.strip()]
        rec_by_id = {r["id"]: r for r in recs}
        base = fname.replace(".jsonl", "")
        (CLEANED / f"{base}.ja.jsonl").write_text(
            (CLEANED / fname).read_text(encoding="utf-8"), encoding="utf-8")
        with (CLEANED / f"{base}.zh.jsonl").open("w", encoding="utf-8") as f:
            for m in items:
                r = rec_by_id[m["id"]]
                out = dict(r)
                out["text"] = translations[m["i"]]
                out["text_ja"] = m["text"]
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"  {fname}: {len(items)} entries -> {base}.ja.jsonl + {base}.zh.jsonl")
    print(f"merge OK: {len(translations)} translations, 0 missing")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("extract", "merge"):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "extract":
        extract(sys.argv[2:])
    else:
        if len(sys.argv) < 3:
            print("usage: translate_pipeline.py merge <translations.json|glob>")
            sys.exit(2)
        merge(sys.argv[2])
