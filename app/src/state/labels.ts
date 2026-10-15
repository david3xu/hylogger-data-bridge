// Name review choices and the successor chapters they create without rewriting saved page titles.
import type { DecisionChoice, Page } from "./contracts";

export const CHOICE_LABELS: Record<DecisionChoice, string> = {
  accept: "Continue with this evidence",
  modify: "Change the investigation",
  reject: "Set this candidate aside",
};

export function chapterTitle(page: Page, pages: readonly Page[]): string {
  const previous = pages.find((item) => item.id === page.parent_id);
  return previous?.decision ? CHOICE_LABELS[previous.decision.choice] : page.title;
}
