#!/usr/bin/env python3
"""2026-10-13 清洗复审：剔除清单与报告生成（一次性）

依据 sft_dataset_spec.md §3 清洗规则：
  R1 zh 译文 <2 字符剔除
  R2 纯语气词（ja 侧命中语气词表，或 zh 去标点后全为语气字）剔除
  R3 跨源去重：text_ja 归一化（片假名→平假名、去标点空白）为键，
     保留优先级最高来源的一条（tv > game > anime，同源保留首次出现）
剔除条目不改源文件，仅写入 99_logs/cleaning_20261013/exclusions.jsonl 供数据集构造消费。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"
OUT = ROOT / "99_logs" / "cleaning_20261013"

FILES = {  # 优先级从高到低
    "tv": "fanmade_tomori_quotes_bv1jaclz8erb.zh.jsonl",
    "game": "game_tomori_garupa_dryvoice.zh.jsonl",
    "anime": "anime_tomori_quotes_bv1jfzjycef2.zh.jsonl",
}
JA_FILLER = {"うん", "はい", "えっと", "あ", "う", "はぁ", "うんうん", "ああ", "え"}
ZH_FILLER_CHARS = set("嗯啊呀哎欸诶哦噢呜咦哈呵嘛呢吧啦")

KATA2HIRA = {chr(k): chr(k - 0x60) for k in range(0x30A1, 0x30F7)}


def norm_ja(t):
    return re.sub(r"[^\wぁ-ゖァ-ヺー]+", "", (t or "").translate(KATA2HIRA))


def zh_filler(t):
    s = re.sub(r"[\s。．.!！?？，,、…～~?？'’]", "", t)
    return bool(s) and all(c in ZH_FILLER_CHARS for c in s)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs = {}
    for k, f in FILES.items():
        recs[k] = [json.loads(l) for l in (C / f).read_text(encoding="utf-8").splitlines() if l.strip()]

    excl = {}  # id -> {file, reason}

    # R1
    for k in FILES:
        for r in recs[k]:
            if len(re.sub(r"\s", "", r["text"])) < 2:
                excl[r["id"]] = {"file": FILES[k], "reason": "R1 超短(<2字)"}

    # R2
    for k in FILES:
        for r in recs[k]:
            if norm_ja(r.get("text_ja")) in JA_FILLER or zh_filler(r["text"]):
                excl.setdefault(r["id"], {"file": FILES[k], "reason": "R2 纯语气词"})

    # R3（归一化键跨源/源内去重，保优先级最高一条）
    by_key = {}
    for k in FILES:  # dict 保序 = 优先级序
        for r in recs[k]:
            by_key.setdefault(norm_ja(r.get("text_ja")), []).append((k, r))
    dup_groups = []
    for key, v in by_key.items():
        if len(v) > 1:
            keep = v[0]
            dup_groups.append({
                "key": key[:40],
                "keep": keep[1]["id"],
                "drop": [x[1]["id"] for x in v[1:]],
            })
            for src, x in v[1:]:
                item = {"file": FILES[src], "reason": f"R3 跨源重复(留 {keep[1]['id']})"}
                if x["id"] not in excl:
                    excl[x["id"]] = item
                else:
                    excl[x["id"]]["reason"] += " + R3重复"

    order = {f: i for i, f in enumerate(FILES.values())}
    rows = sorted(excl.items(), key=lambda kv: (order[kv[1]["file"]], kv[0]))
    with (OUT / "exclusions.jsonl").open("w", encoding="utf-8") as fh:
        for rid, info in rows:
            fh.write(json.dumps({"id": rid, **info}, ensure_ascii=False) + "\n")

    per_file = {}
    for rid, info in rows:
        per_file.setdefault(info["file"], {"R1": 0, "R2": 0, "R3": 0, "计": 0})
        per_file[info["file"]]["计"] += 1
        for tag in ("R1", "R2", "R3"):
            if tag in info["reason"]:
                per_file[info["file"]][tag] += 1

    total_in = sum(len(v) for v in recs.values())
    print(f"总量 {total_in} -> 剔除 {len(rows)} -> 进入数据集构造 {total_in - len(rows)}")
    for f, n in per_file.items():
        print(f"  {f}: 剔除 {n['计']} (R2 {n['R2']} / R3 {n['R3']} / R1 {n['R1']})")
    print(f"重复组 {len(dup_groups)} 个；明细 -> {OUT / 'exclusions.jsonl'}")
    (OUT / "dup_groups.json").write_text(
        json.dumps(dup_groups, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
