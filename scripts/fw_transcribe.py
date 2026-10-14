#!/usr/bin/env python3
"""faster-whisper 转写 -> SRT（TomoriPersona 项目通用）

openai-whisper 在纯 CPU 上过慢（606s 音频 30min 未完成），改用 faster-whisper
（同权重 int8 量化，CPU 速度约 4x）。输出与 whisper CLI 相同格式的 SRT，
供 90_scripts/srt_to_jsonl.py 消费。

用法：
  python fw_transcribe.py <audio> <outdir> [model]
"""
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    audio, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    model_name = sys.argv[3] if len(sys.argv) > 3 else "medium"
    outdir.mkdir(parents=True, exist_ok=True)

    # model_name 可传 HF repo id、本地模型目录（如 .models/fw-medium）
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio),
        language="ja",  # MyGO TV 动画原声为日语，勿改回 zh
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    print(f"lang={info.language} p={info.language_probability:.2f} dur={info.duration:.1f}s", flush=True)

    srt_path = outdir / (audio.stem + ".srt")
    with srt_path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            print(f"[{i}] {seg.start:.2f}-{seg.end:.2f}: {seg.text}", flush=True)
            f.write(f"{i}\n{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}\n{seg.text.strip()}\n\n")
    print(f"written: {srt_path}", flush=True)


if __name__ == "__main__":
    main()
