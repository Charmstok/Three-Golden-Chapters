import type {
  Book,
  BookDetail,
  ModelConfig,
  ModelInput,
  ModelProbe,
} from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error("无法连接服务，请检查后端是否已启动。");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `请求失败（${response.status}），请稍后重试。`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const api = {
  books: () => request<Book[]>("/books"),
  book: (id: string) => request<BookDetail>(`/books/${id}`),
  models: () => request<ModelConfig>("/models"),
  saveModel: (value: ModelInput, id?: string) =>
    request<ModelConfig>(
      id ? `/models/${id}` : "/models",
      json(id ? "PUT" : "POST", value),
    ),
  deleteModel: (id: string) =>
    request<void>(`/models/${id}`, { method: "DELETE" }),
  defaultModel: (id: string) =>
    request<ModelConfig>(`/models/${id}/default`, { method: "POST" }),
  discoverModels: (value: ModelProbe) =>
    request<{ models: string[] }>("/models/discover", json("POST", value)),
  testModel: (value: ModelProbe) =>
    request<{ ok: boolean; latency_ms: number }>(
      "/models/test",
      json("POST", value),
    ),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<BookDetail>("/books", { method: "POST", body });
  },
  analyze: (id: string, profileId: string) =>
    request<BookDetail>(`/books/${id}/analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId }),
    }),
  delete: (id: string) => request<void>(`/books/${id}`, { method: "DELETE" }),
};
