"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { TypingDots } from "@/components/TypingDots";
import { ProductCard } from "@/components/ProductCard";
import { postChat } from "@/lib/api";
import type { ChatMessage, ChatResponse, PartCard } from "@/types/chat";
import { Header } from "@/components/Header";

const SUGGESTIONS: string[] = [
  "My ice maker isn't working",
  "Find parts for model WDT780SAEM1",
  "Is part PS11752778 compatible with my fridge?",
  "How do I install a dishwasher drain pump?",
  "What are common refrigerator repairs?",
  "How do I track my order?",
  "What is the return policy?",
];

function Avatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#0066CC] text-xs font-semibold text-white">
      PS
    </div>
  );
}

function Bubble({
  role,
  children,
}: {
  role: "user" | "assistant";
  children: React.ReactNode;
}) {
  const isUser = role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start gap-3"}>
      {!isUser ? <Avatar /> : null}
      <div
        className={[
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm",
          isUser
            ? "bg-[#0066CC] text-white"
            : "bg-white text-zinc-900 border border-zinc-200",
        ].join(" ")}
      >
        {children}
      </div>
    </div>
  );
}

function AssistantMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="mt-3 text-base font-semibold first:mt-0">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="mt-3 text-base font-semibold first:mt-0">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="mt-3 text-sm font-semibold first:mt-0">{children}</h3>
        ),
        p: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        ul: ({ children }) => (
          <ul className="mt-2 list-disc pl-5">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mt-2 list-decimal pl-5">{children}</ol>
        ),
        li: ({ children }) => <li className="mt-1">{children}</li>,
        hr: () => <hr className="my-3 border-zinc-200" />,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-[#0066CC] underline underline-offset-2"
          >
            {children}
          </a>
        ),
        code: ({ children }) => (
          <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[13px] text-zinc-900">
            {children}
          </code>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold">{children}</strong>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export function ChatShell() {
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [history, setHistory] = React.useState<
    Array<{ role: string; content: unknown }>
  >([]);
  const [parts, setParts] = React.useState<PartCard[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const listRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isLoading, parts]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setError(null);
    setIsLoading(true);
    setParts([]);

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const res: ChatResponse = await postChat({
        message: trimmed,
        conversation_history: history,
        session_data: {},
      });

      setHistory(res.conversation_history ?? []);
      setMessages((m) => [...m, { role: "assistant", content: res.response || "" }]);
      setParts(Array.isArray(res.parts) ? res.parts : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  }

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50">
      <Header />
      <div className="flex h-[calc(100vh-64px)] flex-col">
      <div className="flex-1 overflow-hidden">
        <div ref={listRef} className="h-full overflow-y-auto px-4 py-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
            {isEmpty ? (
              <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
                <div className="text-2xl font-semibold text-zinc-900">
                  Hi — I’m your PartSelect assistant.
                </div>
                <div className="max-w-lg text-sm text-zinc-600">
                  I can help you diagnose issues, find the right part, and guide you through purchase and installation —{" "}
                  <span className="font-medium">for refrigerators and dishwashers only</span>.
                </div>
                <div className="mt-2 flex max-w-2xl flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-800 shadow-sm hover:bg-zinc-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((m, idx) => (
              <Bubble key={idx} role={m.role}>
                {m.role === "assistant" ? (
                  <AssistantMarkdown text={m.content} />
                ) : (
                  m.content
                )}
              </Bubble>
            ))}

            {isLoading ? (
              <Bubble role="assistant">
                <TypingDots />
              </Bubble>
            ) : null}

            {error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {error}
              </div>
            ) : null}

            {parts.length ? (
              <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2">
                {parts.map((p, i) => (
                  <ProductCard key={`${p.part_number}-${i}`} part={p} />
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-200 bg-white px-4 py-3">
        <div className="mx-auto w-full max-w-3xl">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a refrigerator or dishwasher part…"
            />
            <Button type="submit" disabled={isLoading || !input.trim()}>
              Send
            </Button>
          </form>
          <div className="mt-2 text-xs text-zinc-500">
            Specialized in refrigerator and dishwasher parts only.
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}

