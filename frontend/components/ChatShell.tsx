"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { TypingDots } from "@/components/TypingDots";
import { ProductCard } from "@/components/ProductCard";
import { postChat } from "@/lib/api";
import type {
  ChatMessage,
  ChatResponse,
  KnowledgeSource,
  PartCard,
} from "@/types/chat";
import { Header } from "@/components/Header";

const SUGGESTIONS: string[] = [
  "My ice maker isn't working",
  "Find parts for model WDT780SAEM1",
  "Is part PS11752778 compatible with my fridge?",
  "Dishwasher not draining — what part do I need?",
  "How do I track my order?",
  "What is the return policy?",
];

function Avatar() {
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0b6a6a] text-xs font-bold text-white ring-2 ring-white shadow-sm">
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
          "max-w-[min(100%,42rem)] rounded-2xl px-4 py-3 text-[15px] leading-relaxed shadow-sm",
          isUser
            ? "bg-[#0b6a6a] text-white"
            : "border border-zinc-200/90 bg-white text-zinc-900",
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
        h1: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        h2: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        h3: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        hr: () => null,
        p: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        ul: ({ children }) => <ul className="mt-2 list-disc pl-5">{children}</ul>,
        ol: ({ children }) => <ol className="mt-2 list-decimal pl-5">{children}</ol>,
        li: ({ children }) => <li className="mt-1">{children}</li>,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="break-all font-medium text-[#0b6a6a] underline underline-offset-2"
          >
            {children}
          </a>
        ),
        code: ({ children }) => (
          <span className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[13px] text-zinc-900">
            {children}
          </span>
        ),
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function TurnAttachments({
  parts,
  sources,
}: {
  parts: PartCard[];
  sources: KnowledgeSource[];
}) {
  if (!parts.length && !sources.length) return null;
  return (
    <div className="ml-0 flex max-w-[min(100%,48rem)] flex-col gap-3 pl-0 sm:ml-12">
      {sources.length ? (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-zinc-900 shadow-sm">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-900/80">
            From PartSelect help &amp; guides
          </div>
          <ul className="mt-2 space-y-2">
            {sources.map((s, i) => (
              <li
                key={`${s.url}-${i}`}
                className="border-t border-amber-200/60 pt-2 first:border-t-0 first:pt-0"
              >
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="break-all text-sm font-medium text-[#0b6a6a] underline underline-offset-2"
                >
                  {s.url}
                </a>
                {s.page_kind ? (
                  <span className="ml-2 text-xs text-zinc-500">({s.page_kind})</span>
                ) : null}
                {s.snippet ? (
                  <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-zinc-600">
                    {s.snippet}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {parts.length ? (
        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Parts to consider
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {parts.map((p, i) => (
              <ProductCard key={`${p.part_number}-${i}`} part={p} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ChatShell() {
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [history, setHistory] = React.useState<
    Array<{ role: string; content: unknown }>
  >([]);
  const [sessionData, setSessionData] = React.useState<Record<string, unknown>>(
    {}
  );
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const listRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isLoading, error]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setError(null);
    setIsLoading(true);

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const res: ChatResponse = await postChat({
        message: trimmed,
        conversation_history: history,
        session_data: sessionData,
      });

      setHistory(res.conversation_history ?? []);

      const nextParts = Array.isArray(res.parts) ? res.parts : [];
      const parts = nextParts.filter(
        (p) => Boolean(p?.url) && Boolean(p?.name || p?.part_number)
      );
      const nextSources = Array.isArray(res.sources) ? res.sources : [];
      const sources = nextSources.filter(
        (s): s is KnowledgeSource => Boolean(s?.url) && typeof s.url === "string"
      );

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.response || "",
          parts: parts.length ? parts : undefined,
          sources: sources.length ? sources : undefined,
        },
      ]);

      setSessionData((prev) => {
        const next = { ...prev };
        const upper = trimmed.toUpperCase();

        const psMatch = upper.match(/\bPS\d{5,}\b/);
        if (psMatch) next.last_part_number = psMatch[0];

        const modelMatch = upper.match(/\b[A-Z0-9]{6,}\b/g);
        if (modelMatch) {
          const best = modelMatch.sort((a, b) => b.length - a.length)[0];
          if (best && best !== (next.last_part_number as string | undefined)) {
            next.last_model_number = best;
          }
        }

        if (/\bFRIDGE\b|\bREFRIGERATOR\b|\bFREEZER\b|\bICE MAKER\b/i.test(trimmed)) {
          next.user_stated_appliance = "refrigerator";
        } else if (/\bDISHWASHER\b/i.test(trimmed)) {
          next.user_stated_appliance = "dishwasher";
        }

        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  }

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex min-h-screen flex-col bg-zinc-100">
      <Header />
      <main className="flex min-h-0 flex-1 flex-col">
        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            {isEmpty ? (
              <div className="flex flex-col items-center gap-5 py-12 text-center sm:py-16">
                <div className="rounded-2xl border border-zinc-200 bg-white px-8 py-10 shadow-sm">
                  <div className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl">
                    Find the right part — faster
                  </div>
                  <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-zinc-600">
                    Refrigerator &amp; dishwasher only. Ask with a{" "}
                    <span className="font-medium text-zinc-800">model number</span> or{" "}
                    <span className="font-medium text-zinc-800">symptom</span>; we’ll
                    match parts, price, and stock when the site is reachable.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => send(s)}
                        className="rounded-full border border-zinc-200 bg-zinc-50 px-4 py-2 text-left text-sm text-zinc-800 shadow-sm transition hover:border-[#0b6a6a]/40 hover:bg-white"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            {messages.map((m, idx) => (
              <React.Fragment key={idx}>
                <Bubble role={m.role}>
                  {m.role === "assistant" ? (
                    <AssistantMarkdown text={m.content} />
                  ) : (
                    <div className="whitespace-pre-wrap break-words">{m.content}</div>
                  )}
                </Bubble>
                {m.role === "assistant" &&
                (m.parts?.length || m.sources?.length) ? (
                  <TurnAttachments
                    parts={m.parts ?? []}
                    sources={m.sources ?? []}
                  />
                ) : null}
              </React.Fragment>
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

            <p className="pb-2 text-center text-[11px] leading-relaxed text-zinc-500">
              Suggestions are based on our indexed PartSelect parts &amp; guides. Always
              confirm current price, fit, and stock on{" "}
              <a
                className="font-medium text-[#0b6a6a] underline"
                href="https://www.partselect.com"
                target="_blank"
                rel="noreferrer"
              >
                partselect.com
              </a>{" "}
              before you buy.
            </p>
          </div>
        </div>

        <div className="border-t border-zinc-200/80 bg-white/95 px-4 py-3 shadow-[0_-4px_24px_rgba(0,0,0,0.06)] backdrop-blur-sm">
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
                placeholder="Model number, part # (PS…), or symptom…"
                className="h-11 border-zinc-300 bg-white text-[15px] focus-visible:ring-[#0b6a6a]"
              />
              <Button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="h-11 shrink-0 bg-[#0b6a6a] px-5 text-white hover:bg-[#095858]"
              >
                Send
              </Button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
