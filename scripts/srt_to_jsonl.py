#!/usr/bin/env python3
"""SRT -> jsonl 语料解析器（TomoriPersona 项目通用）

将 Whisper 生成（或 CC）的带时间戳 SRT 解析为项目标准 schema 的 jsonl：
  { id, source, type, speaker, context, text, start, end }

处理逻辑：
1. 解析 SRT 块（序号 / 时间码 / 多行文本）
2. 将连续小段合并为完整句：累积到句末标点（。！？…~）或遇到较长停顿(>gap)即切分；
   单句超长(max_chars)时强制切分
3. 按 text 精确去重（重复台词只保留首次出现），去重报告写入 stderr

用法示例：
  python srt_to_jsonl.py \
    --srt 10_corpus_raw/fanmade/bilibili_BV1JAcLz8ErB_20261007/audio.srt \
    --out 20_corpus_cleaned/fanmade_tomori_quotes_bv1jaclz8erb.jsonl \
    --source "B站 BV1JAcLz8ErB《迷途之子》高松灯台词合集(TV动画干声,Whisper-medium转写)" \
    --id-prefix fanmade_bv1jaclz8erb \
    --speaker "高松灯"
"""
import argparse
import json
import re
import sys
from pathlib import Path

TIMECODE_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
SENT_END = "。！？!?…～~"


def tc_to_sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path):
    """返回 [(start_sec, end_sec, text), ...]，按时间排序"""
    raw = Path(path).read_text(encoding="utf-8-sig")
    entries = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        m = TIMECODE_RE.search(lines[i])
        if not m:
            i += 1
            continue
        start = tc_to_sec(*m.group(1, 2, 3, 4))
        end = tc_to_sec(*m.group(5, 6, 7, 8))
        i += 1
        text_lines = []
        while i < len(lines) and lines[i].strip() and not TIMECODE_RE.search(lines[i]):
            text_lines.append(lines[i].strip())
            i += 1
        text = " ".join(text_lines).strip()
        if text:
            entries.append((start, end, text))
    entries.sort(key=lambda e: e[0])
    return entries


def merge_segments(entries, gap=1.2, max_chars=120):
    """将相邻小段合并为完整句子。

    切分条件（满足其一）：text 以句末标点结尾；与下一段间隔 > gap；合并长度将超 max_chars。
    """
    merged = []
    cur_start, cur_end = None, None
    buf = ""
    for start, end, text in entries:
        if buf and (start - cur_end > gap or len(buf) + len(text) > max_chars):
            merged.append((cur_start, cur_end, buf))
            buf = ""
        if not buf:
            cur_start = start
        else:
            buf += "" if buf.endswith(("，", "。", "、", ",")) else ""
        buf += text
        cur_end = end
        if text.endswith(tuple(SENT_END)):
            merged.append((cur_start, cur_end, buf))
            buf = ""
    if buf:
        merged.append((cur_start, cur_end, buf))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--srt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--id-prefix", required=True)
    ap.add_argument("--speaker", default="高松灯")
    ap.add_argument("--type", default="monologue",
                    help="schema 中的 type 字段（dialogue|monologue|lyrics|profile|worldview）")
    ap.add_argument("--gap", type=float, default=1.2, help="合并句子的最大停顿秒数")
    ap.add_argument("--no-merge", action="store_true",
                    help="不做句子合并：1 个 SRT 段 = 1 条语料（适合日语等无句末标点的转写）")
    ap.add_argument("--keep-dup", action="store_true", help="保留重复台词不去重")
    args = ap.parse_args()

    entries = parse_srt(args.srt)
    merged = entries if args.no_merge else merge_segments(entries, gap=args.gap)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen, n_dup, n_written = set(), 0, 0
    with out.open("w", encoding="utf-8") as f:
        for start, end, text in merged:
            if not args.keep_dup:
                key = re.sub(r"\s", "", text)
                if key in seen:
                    n_dup += 1
                    continue
                seen.add(key)
            rec = {
                "id": f"{args.id_prefix}_{n_written + 1:04d}",
                "source": args.source,
                "type": args.type,
                "speaker": args.speaker,
                "context": None,
                "text": text,
                "start": round(start, 3),
                "end": round(end, 3),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"parsed {len(entries)} srt segs -> {len(merged)} merged -> "
          f"{n_written} written ({n_dup} dups removed) -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
