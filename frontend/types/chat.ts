export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type PartCard = {
  name: string;
  part_number: string;
  price: string;
  stock: string;
  url: string;
  image: string;
};

export type ChatRequest = {
  message: string;
  conversation_history: Array<{ role: string; content: unknown }>;
  session_data: Record<string, unknown>;
};

export type ChatResponse = {
  response: string;
  parts: PartCard[];
  conversation_history: Array<{ role: string; content: unknown }>;
};

