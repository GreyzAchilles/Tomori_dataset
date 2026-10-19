#!/usr/bin/env python3
"""阶段 A：style 数据集构造（spec §1.1 Alpaca / §2 system 80:20 / §4 划分 95:5）

输入：20_corpus_cleaned/ 三个 .zh.jsonl − 99_logs/cleaning_20261013/exclusions.jsonl
流程：情境模板池按内容路由生成 instruction → Alpaca 样本（source=语料 id，text_ja=日文原文）
     → train/val 各自内部分层抽样 20% 携带人格卡（spec 2.1）→ 95:5 划分（seed=42）
输出：30_sft_dataset/style/{train,val}.jsonl + 构造报告（99_logs/style_build_20261013.md）

确定性：instruction 选择用 id 的 md5 哈希（重排序稳定）；划分/抽卡用 random.Random(42)。
"""
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"
OUT = ROOT / "30_sft_dataset" / "style"
EXCL = ROOT / "99_logs" / "cleaning_20261013" / "exclusions.jsonl"

SYSTEM_CARD = (
    "你是高松灯，《BanG Dream! It's MyGO!!!!!》中 MyGO!!!!! 的主唱，羽丘女子学园高一学生。\n"
    "说话方式：句子短、常断续、多用省略号；紧张时重复音节或卡壳；认真起来会突然说得很直白。\n"
    "重要的人：爱音酱（吉他）、立希（鼓手）、素世酱（贝斯）、乐奈酱（吉他）；祥子酱（CRYCHIC 前键盘手）。\n"
    "基调：内向胆怯但真挚，觉得自己\"想要成为人类\"，珍惜想要传达的心情，喜欢企鹅。"
)

FILES = [
    ("fanmade_tomori_quotes_bv1jaclz8erb.zh.jsonl", "TV 动画台词"),
    ("game_tomori_garupa_dryvoice.zh.jsonl", "Garupa 手游干声"),
    ("anime_tomori_quotes_bv1jfzjycef2.zh.jsonl", "Ave Mujica 动画台词"),
]

# ---------------- 情境模板池 ----------------
# 每类 = (触发正则列表, 模板列表)；路由自上而下，首个命中生效；兜底"通用"不设触发。
# 模板为用户侧话语/情境描述，力求与 output 语义兼容。
ROUTES = [
    ("自我介绍", [r"高松灯|请多关照"], [
        "初次见面，能介绍一下自己吗？",
        "你好呀，还不知道你的名字呢。",
        "新学期第一堂课，轮到你自我介绍了。",
        "我们好像没正式认识过——你叫什么名字？",
    ]),
    ("企鹅", [r"企鹅"], [
        "灯，听说你喜欢企鹅？",
        "灯，你在看的书是……企鹅图鉴吗？",
        "水族馆新来了一群企鹅，灯要去看吗？",
        "灯，能讲讲企鹅的事吗？",
        "（翻开灯的笔记本，里面贴满了企鹅贴纸）……灯？",
    ]),
    ("创可贴", [r"创可贴"], [
        "灯，你手上怎么贴着创可贴？",
        "（灯递过来一盒创可贴）这是……给我的？",
        "灯，你包里怎么总有这么多创可贴？",
        "我擦伤了手指……灯，有办法吗？",
    ]),
    ("歌词本", [r"歌词|笔记本|作词|写词|写诗|念诗"], [
        "灯，你的笔记本里都写了什么？",
        "灯，写词的时候都在想些什么？",
        "灯，能让我看看你写的歌词吗？",
        "新歌的词……写出来了吗？",
        "灯，为什么总把心里话写下来，而不是说出来呢？",
        "怎么才能写出真正传达心情的歌词呢？",
    ]),
    ("金平糖", [r"金平糖|糖果|零食"], [
        "灯，平时喜欢吃什么零食？",
        "（倒出一小把金平糖）要吃吗？",
        "灯，为什么喜欢金平糖呀？",
    ]),
    ("天文", [r"天文|星星|星空|观星|望远镜|宇宙"], [
        "灯，晚上一般都在做什么？",
        "今晚好像能看到很多星星，灯要一起看吗？",
        "灯，为什么加入天文部呀？",
        "灯，给我讲讲星星的事吧。",
    ]),
    ("水族馆", [r"水族馆|鱼|海豚"], [
        "周末去哪玩好呢……灯有推荐吗？",
        "灯，上次去水族馆开心吗？",
        "灯想去水族馆还是游乐园？",
    ]),
    ("迷路迷茫", [r"迷路|迷茫|迷子|答案|活着的意义|人生"], [
        "灯，如果迷路了该怎么办？",
        "努力真的有意义吗……灯怎么看？",
        "灯，你找到自己的答案了吗？",
        "前途一片迷茫的时候，灯会怎么做？",
        "灯，会害怕明天吗？",
    ]),
    ("CRYCHIC往事", [r"CRYCHIC|解散|祥子"], [
        "灯，CRYCHIC 是一支怎样的乐队？",
        "灯，还记得 CRYCHIC 的事吗？",
        "以前的乐队……发生了什么？",
        "灯，祥子酱是个怎样的人？",
        "（提起往事）灯，还恨她吗？",
        "听说你以前也组过乐队——能讲讲吗？",
    ]),
    ("乐队日常", [r"乐队|MyGO|组乐队|新曲|演奏|练习|排练"], [
        "灯，为什么想组乐队？",
        "灯，新曲写得怎么样了？",
        "排练马上要开始了，灯准备好了吗？",
        "灯，在乐队里开心吗？",
        "如果有一天乐队走不下去了，灯会怎么办？",
        "灯，你觉得 MyGO!!!!! 是怎样的乐队？",
        "下一个目标是什么，灯？",
    ]),
    ("Live舞台", [r"[Ll]ive|演出|舞台|上台|唱歌|观众|台"], [
        "还有十分钟就要上台了，灯，现在什么心情？",
        "灯，站上舞台的瞬间在想什么？",
        "台下好多人……灯不紧张吗？",
        "灯，唱歌的时候是什么感觉？",
        "演出结束后，灯想做什么？",
    ]),
    ("伙伴-爱音", [r"爱音"], [
        "灯，爱音酱是个怎样的人？",
        "你和爱音酱是怎么成为朋友的？",
        "灯，最近和爱音酱处得怎么样？",
        "（爱音又在叽叽喳喳讲留学的事）灯，你听着是什么感觉？",
    ]),
    ("伙伴-立希", [r"立希"], [
        "灯，立希酱平时怎么照顾你的？",
        "灯和立希酱是怎么认识的？",
        "立希酱好像总在护着你呢，灯知道吗？",
    ]),
    ("伙伴-素世", [r"素世"], [
        "灯，素世酱是个怎样的人？",
        "素世酱找过你聊心事吗？",
        "灯，最近和素世酱聊了什么？",
    ]),
    ("伙伴-乐奈", [r"乐奈"], [
        "灯，乐奈酱是个怎样的人？",
        "乐奈酱又乱跑进练习室了吧？",
        "灯，乐奈酱说的话你能听懂吗？",
    ]),
    ("伙伴-睦", [r"睦"], [
        "灯，睦酱最近怎么样？",
        "灯，睦酱对你说过什么？",
        "（提起睦酱）灯，你担心她吗？",
    ]),
    ("感谢", [r"谢谢|感谢|多谢"], [
        "（把热可可放在灯手边）给你。",
        "灯，这个小礼物送你。",
        "今天多亏了你，灯。",
        "灯，生日快乐。这是大家凑钱买的。",
    ]),
    ("道歉", [r"对不起|抱歉|不好意思"], [
        "（灯突然停下来低下头）……怎么了？",
        "灯，你刚才脸色不太好，没事吧？",
        "其实……我也有做得不对的地方。",
        "灯，是有什么放心不下的事吗？",
    ]),
    ("加油", [r"加油|努力|頑張|尽力"], [
        "明天就是正式演出了。",
        "灯，大家都在看着你呢。",
        "（把手搭在灯肩上）放轻松，可以的。",
        "灯，这次一定要成功啊。",
    ]),
    ("告别", [r"拜拜|再见|晚安|明天见|先走"], [
        "灯，那我先走了。",
        "天色不早了，今天到这里吧。",
        "灯，明天见。",
        "要好好休息哦，灯。",
    ]),
    ("受伤", [r"摔倒|受伤|疼|擦伤|绊倒"], [
        "灯，没事吧？！",
        "（灯踉跄了一下）小心！",
        "刚才摔的那一下要不要紧？",
    ]),
    ("决意回应", [r"^嗯|^好|^做吧|^在呢|^对|^是|^好呀|^我知道"], [
        "灯，练习室到了，进去吗？",
        "灯，在听我说话吗？",
        "那这件事就拜托灯了，可以吗？",
        "灯，决定好了吗？",
        "（轻声）灯？",
    ]),
    ("疑问回应", [r"[？?]$"], [
        "我已经决定退出了。",
        "其实，我一直在骗你。",
        "你不觉得，有些事从一开始就是错的吗？",
        "我把你珍藏的东西弄坏了。",
        "明天开始，我就不来了。",
        "人为什么一定要合群呢？",
    ]),
]

GENERIC = [
    "灯，你现在在想什么？",
    "灯，刚才小声嘀咕了什么？",
    "（灯盯着窗外发呆）……灯？在想事情吗？",
    "灯，今天有什么想说的吗？",
    "（递给灯一支笔）随便写点什么吧。",
    "灯，说说现在的心情？",
    "（和灯并肩坐着，沉默了一会儿）……灯，在听吗？",
    "灯，你嘴边好像有话想说。",
    "灯，今天的日记会写什么？",
    "（轻声）灯，能说说心里话吗？",
    "灯，现在脑子里在想什么？",
    "灯，无聊的话随便聊点什么吧。",
    "灯，最近睡得好吗？",
    "灯，今天过得怎么样？",
    "灯，你看起来有心事。",
    "灯，一个人待着的时候都在做什么？",
    "灯，刚才那个瞬间，你在想什么？",
    "灯，如果我走了，你会寂寞吗？",
    "灯，觉得现在的自己怎么样？",
    "灯，喜欢现在的生活吗？",
    "灯，说点什么吧，什么都行。",
    "（灯安静地整理着书包）……等一下一起走吗？",
    "灯，昨天的梦见了什么？",
    "灯，今天的风好大啊。",
    "灯，累了吗？",
    "灯，喜欢这里吗？",
    "灯，时间过得好快啊……你不觉得吗？",
    "灯，在害怕的时候会想什么？",
    "灯，开心的时候会做什么？",
    "灯，难过的时候呢？",
    "灯，对你来说，什么是重要的？",
    "灯，你相信「一辈子」吗？",
    "灯，朋友对你来说是什么？",
    "灯，音乐对你来说是什么？",
    "灯，如果声音能传达到就好了，对吧？",
    "灯，今天也辛苦了。",
    "灯，明天会更好吗？",
    "（把刚买的饮料递过去）灯，渴了吧？",
    "灯，刚才大家在聊未来的事，你怎么想？",
    "灯，如果给你一天假期，你想做什么？",
    "灯，你觉得自己变了吗？",
    "灯，还记得我们第一次见面吗？",
    "灯，最近有什么开心的事吗？",
    "灯，有什么想问我的吗？",
    "灯，这道题你会吗？教教我。",
    "灯，走廊那边好像很吵，去看看？",
    "灯，放学后有空吗？",
    "灯，你带着的这个小瓶子……里面是什么？",
    "灯，下雨了，带伞了吗？",
    "灯，一起回家吗？",
]

def pick(pool, seed_key):
    h = int(hashlib.md5(seed_key.encode()).hexdigest(), 16)
    return pool[h % len(pool)]


# 重对齐覆盖（2026-10-14：通用桶 instruction 语义对齐，Flash 工作流产出）
REALIGN = {}
_realign_path = ROOT / "99_logs" / "dialogue_work" / "realign.json"
if _realign_path.exists():
    REALIGN = {r["id"]: r["instruction"] for r in
               (json.loads(l) for l in _realign_path.read_text(encoding="utf-8").splitlines() if l.strip())}


def route(text):
    for name, pats, _ in ROUTES:
        if any(re.search(p, text) for p in pats):
            return name
    return "通用"


def main():
    excl = {json.loads(l)["id"] for l in EXCL.read_text(encoding="utf-8").splitlines() if l.strip()}
    samples = []
    cat_cnt = Counter()
    for fname, label in FILES:
        for line in (C / fname).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] in excl:
                continue
            cat = route(r["text"])
            cat_cnt[cat] += 1
            pool = next((t for n, _, t in ROUTES if n == cat), GENERIC)
            instruction = REALIGN.get(r["id"]) or pick(pool, r["id"])
            samples.append({
                "instruction": instruction,
                "input": "",
                "output": r["text"],
                "source": r["id"],
                "text_ja": r.get("text_ja"),
                "_cat": cat,
                "_src": label,
            })

    rng = random.Random(42)
    rng.shuffle(samples)
    n_val = max(1, round(len(samples) * 0.05))
    val, train = samples[:n_val], samples[n_val:]

    def stamp(subset):
        k = max(1, round(len(subset) * 0.2))
        for s in subset[:k]:
            s["system"] = SYSTEM_CARD

    stamp(train)
    stamp(val)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, subset in (("train", train), ("val", val)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for s in subset:
                rec = {k: v for k, v in s.items() if not k.startswith("_")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 构造报告
    stat = {
        "总量": len(samples),
        "train": len(train),
        "val": len(val),
        "system卡": sum("system" in s for s in samples),
        "裸样本": sum("system" not in s for s in samples),
    }
    lines = [
        "# style 数据集构造报告（2026-10-13，阶段 A）",
        "",
        f"- 输入：三源 zh 语料 − exclusions（{len(excl)} 条）= **{len(samples)} 条**",
        f"- 划分：train {len(train)} / val {len(val)}（95:5，seed=42）",
        f"- system：{stat['system卡']} 条带人格卡 / {stat['裸样本']} 条裸样本"
        f"（train 内 {sum('system' in s for s in train)}/{len(train)}，"
        f"val 内 {sum('system' in s for s in val)}/{len(val)}，分层 20%）",
        f"- instruction：{sum(len(t) for _, _, t in ROUTES)} 个路由模板 + {len(GENERIC)} 个通用模板"
        + (f"；其中 {len(REALIGN)} 条通用桶 instruction 已由重对齐覆盖（语义对齐，2026-10-14）" if REALIGN else ""),
        "",
        "## 情境路由分布",
        "",
        "| 类别 | 条数 |", "| --- | --- |",
    ]
    for name, n in cat_cnt.most_common():
        lines.append(f"| {name} | {n} |")
    lines += ["", "样本结构：`instruction / input(\"\") / output / source(=语料id) / text_ja`，",
              "20% 样本附 `system` 人格卡（spec 2.1 原文）。LLaMA-Factory 注册（阶段 D 统一做）：",
              '`"tomori_style": {"file_name": "style/train.jsonl", "formatting": "alpaca"}`（val 同）']
    (ROOT / "99_logs" / "style_build_20261013.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(stat, ensure_ascii=False))
    print("类别分布:", dict(cat_cnt.most_common()))
    print(f"输出: {OUT / 'train.jsonl'}, {OUT / 'val.jsonl'}")


if __name__ == "__main__":
    main()
