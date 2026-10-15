// Observe local backend return receipts while the browser keeps following the book.
import { useEffect, useState } from "react";
import { returnLabel } from "../state/return";

export function ReturnStatus({ sequence, pending }: { sequence: number; pending: boolean }) {
  const [label, setLabel] = useState("Checking chat connection…");
  useEffect(() => {
    let stopped = false;
    const update = async () => {
      try {
        const reply = await fetch("/api/return", { cache: "no-store" });
        const result: unknown = reply.ok ? await reply.json() : null;
        if (!stopped) setLabel(returnLabel(result));
      } catch {
        if (!stopped) setLabel("Chat status unavailable · explicit follow-up is available");
      }
    };
    void sequence;
    void update();
    const timer = pending ? window.setInterval(() => void update(), 2000) : undefined;
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, [sequence, pending]);
  return (
    <output className="progress-line" aria-label="Chat return status">
      {label}
    </output>
  );
}
