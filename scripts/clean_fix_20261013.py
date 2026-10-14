#!/usr/bin/env python3
"""2026-10-13 清洗复审：确定性专名/物种名修复（一次性，留审计痕迹）

对三个语料源的 .ja.jsonl 与 .zh.jsonl 按条目 id 做定点文本替换：
- zh 修 text 字段（含 text_ja 时同步修 ja 侧）
- ja 修 text 字段
每处替换断言旧串存在，防止 id 漂移后静默失配。
修复清单与依据见 99_logs/cleaning_20261013/report.md。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "20_corpus_cleaned"

# (文件基名, id, zh_old, zh_new, ja_old, ja_new)  ja 侧为 None 表示不改
FIXES = [
    # --- TV 源（fanmade BV1JAcLz8ErB）---
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0004",
     "我是地阪灯", "我是高松灯",
     "じはやさん、とこまつともりです、よろしく", "たかまつともりです、よろしく"),  # 乱码前缀截除
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0007",
     "胡须企鹅", "帽带企鹅", None, None),  # ヒゲペンギン=chinstrap
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0008",
     "全通企鹅", "洪堡企鹅", "全通ペンギン", "フンボルトペンギン"),  # ASR 误听
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0015",
     "帽带企鹅和麦哲伦企鹅", "开普企鹅和长冠企鹅", "ケーブペンギン", "ケープペンギン"),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0016",
     "帝企鹅", "王企鹅", None, None),  # キングペンギン=王企鹅，非帝企鹅
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0039",
     "胡须企鹅", "帽带企鹅", None, None),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0183",
     "睦美姐", "睦酱", None, None),
    # --- 游戏源（garupa 干声）---
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0132",
     "小泷", "立希酱", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0145",
     "小泷", "立希酱", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0149",
     "小泷", "立希酱", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0676",
     "睦美酱、纱代酱", "睦酱、素世酱", None, None),
    # --- Ave Mujica 动画源（BV1JFZjYcEf2）---
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0008",
     "Abemagic？", "Ave Mujica……？", None, None),  # アベマジカ=Ave Mujica 谐音
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0012",
     "睦美酱", "睦酱", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0014",
     "丰川组", "丰川集团", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0019",
     "睦美酱说，睦美酱想见你。", "睦酱说，睦酱想见你。", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0020",
     "睦美酱，Crychic已经解散了。", "睦酱，CRYCHIC已经解散了。", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0023",
     "睦美酱", "睦酱", None, None),
    # --- 第二轮：复扫追加（游戏源企鹅系列 + 残余大小写）---
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0296",
     "长胡子的企鹅", "帽带企鹅", "ひげペンギン", "ヒゲペンギン"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0298",
     "金图企鹅", "巴布亚企鹅", None, None),  # ジェンツー=Gentoo
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0299",
     "企鹅系列的伴奏功还有其他种类", "企鹅系列的创可贴还有其他种类",
     "伴奏功", "絆創膏"),  # ばんそうこう 同音误转写
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0304",
     "还有冠企鹅、通心粉企鹅和帝企鹅的哦", "还有开普企鹅、长冠企鹅和王企鹅的哦",
     "ケーブペンギン", "ケープペンギン"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0326",
     "阿南酱，这个，长胡子的企鹅。", "爱音酱，这个，帽带企鹅。",
     "あなんち、これ、ヒゲペンギン", "アノンちゃん、これ、ヒゲペンギン"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0328",
     "长胡子企鹅", "帽带企鹅", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0474",
     "冠企鹅……", "开普企鹅……", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0028",
     "关于Crychic的事。", "关于CRYCHIC的事。", None, None),
    # --- 第三轮：伴奏功（ばんそうこう=絆創膏）散落条目 ---
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0293",
     "伴奏功", "创可贴", "伴奏功", "絆創膏"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0294",
     "我在收集伴奏功", "我在收集创可贴", "私、伴奏功を集めてて", "私、絆創膏を集めてて"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0707",
     "伴奏功。", "创可贴。", "伴奏功。", "絆創膏。"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0709",
     "要是能配上伴奏功就好了。", "要是能贴上创可贴就好了。",
     "伴奏功、張れたらいいのに。", "絆創膏、張れたらいいのに。"),
    # --- 第四轮：剩余 2 处（0154 的 すあちゃん→小须亚 待用户确认，暂保留）---
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0154",
     "伴奏伤", "创可贴", "指に伴奏功", "指に絆創膏"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0156",
     "伴奏伤有很多种的，要是受伤了要告诉我哦。", "创可贴我有很多的，要是受伤了要告诉我哦。",
     "伴奏功、いっぱいあるから", "絆創膏、いっぱいあるから"),
    # --- 第五轮：塔基/小夜（そや）人名乱译 ---
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0099",
     "塔基酱", "立希酱", None, None),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0108",
     "塔基酱", "立希酱", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0683",
     "小夜酱", "素世酱", "そやちゃん", "そよちゃん"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0687",
     "小夜酱，对不起。", "素世酱，对不起。", "そやちゃん、ごめん。", "そよちゃん、ごめん。"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0690",
     "小夜酱", "素世酱", "そやちゃん", "そよちゃん"),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0702",
     "小夜酱", "素世酱", "そやちゃん", "そよちゃん"),
    # --- 第七轮：②特征重审——日文原文结巴证据恢复 + 新发现人名错误 ---
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0004",
     "啊，谢谢。", "啊……谢谢。", None, None),  # あ、ありがとう
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0079",
     "哦，辛苦了。", "辛、辛苦了。", None, None),  # お、お疲れ様
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0089",
     "哦，拜托你了。", "拜、拜托你了。", None, None),  # お、お願いします
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0710",
     "啊，那时我太入神了，居然那样。", "那、那个时候我太入神了，居然那样。", None, None),  # あ、あの時は
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0692",
     "又是去灯酱家吗？", "又是去立希酱家吗？", None, None),  # たきちゃん=立希，误作灯酱（R3 剔除条目，源文件卫生修复）
    # --- 第八轮：②特征校准——结巴率 1.4% → 5-10%（用户裁定），词首结巴落在紧张/告白/道歉/悲伤语境 ---
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0561", "让我来演奏吧……", "让、让我来演奏吧……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0567", "为什么会这样……", "为、为什么会这样……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0382", "和大家在一起时的感受……", "和、和大家在一起时的感受……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0371", "祥子酱，声音太大了……", "祥、祥子酱，声音太大了……", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0021", "这次一定要好好地……", "这、这次一定要好好地……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0497", "就算继续前进……", "就、就算继续前进……", None, None),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0057", "但是，没有祥子酱的话……", "但、但是，没有祥子酱的话……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0582", "我早就讨厌了……", "我、我早就讨厌了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0510", "所以只有歌词……", "所、所以只有歌词……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0605", "我觉得不是因为风……", "我、我觉得不是因为风……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0417", "我竟然这么想了……", "我、我竟然这么想了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0425", "我没有珍贵的东西……", "我、我没有珍贵的东西……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0479", "没能传达出去……", "没、没能传达出去……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0488", "我实在不擅长……", "我、我实在不擅长……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0592", "只能拼命努力了……", "只、只能拼命努力了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0416", "要是能把眼泪收集起来留着就好了……", "要、要是能把眼泪收集起来留着就好了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0598", "有你们在的话……", "有、有你们在的话……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0447", "一辈子一起做吧……", "一、一辈子一起做吧……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0580", "我不想再经历这种事了……", "我、我不想再经历这种事了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0514", "我们一起去录音室吧……", "我、我们一起去录音室吧……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0369", "可是，我完全唱不出来……", "可、可是，我完全唱不出来……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0400", "是我把CRYCHIC搞砸了……", "是、是我把CRYCHIC搞砸了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0458", "多亏了爱音酱……", "多、多亏了爱音酱……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0373", "在录音室里，我会很紧张……", "在、在录音室里，我会很紧张……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0459", "我们才能再次组建乐队……", "我、我们才能再次组建乐队……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0377", "入口处的那个东西好厉害……", "入口处的那个东西好、好厉害……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0361", "那是，那个，歌词…", "那是，那、那个，歌词…", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0403", "我不知道该用什么样的脸去见大家……", "我、我不知道该用什么样的脸去见大家……", None, None),
    ("anime_tomori_quotes_bv1jfzjycef2", "anime_bv1jfzjycef2_0011", "但是，这首歌却……", "但、但是，这首歌却……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0502", "我们一起加油吧……", "我、我们一起加油吧……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0627", "说要一辈子做下去……", "说要一、一辈子做下去……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0535", "到底去哪儿了呢……", "到、到底去哪儿了呢……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0422", "我缺少了什么吗……", "我、我缺少了什么吗……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0418", "只有我哭不出来……", "只、只有我哭不出来……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0638", "真不该那么做的……", "真、真不该那么做的……", None, None),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0087", "可是，即便如此……", "可、可是，即便如此……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0383", "我试着写下来了……", "我、我试着写下来了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0426", "我想要能让我流泪的珍贵之物……", "我、我想要能让我流泪的珍贵之物……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0579", "不想再有这种经历了……", "不、不想再有这种经历了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0402", "我就没法去练习了……", "我、我就没法去练习了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0472", "因为她说喜欢企鹅……", "因、因为她说喜欢企鹅……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0623", "要一辈子组乐队……", "要、要一辈子组乐队……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0641", "变得看不清了……", "变得看、看不清了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0622", "和素世酱一起……", "和、和素世酱一起……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0398", "因为我的歌声不好……", "因、因为我的歌声不好……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0457", "我没想到还能回来……", "我、我没想到还能回来……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0399", "祥子酱也一定……", "祥、祥子酱也一定……", None, None),
    ("fanmade_tomori_quotes_bv1jaclz8erb", "fanmade_bv1jaclz8erb_0002", "可是，没有祥子酱的话……", "可、可是，没有祥子酱的话……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0713", "嗯……我不记得了。", "嗯……我、我不记得了。", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0507", "是她拜托我的……", "是、是她拜托我的……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0637", "我讨厌难受的感觉……", "我、我讨厌难受的感觉……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0406", "但我一次也没能回复……", "但、但我一次也没能回复……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0577", "好痛苦好痛苦……", "好痛苦、好痛苦……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0624", "因为那样约定过……", "因、因为那样约定过……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0588", "就算还是迷路的状态也想继续前进……", "就、就算还是迷路的状态也想继续前进……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0554", "我也会加油的……", "我、我也会加油的……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0412", "毕业好难过啊……", "毕、毕业好难过啊……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0409", "初中也到了最后一天……", "初、初中也到了最后一天……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0634", "我并不想待在这里……", "我、我并不想待在这里……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0560", "要让她听到哦……", "要、要让她听到哦……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0648", "没能成为真正的人……", "没、没能成为真正的人……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0607", "可能不会来了……", "可、可能不会来了……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0608", "因为我伤害了她……", "因、因为我伤害了她……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0451", "直到首次演出为止……", "直、直到首次演出为止……", None, None),
    ("game_tomori_garupa_dryvoice", "game_tomori_dryvoice_0405", "虽然收到了很多消息……", "虽、虽然收到了很多消息……", None, None),
]

# 全局替换（跨文件扫荡性修复，第 6 轮）：泷=たき/滝ちゃん 乱译；春日陰→春日影
GLOBAL_REPLACES = [
    ("泷酱", "立希酱"),
    ("泷姐", "立希酱"),
    ("春日阴", "春日影"),
    ("春日陰", "春日影"),
    ("滝ちゃん", "たきちゃん"),
]


def main():
    total = 0
    for base, rid, zh_old, zh_new, ja_old, ja_new in FIXES:
        for suffix, fix in ((".zh.jsonl", (zh_old, zh_new)), (".ja.jsonl", (ja_old, ja_new))):
            if not fix or fix[0] is None:
                continue
            path = C / (base + suffix)
            recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            rec = next((r for r in recs if r["id"] == rid), None)
            assert rec is not None, f"{rid} not in {path.name}"
            target = "text_ja" if suffix == ".zh.jsonl" and rec.get("text_ja") else "text"
            if suffix == ".zh.jsonl":
                if zh_old not in rec["text"]:
                    if zh_new in rec["text"]:
                        continue  # 已修过，幂等跳过
                    raise AssertionError(f"zh mismatch {rid}: {rec['text']!r}")
                rec["text"] = rec["text"].replace(zh_old, zh_new)
                if ja_old and rec.get("text_ja"):
                    if ja_old not in rec["text_ja"]:
                        if ja_new in rec["text_ja"]:
                            continue
                        raise AssertionError(f"ja mismatch {rid}: {rec['text_ja']!r}")
                    rec["text_ja"] = rec["text_ja"].replace(ja_old, ja_new)
                path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
            else:
                if ja_old not in rec["text"]:
                    if ja_new in rec["text"]:
                        continue  # 已修过，幂等跳过
                    raise AssertionError(f"ja-file mismatch {rid}: {rec['text']!r}")
                rec["text"] = rec["text"].replace(ja_old, ja_new)
                path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
            total += 1
    # 第 6 轮：全局替换（ja/zh 两侧均扫）
    g_total = 0
    for f in sorted(C.glob("*.zh.jsonl")) + sorted(C.glob("*.ja.jsonl")):
        text = f.read_text(encoding="utf-8")
        new = text
        for old, repl in GLOBAL_REPLACES:
            g_total += new.count(old)
            new = new.replace(old, repl)
        if new != text:
            f.write_text(new, encoding="utf-8")
    print(f"applied {total} file-level fixes across {len(FIXES)} entries; global replaces hit {g_total}")


if __name__ == "__main__":
    main()
