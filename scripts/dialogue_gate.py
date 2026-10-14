#!/usr/bin/env python3
"""对话批次质量门（阶段 C 试点）

用法：python dialogue_gate.py <batch.jsonl> <rounds_spec> <quota>
  rounds_spec ∈ {"2-4","4-6"}：允许的对话轮数区间（human/gpt 一来一回 = 2 轮）
校验规则：
  G1 schema：每行一个 JSON 对象，conversations 数组，from ∈ {human,gpt}
  G2 交替：严格 human/gpt 交替，首 human 尾 gpt
  G3 轮数：在 rounds_spec 区间内
  G4 逐字锚定：每个 gpt value 必须与语料库（三源 − exclusions）中的台词文本完全一致
  G5 lint：任何 value 不得命中禁词（AI/扮演/系统提示等出戏内容）；human 非空且 ≤120 字
  G6 数量：≥ quota-2（允许少量缺口，汇总阶段统一核准）
退出码 0 = 通过；1 = 不通过（stdout 输出逐行错误报告）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"
EXCL = ROOT / "99_logs" / "cleaning_20261013" / "exclusions.jsonl"
FORBIDDEN = ["作为AI", "作为人工智能", "语言模型", "AI助手", "扮演", "系统提示", "SYSTEM", "prompt", "角色扮演"]


def load_valid_texts():
    excl = {json.loads(l)["id"] for l in EXCL.read_text(encoding="utf-8").splitlines() if l.strip()}
    texts = set()
    for f in C.glob("*.zh.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] not in excl:
                texts.add(r["text"].strip())
    return texts


def main():
    batch_path, spec, quota = sys.argv[1], sys.argv[2], int(sys.argv[3])
    lo, hi = (int(x) for x in spec.split("-"))
    valid = load_valid_texts()
    errors = []
    n_ok = 0
    lines = [l for l in Path(batch_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    for i, line in enumerate(lines, 1):
        tag = f"L{i}"
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"{tag}: JSON 解析失败 {e}")
            continue
        conv = rec.get("conversations")
        if not isinstance(conv, list) or not conv:
            errors.append(f"{tag}: conversations 缺失或为空")
            continue
        bad = []
        if conv[0]["from"] != "human" or conv[-1]["from"] != "gpt":
            bad.append(f"首尾应为 human/gpt，实际 {conv[0]['from']}/{conv[-1]['from']}")
        for j, t in enumerate(conv):
            if t.get("from") not in ("human", "gpt"):
                bad.append(f"第{j}轮 from 非法: {t.get('from')}")
            v = (t.get("value") or "").strip()
            if not v:
                bad.append(f"第{j}轮 value 为空")
            for pat in FORBIDDEN:
                if pat.lower() in v.lower():
                    bad.append(f"第{j}轮命中禁词「{pat}」")
            if t.get("from") == "human" and len(v) > 120:
                bad.append(f"第{j}轮 human 过长({len(v)}字)")
            if t.get("from") == "gpt" and v not in valid:
                bad.append(f"第{j}轮 gpt 非语料原文: {v[:30]}…")
        for j in range(1, len(conv)):
            if conv[j]["from"] == conv[j - 1]["from"]:
                bad.append(f"第{j}轮与上一轮角色相同")
        n = len(conv)
        if not (lo <= n <= hi) or n % 2 != 0:
            bad.append(f"轮数{n}不在{spec}区间或非偶数")
        if bad:
            errors.append(f"{tag}: " + "；".join(bad))
        else:
            n_ok += 1
    if n_ok < quota - 2:
        errors.append(f"总量不足: 有效{n_ok} < 配额{quota}-2")
    if errors:
        print(f"FAIL {batch_path}（有效 {n_ok}/{len(lines)}）")
        for e in errors[:40]:
            print("  " + e)
        sys.exit(1)
    print(f"PASS {batch_path}: {n_ok} 条全部通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
