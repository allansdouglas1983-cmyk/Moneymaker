import { assertEquals } from "jsr:@std/assert";
import { entryTiming, minutesToStart } from "./board.ts";

Deno.test("minutes to scheduled start, or null when the start is unknown", () => {
  const now = Date.parse("2026-07-30T12:00:00Z");
  assertEquals(minutesToStart("2026-07-30T13:00:00Z", now), 60);
  assertEquals(minutesToStart("2026-07-30T12:00:00Z", now), 0);
  // Already past its scheduled start: negative, never clamped. A clamp would hide the
  // single most dangerous state — a match that may already be in play.
  assertEquals(minutesToStart("2026-07-30T11:45:00Z", now), -15);
  // Manual entries carry no start time. Absent, never assumed.
  assertEquals(minutesToStart(null, now), null);
  assertEquals(minutesToStart(undefined, now), null);
});

Deno.test("the entry window is bounded on both sides, and the late bound is a safety rule", () => {
  const now = Date.parse("2026-07-30T12:00:00Z");
  const at = (iso: string) => entryTiming(iso, now);

  // Early: the price is no better as a forecast (TE-0006 found log loss flat across
  // horizons) but the spread is measurably wider and top-of-book depth roughly halved,
  // so acting here pays a real cost for no information.
  assertEquals(at("2026-07-31T12:00:00Z"), "TOO_EARLY");
  assertEquals(at("2026-07-30T14:00:00Z"), "TOO_EARLY");

  // The window. Spread has reached its floor and the match cannot plausibly have started.
  assertEquals(at("2026-07-30T13:30:00Z"), "ACT");
  assertEquals(at("2026-07-30T12:45:00Z"), "ACT");
  assertEquals(at("2026-07-30T12:30:00Z"), "ACT");

  // Late. NOT because the book is worse — spread is flat from T-30m to T-2m, so this
  // costs essentially nothing. Because tennis matches can START EARLY: SPEC-022 and
  // conceptual audit F-01 both say scheduled start is not a safe live boundary for a
  // sport whose events can begin ahead of schedule. Standing in front of a market that
  // has already gone in-play would breach a hard prohibition with real money behind it.
  assertEquals(at("2026-07-30T12:29:00Z"), "TOO_LATE");
  assertEquals(at("2026-07-30T12:01:00Z"), "TOO_LATE");
  assertEquals(at("2026-07-30T11:30:00Z"), "TOO_LATE");

  // No scheduled start recorded is its own state, never silently treated as actionable.
  assertEquals(entryTiming(null, now), "UNKNOWN");
});
