# Input Data (Chapter 1)
以下是第一章的文本内容：
{jsonl_content} 

# Analysis Requirement
请根据“黄金三章”法则（开篇得有危机、悬念或强烈冲突，快速代入主角视角）对第一章进行拆解。

# Output JSON Schema
请严格按照以下 JSON 结构输出：
{
  "chapter_id": 1,
  "chunks": [
    {
      "chunk_id": 1,
      "chunk_title": "<给该 chunk 起一个简要标题>",
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
