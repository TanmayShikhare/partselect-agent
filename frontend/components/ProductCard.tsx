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
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start gap-3">
        <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50">
          {part.image ? (
            <Image
              src={part.image}
              alt={part.name || part.part_number}
              fill
              className="object-contain"
            />
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-sm font-semibold text-zinc-900">
            {part.name || "Part"}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-600">
            <span className="font-mono">{part.part_number}</span>
            {part.stock ? (
              <Badge variant={stockVariant(part.stock)}>{part.stock}</Badge>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-zinc-900">
          {part.price || ""}
        </div>
        <Button asChild>
          <a href={part.url} target="_blank" rel="noreferrer">
            View on PartSelect
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

