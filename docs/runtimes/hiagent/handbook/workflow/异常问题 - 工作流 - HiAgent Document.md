---
title: "异常问题 - 工作流"
summary: "工作流异常问题排查指南"
tags: ["HiAgent", "workflow", "troubleshooting"]
type: documentation
source: HiAgent 官方文档
updated: 2026-04-06
---

⼯作流 - HiAgent Document
⽂档中⼼
⼯作流

⼯作流中调⽤知识库时未返回内容

问题描述 ⼯作流中调⽤知识库时，知识库未返回任何内容，如下图所示：

hiagent.deyunai.com:32300/platform/doc/faq/abnormal-issue/workﬂow

1/3

2026/1/30 22:34

⼯作流 - HiAgent Document

问题分析 查看知识库的相关设置，发现相似度设置过⾼。推测是因为知识库未能检索到满⾜相似度要求的内容，需要适当降低相似度设置

值。调低相似度设置后，能够正常返回相关内容。 解决⽅案 适当调低相似度设置值。

上⼀⻚

hiagent.deyunai.com:32300/platform/doc/faq/abnormal-issue/workﬂow

下⼀⻚

2/3

识图提问2026/1/30 22:34

智能体

⼯作流 - HiAgent Document

知识库

hiagent.deyunai.com:32300/platform/doc/faq/abnormal-issue/workﬂow

3/3

