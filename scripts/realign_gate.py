#!/usr/bin/env python3
"""重对齐批次质量门

用法：python realign_gate.py <batch.json> <seeds.json 的批次名>
输入批次文件（每行一个 JSON）：
  {"id":"...","instruction":"..."}  —— 对齐成功
  {"id":"...","reject":"理由"}       —— 无法对齐（乱码/无实义），进入剔除候选
门禁：覆盖种子批全部 id 各一次；instruction 非空且 ≤60 字、不含禁词；reject 必须有理由。
退出码 0 = 通过。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ["作为AI", "人工智能", "语言模型", "AI助手", "扮演", "系统提示", "角色扮演"]


def main():
    batch_path, batch_name = sys.argv[1], sys.argv[2]
    seeds = json.loads((ROOT / "99_logs" / "dialogue_work" / "realign_seeds.json").read_text(encoding="utf-8"))
    want_ids = [l["id"] for l in seeds[batch_name]["lines"]]

    got, errors = {}, []
    for i, line in enumerate(Path(batch_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"L{i}: JSON 解析失败 {e}")
            continue
        rid = rec.get("id")
        if rid not in want_ids:
            errors.append(f"L{i}: id {rid} 不在种子批内")
            continue
        if rid in got:
            errors.append(f"L{i}: id {rid} 重复")
            continue
        if "reject" in rec:
            if not str(rec["reject"]).strip():
                errors.append(f"L{i}: reject 缺理由")
                continue
        else:
            ins = str(rec.get("instruction", "")).strip()
            if not ins:
                errors.append(f"L{i}: instruction 为空")
                continue
            if len(ins) > 60:
                errors.append(f"L{i}: instruction 过长({len(ins)})")
            for p in FORBIDDEN:
                if p in ins:
                    errors.append(f"L{i}: instruction 含禁词「{p}」")
        got[rid] = True
    missing = [i for i in want_ids if i not in got]
    if missing:
        errors.append(f"缺少 {len(missing)} 个 id: {missing[:10]}")
    if errors:
        print(f"FAIL {batch_path}（覆盖 {len(got)}/{len(want_ids)}）")
        for e in errors[:30]:
            print("  " + e)
        sys.exit(1)
    print(f"PASS {batch_path}: {len(got)} 条全覆盖")


if __name__ == "__main__":
    main()
