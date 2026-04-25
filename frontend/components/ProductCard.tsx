import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { PartCard } from "@/types/chat";

function stockVariant(stock: string): "success" | "destructive" | "secondary" {
  const s = (stock || "").toLowerCase();
  if (!s) return "secondary";
  if (s.includes("in stock") || s.includes("available")) return "success";
  if (s.includes("out of stock") || s.includes("unavailable")) return "destructive";
  return "secondary";
}

export function ProductCard({ part }: { part: PartCard }) {
  return (
    <Card className="overflow-hidden border-zinc-200/90 shadow-sm transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-start gap-3 pb-2">
        <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg border border-zinc-200 bg-white">
          {part.image ? (
            <Image
              src={part.image}
              alt={part.name || part.part_number}
              fill
              className="object-contain p-1"
              sizes="80px"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-[10px] text-zinc-400">
              No image
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-sm font-semibold leading-snug text-zinc-900">
            {part.name || "Part"}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-zinc-600">{part.part_number}</span>
            {part.stock ? (
              <Badge variant={stockVariant(part.stock)} className="text-[10px]">
                {part.stock}
              </Badge>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 border-t border-zinc-100 bg-zinc-50/50 pt-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-lg font-bold text-[#0b6a6a]">{part.price || "—"}</div>
        <Button
          asChild
          className="w-full bg-[#0b6a6a] text-white hover:bg-[#095858] sm:w-auto"
        >
          <a href={part.url} target="_blank" rel="noreferrer">
            View on PartSelect
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}
