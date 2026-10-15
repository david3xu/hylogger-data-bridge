// Require actual receipt phases before describing a decision as queued or completed.
import { expect, test } from "vitest";
import { returnLabel } from "./state/return";

test("unbound and malformed status never claim successful delivery", () => {
  expect(returnLabel({ phase: "manual" })).toContain("not connected");
  expect(returnLabel({ active: true })).toBe("Chat status unavailable");
});
test("queue receipt differs from completed work", () => {
  expect(returnLabel({ phase: "queued" })).toContain("waiting");
  expect(returnLabel({ phase: "completed" })).toContain("new evidence is ready");
});
test("uncertain and failed return remain actionable", () => {
  expect(returnLabel({ phase: "uncertain" })).toContain("uncertain");
  expect(returnLabel({ phase: "failed" })).toContain("explicit follow-up");
});
