import type { ChatRequest, ChatResponse } from "@/types/chat";

const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function postChat(
  payload: ChatRequest,
  baseUrl: string = DEFAULT_BASE_URL
): Promise<ChatResponse> {
  const res = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Backend error (${res.status}): ${text || res.statusText}`);
  }

  return (await res.json()) as ChatResponse;
}

