#!/usr/bin/env python3
"""hy-mt2-pro 直连翻译驱动器（TomoriPersona 项目）

背景：ZCode workflow 运行时无法连通 new-provider/hy-mt2-pro（network_error 死循环，
7分钟0 token），而本机 python 直连该 OpenAI 兼容端点畅通（单发/8并发/流式均实测OK）。
故翻译调度改由本脚本完成：读取批次文件 → 调 hy-mt2-pro 翻译 → 行号覆盖率校验 +
缺行补译（最多3轮）→ 写 results/batch_NN.result.json（供 translate_pipeline.py merge）。

密钥只在进程内从 ZCode provider 配置读取，不打印、不落盘。
"""
import concurrent.futures
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = ROOT / "99_logs" / "translate_work" / "batches"
RESULT_DIR = ROOT / "99_logs" / "translate_work" / "results"
PROVIDER_CFG = Path(r"C:/Users/GreyzAchilles/.zcode/v2/provider_config.json")

PERSONA = (
    "你是日译中翻译引擎，专门翻译《BanG Dream! It's MyGO!!!!!》中高松灯的台词（语音转写文本）。"
    "她胆怯内向、说话断续但真挚，译文需保留这种语气，不要润色改写。"
    "人名固定译法：サキちゃん→祥子酱、アナちゃん→爱音酱、ソヨちゃん→素世酱、ラーナちゃん→乐奈酱、ともり/トモリ→灯、イヤキン→祥子。"
    "专有名词保留原文：CRYCHIC、MyGO!!!!!、Garupa；企鹅等动物名用标准中文名。"
    "逐句对应翻译，不合并、不拆分、不省略；碎片和语气词（如「あ、あ、あ」→「啊、啊、啊」）也照译成中文碎片。"
)


def load_endpoint():
    cfg = json.loads(PROVIDER_CFG.read_text(encoding="utf-8"))
    rule = cfg["config"]["providerConfigRules"]["providerRules"][0]
    return rule["config"]["api"]["baseUrl"], rule["config"]["access"]["apiKey"], \
        rule["config"]["personalModelIds"][0]


def chat(url, key, model, user_msg, max_tokens=4096, timeout=120):
    # baseUrl 可能是 OpenAI 兼容根路径（…/v1）或完整端点（…/chat/completions），统一补全
    if not url.rstrip("/").endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": PERSONA}, {"role": "user", "content": user_msg}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


RE_A = re.compile(r'"i"\s*:\s*(\d+)\s*,\s*"zh"\s*:\s*"((?:[^"\\]|\\.)*)"')
RE_B = re.compile(r'"zh"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"i"\s*:\s*(\d+)')


def parse_translations(raw):
    s = raw.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        s = (s[nl + 1:] if nl >= 0 else "").rstrip().rstrip("`").rstrip()
    out = {}
    try:
        arr = json.loads(s)
        if isinstance(arr, list):
            for d in arr:
                if isinstance(d, dict) and isinstance(d.get("i"), int) \
                        and isinstance(d.get("zh"), str) and d["zh"].strip():
                    out[d["i"]] = d["zh"].strip()
            if out:
                return out
    except (json.JSONDecodeError, ValueError):
        pass
    for i, zh in RE_A.findall(s):
        try:
            zh = json.loads(f'"{zh}"')
        except json.JSONDecodeError:
            pass
        if zh.strip():
            out.setdefault(int(i), zh.strip())
    for zh, i in RE_B.findall(s):
        try:
            zh = json.loads(f'"{zh}"')
        except json.JSONDecodeError:
            pass
        if zh.strip():
            out.setdefault(int(i), zh.strip())
    return out


def translate_batch(path, url, key, model):
    batch_no = int(re.sub(r"\D", "", path.stem))
    items = json.loads(path.read_text(encoding="utf-8"))
    acc = {}
    rounds = 0
    for round_no in range(1, 4):
        todo = [x for x in items if x["i"] not in acc]
        if not todo:
            break
        rounds = round_no
        ask = (
            '请把下面JSON数组中每项的日文"text"翻译成简体中文。\n\n输入：\n'
            + json.dumps(todo, ensure_ascii=False, separators=(",", ":"))
            + f'\n\n输出：只输出一个JSON数组，每项形如 {{"i":行号,"zh":"中文译文"}}，'
              f'必须覆盖输入的全部 {len(todo)} 行，按i升序排列，不要输出任何解释、前缀或代码块标记。'
        )
        for attempt in range(3):
            try:
                raw = chat(url, key, model, ask)
                break
            except Exception as e:  # noqa: BLE001 - 网络层重试
                if attempt == 2:
                    raise
                print(f"  batch{batch_no} 网络重试{attempt + 1}: {type(e).__name__}", flush=True)
                time.sleep(2 * (attempt + 1))
        acc.update(parse_translations(raw))
    done = [{"i": x["i"], "zh": acc[x["i"]]} for x in items if x["i"] in acc]
    RESULT_DIR.joinpath(f"batch_{batch_no:02d}.result.json").write_text(
        json.dumps(done, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    missing = len(items) - len(done)
    return batch_no, len(items), len(done), rounds, missing


def main():
    url, key, model = load_endpoint()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    batches = sorted(BATCH_DIR.glob("batch_*.json"))
    print(f"端点已加载，开始翻译 {len(batches)} 个批次（8并发）", flush=True)
    t0 = time.time()
    total_missing = 0
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(translate_batch, p, url, key, model): p for p in batches}
        for fut in concurrent.futures.as_completed(futs):
            try:
                batch_no, n, done, rounds, missing = fut.result()
                total_missing += missing
                flag = "OK " if missing == 0 else "缺行"
                print(f"  [{flag}] batch{batch_no:02d}: {done}/{n} 行, {rounds} 轮", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"  [失败] {futs[fut].name}: {type(e).__name__}: {str(e)[:100]}", flush=True)
                total_missing += 999
    print(f"完成，总缺行 {total_missing}，耗时 {time.time() - t0:.0f}s", flush=True)
    sys.exit(1 if total_missing else 0)


if __name__ == "__main__":
    main()
