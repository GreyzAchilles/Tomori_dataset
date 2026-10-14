# Tomori_dataset

高松灯（《BanG Dream! It's MyGO!!!!!》，MyGO!!!!! 主唱）中文人格微调（SFT）数据集，
含清洗后的台词语料与三个可直接训练的子数据集。基于 Qwen3.5-0.8B / MiniCPM-1B 等
中文基座模型的人格化训练目标构建。

## 数据规模

| 子集 | 格式 | train / val | 说明 |
| --- | --- | --- | --- |
| `sft/style` | Alpaca | 997 / 52 | 真实台词（三源 1054 条清洗后）+ 情境模板 instruction |
| `sft/identity` | Alpaca | 158 / 8 | 76 事实 × 多问法（2-4 种）人格知识 QA，答案灯第一人称 |
| `sft/dialogue` | ShareGPT | 460 / 24 | 多轮对话：语料锚定生成（D1/D2）+ 出戏防御（D3）+ 自我认知多轮（D4） |

- System 策略：各子集整体 20% 携带人格卡、80% 裸样本（人格进权重）；
  identity 的 self 组与 dialogue 的 D3/D4 100% 裸（防御必须无 system 可用）。
- 划分：各子集独立 95:5，seed=42。
- 台词特征校准：词内结巴率 style 7.4% / identity 9.5% / dialogue 6.4%（目标区间 5-10%）。

## 目录结构

```
sft/            三个可直接训练的数据集（LLaMA-Factory 格式）
corpus/cleaned/ 三源台词语料（ja / zh 双语 jsonl，schema: id/source/type/speaker/text/start/end）
corpus/wiki/    角色经历与档案整理（来源：萌娘百科，经 Fandom 交叉核对）
corpus/music/   演唱曲目目录（MyGO!!!!! 35 首 + CRYCHIC 3 条）
corpus/exclusions.jsonl  清洗剔除清单（88 条，下游按 id 过滤）
scripts/        全套构建管线（转写→清洗→翻译→构造），按文件名可读出流程
docs/           清洗报告与三个子集的构造报告
```

## 语料来源与致谢

- TV 动画台词：B 站 [BV1JAcLz8ErB](https://www.bilibili.com/video/BV1JAcLz8ErB/)（up 主自剪干声，去 BGM 降噪）
- Ave Mujica 动画台词：B 站 [BV1JFZjYcEf2](https://www.bilibili.com/video/BV1JFZjYcEf2/)
- 手游语音：《BanG Dream! 少女乐团派对》高松灯干声（本地素材转写）
- 角色资料：萌娘百科「高松灯」等条目；经 Wikipedia / Fandom Bandori Wiki 交叉核对

音频/视频等原始媒体**不在本仓库再分发**，请通过上述来源获取。

## 构建管线（摘要）

1. faster-whisper（medium, int8）日语转写 → 话语级 jsonl
2. 清洗复审：专名/人名/物种名修复（107 条）、语气词与跨源重复剔除（88 条）
3. hy-mt2-pro 机翻（人名表约束 + 碎片照译）
4. 子集构造：情境模板池（style）/ 问法增广（identity）/ 语料锚定 + 质量门批量生成 + 手写防御集（dialogue）
5. 详见 `docs/` 各报告

## 用途声明

本仓库内容为对既有作品台词的转写、翻译与整理，仅用于个人研究与学习目的，
相关权利归原作者及出版方所有。请勿用于商业用途。
