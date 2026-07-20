import assert from "node:assert/strict";
import test from "node:test";
import { normalizeToken, parseTsv, pdfPointBox, typedValue } from "../web/browser-ocr.js";

test("browser OCR typed parsing is strict", () => {
  assert.equal(typedValue("$2,166.00", "currency"), 2166);
  assert.equal(typedValue("2026-06-27", "date"), "2026-06-27");
  assert.equal(typedValue("27 June 2026", "date"), null);
  assert.equal(typedValue("weekly", "frequency"), "weekly");
  assert.equal(typedValue("quarterly", "frequency"), null);
});

test("browser OCR normalizes labels and parses word geometry", () => {
  assert.equal(normalizeToken("Pay-Date:"), "PAYDATE");
  const parsed = parseTsv("level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t10\t20\t30\t10\t96\tGROSS\n5\t1\t1\t1\t50\t20\t30\t10\t95\tPAY");
  assert.equal(parsed.malformed, false);
  assert.equal(parsed.lines[0].words.length, 2);
  assert.deepEqual(pdfPointBox(612, 792, 100, 100, [{ left: 10, top: 20, width: 30, height: 10 }]), [61.2, 554.4, 244.8, 633.6]);
});

test("malformed or low-confidence TSV does not produce usable words", () => {
  assert.equal(parseTsv("not tsv").malformed, true);
  const parsed = parseTsv("level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t10\t20\t30\t10\t89\tEMPLOYEE");
  assert.equal(parsed.lines[0].words[0].confidence, 89);
});
