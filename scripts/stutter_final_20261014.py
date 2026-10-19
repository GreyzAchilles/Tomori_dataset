#!/usr/bin/env python3
"""结巴终态校正（2026-10-14，用户裁定：1-2%，仅负面语境）

背景：clean_fix 第 8/9 轮用子串替换，重跑时第 8 轮被重复应用产生「但、但、但是」，
第 9 轮只回退一层。本脚本改为终态整句覆写：
  1) 全量去结巴（迭代折叠 X、X → X）
  2) 按 KEEP 表回写 19 处负面语境保留项（单层结巴终态）
  3) 同步 pilot.jsonl 与 batches_v2/*.jsonl 的 gpt 轮副本
幂等：重复运行结果不变。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"
WORK = ROOT / "99_logs" / "dialogue_work"

STUT = re.compile(r"([\u4e00-\u9fff])、\1")

# 负面语境保留项（失落/犹豫/恐惧/自责/慌乱），id -> 终态文本
KEEP = {
    "fanmade_bv1jaclz8erb_0002": "可、可是，没有祥子酱的话……",
    "fanmade_bv1jaclz8erb_0048": "啊、那个、那、那个，这里。",
    "fanmade_bv1jaclz8erb_0087": "可、可是，即便如此……",
    "anime_bv1jfzjycef2_0011": "但、但是，这首歌却……",
    "anime_bv1jfzjycef2_0027": "我、我还没有……",
    "game_tomori_dryvoice_0078": "呃，那个，有、有客人来吗？",
    "game_tomori_dryvoice_0313": "对、对不起，卡拉OK？",
    "game_tomori_dryvoice_0322": "啊，对、对不起。",
    "game_tomori_dryvoice_0367": "我、我不明白……",
    "game_tomori_dryvoice_0369": "可、可是，我完全唱不出来……",
    "game_tomori_dryvoice_0403": "我、我不知道该用什么样的脸去见大家……",
    "game_tomori_dryvoice_0418": "只、只有我哭不出来……",
    "game_tomori_dryvoice_0425": "我、我没有珍贵的东西……",
    "game_tomori_dryvoice_0479": "没、没能传达出去……",
    "game_tomori_dryvoice_0567": "为、为什么会这样……",
    "game_tomori_dryvoice_0577": "好痛苦、好痛苦……",
    "game_tomori_dryvoice_0580": "我、我不想再经历这种事了……",
    "game_tomori_dryvoice_0641": "变得看、看不清了……",
    "game_tomori_dryvoice_0648": "没、没能成为真正的人……",
}


def destutter(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = STUT.sub(r"\1", text)
    return text


def main():
    # 1) 语料终态
    for f in sorted(C.glob("*.zh.jsonl")):
        recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        changed = 0
        for r in recs:
            if r["id"] in KEEP:
                want = KEEP[r["id"]]
            else:
                want = destutter(r["text"])
            if want != r["text"]:
                r["text"] = want
                changed += 1
        if changed:
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        print(f"{f.name}: 终态覆写 {changed} 条")

    # 2) 对话副本（仅 gpt 轮 = 语料拷贝）
    targets = [ROOT / "30_sft_dataset" / "dialogue" / "pilot.jsonl"] + sorted((WORK / "batches_v2").glob("*.jsonl"))
    for p in targets:
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        changed = 0
        for r in recs:
            for t in r["conversations"]:
                if t["from"] != "gpt":
                    continue
                want = destutter(t["value"])
                if want != t["value"]:
                    t["value"] = want
                    changed += 1
        if changed:
            p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        print(f"{p.name}: 副本同步 {changed} 条")

    # 3) 复测
    excl = {json.loads(l)["id"] for l in (ROOT / "99_logs/cleaning_20261013/exclusions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    n = t = 0
    for f in sorted(C.glob("*.zh.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r["id"] not in excl:
                t += 1
                if STUT.search(r["text"]):
                    n += 1
    print(f"语料结巴终态: {n}/{t} = {n/t:.1%}（保留项 {len(KEEP)}）")


if __name__ == "__main__":
    main()
