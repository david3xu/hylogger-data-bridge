// Verify note drafts survive reload without committing, and each explicit action commits exact input.
import { Children, isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import fixtures from "../../../schemas/fixtures/v1/Book.json";
import { checkBook, type DecisionChoice, type Page } from "../state/contracts";
import { CHOICE_LABELS, chapterTitle } from "../state/labels";
import { getDraft, initialReader, updateDraft } from "../state/reader";
import { loadPersistedReader, savePersistedReader } from "../transport/useBook";
import { DecisionForm } from "./DecisionForm";

const note = '  Automated test: inspect "SWIR"\nExact whitespace — Δ  ';
function ready(): Page {
  const page = checkBook(structuredClone(fixtures.valid["decided-with-successor"])).pages[0];
  return { ...page, status: "ready", decision: null };
}
function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  const found: ReactElement<Record<string, unknown>>[] = [];
  Children.forEach(node, (child) => {
    if (isValidElement<Record<string, unknown>>(child)) {
      found.push(child, ...elements(child.props.children as ReactNode));
    }
  });
  return found;
}
afterEach(() => vi.unstubAllGlobals());

it("autosaves exact draft text for reload and reports denied browser storage", () => {
  const data = new Map<string, string>();
  vi.stubGlobal("window", {
    sessionStorage: {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => data.set(key, value),
    },
  });
  const page = ready();
  const reader = updateDraft(initialReader, page, "modify", note);
  expect(savePersistedReader(reader)).toBe(true);
  const restored = loadPersistedReader();
  expect(restored.drafts[page.id].note).toBe(note);
  expect(restored.drafts[page.id].choice).toBe("modify");
  expect(restored.drafts[page.id].requestId).toBe("");
  expect(restored.book).toBeNull(); // Browser draft persistence never invents a committed decision.
  vi.stubGlobal("window", {
    get sessionStorage() {
      throw new Error("Storage disabled");
    },
  });
  expect(savePersistedReader(reader)).toBe(false);
  expect(loadPersistedReader()).toBe(initialReader);
});

it("typing only edits a draft; each action commits its own choice and the exact latest note", async () => {
  const page = ready();
  const change = vi.fn();
  const submit = vi.fn(async () => true);
  const tree = DecisionForm({
    page,
    draft: { ...getDraft(initialReader, page), note },
    busy: false,
    draftSaveStatus: "unavailable",
    onChangeDraft: change,
    onSubmitDecision: submit,
  });
  const nodes = elements(tree);
  const textarea = nodes.find((node) => node.type === "textarea");
  const edit = textarea?.props.onChange as (event: { target: { value: string } }) => void;
  edit({ target: { value: "unfinished note" } });
  expect(change).toHaveBeenCalledWith("accept", "unfinished note");
  expect(submit).not.toHaveBeenCalled();
  const actions = nodes.filter((node) => node.type === "button");
  expect(actions).toHaveLength(3);
  for (const [index, choice] of ["accept", "modify", "reject"].entries()) {
    await (actions[index].props.onClick as () => Promise<boolean>)();
    expect(submit).toHaveBeenLastCalledWith(choice, note);
  }
  expect(submit).toHaveBeenCalledTimes(3);
  const html = renderToStaticMarkup(tree);
  expect(html).not.toContain("Record decision &amp; turn page");
  expect(html).not.toContain('type="radio"');
  expect(html).toContain("Draft cannot be saved");
  expect(html.indexOf("<textarea")).toBeLessThan(html.indexOf("<button"));
});

it.each(["accept", "modify", "reject"] as DecisionChoice[])(
  "names the successor from its parent’s %s choice, not its own later decision",
  (choice) => {
    const book = checkBook(structuredClone(fixtures.valid["decided-with-successor"]));
    const parent = book.pages[0];
    if (!parent.decision) throw new Error("fixture needs a parent decision");
    parent.decision.choice = choice;
    const successor = book.pages[1];
    const originalTitle = successor.title;
    expect(chapterTitle(successor, book.pages)).toBe(CHOICE_LABELS[choice]);
    expect(chapterTitle(parent, book.pages)).toBe(parent.title);
    expect(successor.title).toBe(originalTitle);
  },
);
