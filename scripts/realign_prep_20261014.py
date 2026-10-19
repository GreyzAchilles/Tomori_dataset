#!/usr/bin/env python3
"""重对齐前置（2026-10-14）：

1) 残句收尾修复（用户裁定：残句 output 以省略号收尾传达迟疑/难过）：
   - 逗号结尾「……，」→「…………」（去逗号加省略号）
   - 悬挂连接词：「和。」「但是。」「心里也。」「那样的。」→ 去词/去句号 + 省略号
   - 完整句不动（的/了/也是。 等正常句末助词）
2) 追加试点 4 条剔除（0652 乱码 / 0516 人名不明 / 0518、0065 无实义）
3) 抽取通用桶（route==通用，剔除外）→ 99_logs/dialogue_work/realign_seeds.json（30 条/批）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_style_dataset import route

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"
EXCL = ROOT / "99_logs" / "cleaning_20261013" / "exclusions.jsonl"
OUT = ROOT / "99_logs" / "dialogue_work"

NEW_EXCL = [
    {"id": "game_tomori_dryvoice_0652", "file": "game_tomori_garupa_dryvoice.zh.jsonl",
     "reason": "R4 用户决策口径（严重乱码：佛学生是小云legs了）"},
    {"id": "game_tomori_dryvoice_0516", "file": "game_tomori_garupa_dryvoice.zh.jsonl",
     "reason": "R4 用户决策口径（人名「桥本」指代不明）"},
    {"id": "game_tomori_dryvoice_0518", "file": "game_tomori_garupa_dryvoice.zh.jsonl",
     "reason": "R4 用户决策口径（无实义残句「吗……」）"},
    {"id": "game_tomori_dryvoice_0065", "file": "game_tomori_garupa_dryvoice.zh.jsonl",
     "reason": "R4 用户决策口径（无实义应答「不过，嗯。」）"},
]

# 残句修复规则：逗号结尾→省略号；悬挂连接词「和」删除；其余残尾保留词换省略号
def fix_dangling(text: str):
    t = text.rstrip()
    if t.endswith("，"):
        return t[:-1] + "……"
    if t.endswith("和。"):
        return t[:-2] + "……"
    for suffix in ("但是。", "心里也。", "那样的。"):
        if t.endswith(suffix):
            return t[:-1] + "……"
    return text


def main():
    # 1) 剔除追加
    have = {json.loads(l)["id"] for l in EXCL.read_text(encoding="utf-8").splitlines() if l.strip()}
    with EXCL.open("a", encoding="utf-8") as f:
        for a in NEW_EXCL:
            if a["id"] not in have:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
    excl = have | {a["id"] for a in NEW_EXCL}

    # 2) 残句修复（ja/zh 两侧 zh 文本；对话副本随后由同步脚本处理）
    fixes = []
    for f in sorted(C.glob("*.zh.jsonl")):
        recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        changed = 0
        for r in recs:
            new = fix_dangling(r["text"])
            if new != r["text"]:
                fixes.append((r["id"], r["text"], new))
                r["text"] = new
                changed += 1
        if changed:
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        print(f"{f.name}: 残句修复 {changed}")
    print(f"残句修复合计 {len(fixes)} 条")

    # 3) 通用桶抽取
    pool = []
    for f in sorted(C.glob("*.zh.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r["id"] in excl:
                continue
            if route(r["text"]) == "通用":
                pool.append({"id": r["id"], "text": r["text"]})
    batches = [pool[i:i + 30] for i in range(0, len(pool), 30)]
    seeds = {f"realign_{i+1:02d}": {"lines": b} for i, b in enumerate(batches)}
    (OUT / "realign_seeds.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"通用桶 {len(pool)} 条 -> {len(batches)} 批种子 -> realign_seeds.json")
    with (OUT / "realign_fixes.json").open("w", encoding="utf-8") as f:
        json.dump([{"id": i, "old": o, "new": n} for i, o, n in fixes], f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
