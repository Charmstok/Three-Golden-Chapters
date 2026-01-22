# Context (Previous Chapter Summary)
这是上一章的剧情与节奏总结，请基于此背景进行本章分析，注意剧情的连贯性和伏笔的回收：
{previous_chapter_summary}

# Input Data (Current Chapter)
以下是本章的文本内容：
{jsonl_content}

# Analysis Requirement
请继续分析。在“黄金三章”中，第二、三章通常负责：
1. **强化冲突**：将第一章的危机具体化或扩大化。
2. **金手指/转折**：主角获得破局的关键能力或信息。
3. **期待感落地**：第一章埋下的悬念得到初步回应，并建立新的长期悬念。

请基于以上原则，对本章进行结构化拆解。

# Output JSON Schema
请严格按照以下 JSON 结构输出：
{
  "chapter_id": 1,
  "chunks": [
    {
      "chunk_id": 1,
      "start_paragraph": <int>,
      "end_paragraph": <int>,
      "slices": [
        {
          "slice_id": 1,
          "start": <int>,
          "end": <int>,
          "content_summary": "<简要概括该片段发生了什么>",
          "pacing_analysis": "<节奏拆解，例如：引入突发危机，拉高读者紧张感>",
          "hook_extraction": "<爆点/钩子提取，若无则填“无”>"
        },
        ...
      ],
      "plot_summary": "<该Chunk的剧情总结>",
      "pacing_summary": "<该Chunk的节奏总结，例如：先抑后扬，通过压抑环境衬托主角困境>"
    },
    ...
  ]
}