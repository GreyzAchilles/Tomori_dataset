#!/usr/bin/env python3
"""汇总阶段 C 试点：合并批次 → 去重 → pilot.jsonl + 统计

用法：python dialogue_assemble.py
输入：99_logs/dialogue_work/seeds.json + batches/batch*.jsonl（均已过 dialogue_gate）
输出：30_sft_dataset/dialogue/pilot.jsonl（ShareGPT + source/line_ids/theme 溯源字段）
     统计写 99_logs/dialogue_build_pilot.md，摘要打 stdout
退出码 0 = 成功；1 = 有批次文件缺失或复核失败
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "99_logs" / "dialogue_work"
OUT = ROOT / "30_sft_dataset" / "dialogue"
C = ROOT / "20_corpus_cleaned"
EXCL = ROOT / "99_logs" / "cleaning_20261013" / "exclusions.jsonl"


def main():
    excl = {json.loads(l)["id"] for l in EXCL.read_text(encoding="utf-8").splitlines() if l.strip()}
    text2ids = {}
    for f in C.glob("*.zh.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] not in excl:
                text2ids.setdefault(r["text"].strip(), []).append(r["id"])

    seeds = json.loads((WORK / "seeds.json").read_text(encoding="utf-8"))
    seen = set()
    n_dup = 0
    convs = []
    reuse = {}
    problems = []
    for name in sorted(seeds):
        p = WORK / "batches" / f"{name}.jsonl"
        if not p.exists():
            problems.append(f"批次文件缺失: {name}")
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            conv = rec["conversations"]
            # 复核（门已过，这里防文件被改）
            if conv[0]["from"] != "human" or conv[-1]["from"] != "gpt":
                problems.append(f"{name}: 存在非 human 开头样本")
                continue
            gpts = [t["value"].strip() for t in conv if t["from"] == "gpt"]
            if any(g not in text2ids for g in gpts):
                problems.append(f"{name}: 存在非语料原文 gpt 轮")
                continue
            key = hashlib.md5(
                "|".join([t["value"] for t in conv]).encode()).hexdigest()
            if key in seen:
                n_dup += 1
                continue
            seen.add(key)
            ids = []
            for g in gpts:
                ids.extend(text2ids[g])
                reuse[g] = reuse.get(g, 0) + 1
            convs.append({"conversations": conv, "theme": name,
                          "source": f"dialogue_pilot_{len(convs) + 1:04d}",
                          "line_ids": ids})
    if problems:
        for x in problems:
            print("PROBLEM", x)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "pilot.jsonl").open("w", encoding="utf-8") as f:
        for rec in convs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    n_turn = {2: 0, 4: 0, 6: 0}
    for rec in convs:
        n_turn[len(rec["conversations"])] = n_turn.get(len(rec["conversations"]), 0) + 1
    used = sorted(reuse.items(), key=lambda kv: -kv[1])
    lines = [
        "# 阶段 C 试点构造报告（D1+D2，语料锚定生成）", "",
        f"- 对话总数：**{len(convs)}**（批内去重剔除 {n_dup} 条完全重复）",
        f"- 轮数分布：2 轮 {n_turn.get(2, 0)} / 4 轮 {n_turn.get(4, 0)} / 6 轮 {n_turn.get(6, 0)}",
        f"- 台词复用：覆盖 {len(reuse)} 条不同台词；最高复用 {used[0][1]} 次"
        if used else "- 台词复用：无",
        "",
        "## 复用最高的 10 条台词", "",
    ]
    for t, n in used[:10]:
        lines.append(f"- {n} 次：{t[:36]}")
    lines += ["", "## 每主题条数", ""]
    from collections import Counter
    for theme, n in Counter(r["theme"] for r in convs).most_common():
        lines.append(f"- {theme}: {n}")
    (ROOT / "99_logs" / "dialogue_build_pilot.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"assembled {len(convs)} conversations (dups {n_dup}) -> pilot.jsonl")


if __name__ == "__main__":
    main()
