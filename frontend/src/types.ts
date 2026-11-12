export type BookStatus =
  "ready" | "queued" | "running" | "completed" | "failed";
export interface Paragraph {
  paragraph_id: number;
  text: string;
}
export interface Chapter {
  id: number;
  no: number;
  title: string;
  paragraphs: Paragraph[];
}
export interface Slice {
  slice_id: number;
  start: number;
  end: number;
  content_summary: string;
  pacing_analysis: string;
  hook_extraction: string;
}
export interface Chunk {
  chunk_id: number;
  chunk_title: string;
  start_paragraph: number;
  end_paragraph: number;
  plot_summary: string;
  pacing_summary: string;
  slices: Slice[];
}
export interface Analysis {
  chapter_id: number;
  chunks: Chunk[];
}
export interface Book {
  id: string;
  title: string;
  filename: string;
  created_at: string;
  status: BookStatus;
  progress: number;
  message: string;
  error: string | null;
  profile_id: string | null;
  chapter_count: number;
  paragraph_count: number;
}
export interface BookDetail extends Book {
  chapters: Chapter[];
  analyses: Analysis[];
}
export interface ModelProfile {
  id: string;
  label: string;
  model: string;
  configured: boolean;
  base_url: string;
  has_api_key: boolean;
  params: ModelParameters;
}
export interface ModelConfig {
  default_profile: string | null;
  profiles: ModelProfile[];
}

export interface ModelParameters {
  api_format: "auto" | "chat_completions" | "responses";
  temperature: number | null;
  max_tokens: number | null;
  token_limit_field: "max_tokens" | "max_completion_tokens";
  timeout_s: number;
  extra_body: Record<string, unknown>;
}
export interface ModelInput {
  label: string;
  base_url: string;
  api_key?: string;
  clear_api_key: boolean;
  model: string;
  params: ModelParameters;
  make_default: boolean;
}
export interface ModelProbe {
  base_url: string;
  api_key?: string;
  clear_api_key: boolean;
  saved_id?: string;
  model: string;
  params: ModelParameters;
}
