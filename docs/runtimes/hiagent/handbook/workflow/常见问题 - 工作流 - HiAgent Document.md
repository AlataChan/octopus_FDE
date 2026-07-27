---
title: "常见问题 - 工作流"
summary: "工作流相关常见问题解答"
tags: ["HiAgent", "workflow", "faq"]
type: documentation
source: HiAgent 官方文档
updated: 2026-04-06
---

⼯作流 - HiAgent Document
⽂档中⼼
⼯作流

⼯作流⾥知识库节点的召回⽚段能在智能体展示引⽤和归属么？

智能体会动态检查⼯作流的输出，如果输出是符合知识库 schema 的且智能体开启了引⽤和归属，则会展示参考资料。 如果需要展示⼯作流中的知识库节点的引⽤和归属，请直接将知

识库的  outputList  传给 end 节点，在 end 节点选择「返回变量，由 Bot ⽣成回答」，并设置参数名为  outputList  ⼯作流：

效果：

hiagent.deyunai.com:32300/platform/doc/faq/usage-consultation/workﬂow

1/5

识图提问2026/1/30 22:32

⼯作流 - HiAgent Document

⼯作流中不⽀持 CodeInterpreter ⼯具？

该⼯具要⽤到智能体的模型去⽣成代码，因此只能在智能体中使⽤，不⽀持在⼯作流、对话流中使⽤。

hiagent.deyunai.com:32300/platform/doc/faq/usage-consultation/workﬂow

2/5

2026/1/30 22:32

⼯作流 - HiAgent Document

如何使⽤⼯作流代码节点处理输出？

示例： 上个节点输出内容：

{
  "raw_output": "```json\n{\n  \"stock_name\": \"杭州银⾏\",\n  \"stock_code\": \"600926\",\n  \"report_year\": \"2024\",\n  \"report_season\": \"Q1\"\n

}

代码节点处理代码：抽取上个⼯作流节点的 json 输出

hiagent.deyunai.com:32300/platform/doc/faq/usage-consultation/workﬂow

3/5

2026/1/30 22:32

⼯作流 - HiAgent Document

# ⽅法定义不能修改

import re

def handler(params):
    # 返回值是⼀个可序列化成 json 的 dict 或 object，根据上个节点的输出内容的分隔符进⾏变量输出

    text = params['input']

    stock_name = re.search(r'"stock_name": "([^"]+)",', text).group(1)

    stock_code = re.search(r'"stock_code": "([^"]+)",', text).group(1)

    report_year = re.search(r'"report_year": "([^"]+)",', text).group(1)

    report_season = re.search(r'"report_season": "([^"]+)"', text).group(1)

    ret = {

        "key0": text,

        "stock_name": stock_name,

        "stock_code": stock_code,

        "report_year": report_year,

        "report_season": report_season

    }

    return ret

代码节点⼯作流使⽤图示：

hiagent.deyunai.com:32300/platform/doc/faq/usage-consultation/workﬂow

4/5

2026/1/30 22:32

⼯作流 - HiAgent Document

上⼀⻚

智能体

下⼀⻚

知识库

hiagent.deyunai.com:32300/platform/doc/faq/usage-consultation/workﬂow

5/5

