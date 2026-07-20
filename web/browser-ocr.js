let pdfjsLibPromise;
let tesseractPromise;

export const OCR_DPI = 300;
export const OCR_MIN_CONFIDENCE = 90;
export const OCR_TIMEOUT_MS = 30000;

const numberKinds = new Set(["integer", "number", "currency"]);

export function normalizeToken(value) {
  return String(value).toUpperCase().replace(/[^A-Z0-9]/g, "");
}

export function typedValue(raw, kind) {
  const value = String(raw ?? "").trim();
  if (kind === "string") return value || null;
  if (kind === "date") return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
  if (kind === "month") return /^\d{4}-\d{2}$/.test(value) ? value : null;
  if (kind === "frequency") return ["weekly", "biweekly", "semimonthly", "monthly", "annual"].includes(value.toLowerCase()) ? value.toLowerCase() : null;
  if (numberKinds.has(kind)) {
    const numericText = value.replace(/[^0-9.-]/g, "");
    if (!numericText) return null;
    const numeric = Number(numericText);
    if (!Number.isFinite(numeric)) return null;
    if (kind === "integer") return Number.isInteger(numeric) ? numeric : null;
    return kind === "number" && Number.isInteger(numeric) ? numeric : numeric;
  }
  return null;
}

export function parseTsv(tsv) {
  const rows = String(tsv || "").split(/\r?\n/).filter(Boolean);
  if (!rows.length) return { lines: [], text: "", malformed: true };
  if (!rows[0].includes("\t")) return { lines: [], text: "", malformed: true };
  const standardHeaders = ["level", "page_num", "block_num", "par_num", "line_num", "word_num", "left", "top", "width", "height", "conf", "text"];
  const firstCells = rows[0].split("\t");
  const headers = firstCells[0] === "level" ? rows.shift().split("\t") : standardHeaders;
  const required = ["level", "block_num", "par_num", "line_num", "left", "top", "width", "height", "conf", "text"];
  if (!required.every((key) => headers.includes(key))) return { lines: [], text: "", malformed: true };
  const index = Object.fromEntries(headers.map((header, i) => [header, i]));
  const grouped = new Map();
  const text = [];
  try {
    for (const row of rows) {
      const cells = row.split("\t");
      const wordText = cells[index.text]?.trim();
      if (!wordText || !Number.isFinite(Number(cells[index.conf]))) continue;
      const word = { text: wordText, confidence: Number(cells[index.conf]), left: Number(cells[index.left]), top: Number(cells[index.top]), width: Number(cells[index.width]), height: Number(cells[index.height]) };
      if (!Object.values(word).every((item) => typeof item === "string" || Number.isFinite(item))) throw new Error("malformed TSV");
      text.push(wordText);
      const key = [cells[index.block_num], cells[index.par_num], cells[index.line_num]].join(":");
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(word);
    }
  } catch { return { lines: [], text: "", malformed: true }; }
  const lines = [...grouped.values()].map((words) => {
    words.sort((a, b) => a.left - b.left);
    return { words, left: Math.min(...words.map((word) => word.left)), right: Math.max(...words.map((word) => word.left + word.width)), top: Math.min(...words.map((word) => word.top)), bottom: Math.max(...words.map((word) => word.top + word.height)) };
  }).sort((a, b) => a.top - b.top || a.left - b.left);
  return { lines, text: text.join(" "), malformed: false };
}

function parseWords(words) {
  const groups = (words || []).reduce((groups, word) => {
    const key = word.line?.text || `${word.block_num || 0}:${word.line_num || 0}`;
    if (!groups.has(key)) groups.set(key, []);
    const box = word.bbox || {};
    groups.get(key).push({ text: word.text, confidence: Number(word.confidence ?? word.conf ?? 0), left: Number(box.x0), top: Number(box.y0), width: Number(box.x1 - box.x0), height: Number(box.y1 - box.y0) });
    return groups;
  }, new Map());
  return [...groups.values()].map((lineWords) => {
    lineWords.sort((a, b) => a.left - b.left);
    return { words: lineWords, left: Math.min(...lineWords.map((word) => word.left)), right: Math.max(...lineWords.map((word) => word.left + word.width)), top: Math.min(...lineWords.map((word) => word.top)), bottom: Math.max(...lineWords.map((word) => word.top + word.height)) };
  }).sort((a, b) => a.top - b.top || a.left - b.left);
}

function parseBlocks(data) {
  const words = [];
  for (const block of data?.blocks || []) for (const paragraph of block.paragraphs || []) for (const line of paragraph.lines || []) for (const word of line.words || []) words.push({ ...word, line: { text: line.text } });
  return parseWords(words);
}

export function pdfPointBox(pageWidth, pageHeight, pixelWidth, pixelHeight, words) {
  const x0 = Math.min(...words.map((word) => word.left));
  const y0 = Math.min(...words.map((word) => word.top));
  const x1 = Math.max(...words.map((word) => word.left + word.width));
  const y1 = Math.max(...words.map((word) => word.top + word.height));
  return [x0 * pageWidth / pixelWidth, pageHeight - y1 * pageHeight / pixelHeight, x1 * pageWidth / pixelWidth, pageHeight - y0 * pageHeight / pixelHeight].map((value) => Math.round(value * 100) / 100);
}

function valueWords(lines, labelLine, labelRight, leftLimit, rightLimit, kind) {
  for (const line of lines) {
    const candidates = line === labelLine ? line.words.filter((word) => word.left >= labelRight) : line.top >= labelLine.bottom - 2 && line.top - labelLine.bottom <= OCR_DPI * 1.5 ? line.words : [];
    const eligible = candidates.filter((word) => word.confidence >= OCR_MIN_CONFIDENCE && leftLimit <= word.left + word.width / 2 && word.left + word.width / 2 < rightLimit);
    if (eligible.length && typedValue(eligible.map((word) => word.text).join(" "), kind) !== null) return eligible;
  }
  return null;
}

export function extractPageFields(page, pageNumber, pixelWidth, pixelHeight, lines, labels, metadata) {
  const located = new Map();
  for (const item of labels) {
    const labelTokens = item.label.split(/\s+/).map(normalizeToken);
    for (const line of lines) {
      for (let start = 0; start <= line.words.length - labelTokens.length; start += 1) {
        const candidate = line.words.slice(start, start + labelTokens.length);
        if (candidate.every((word) => word.confidence >= OCR_MIN_CONFIDENCE) && candidate.map((word) => normalizeToken(word.text)).join(" ") === labelTokens.join(" ")) {
          located.set(item.field, { item, line, start, end: start + labelTokens.length });
          break;
        }
      }
      if (located.has(item.field)) break;
    }
  }
  const result = [];
  for (const item of labels) {
    const found = located.get(item.field);
    if (!found) continue;
    const labelWords = found.line.words.slice(found.start, found.end);
    const labelLeft = Math.min(...labelWords.map((word) => word.left));
    const labelRight = Math.max(...labelWords.map((word) => word.left + word.width));
    const rowLabels = [...located.entries()].filter(([, value]) => value.line === found.line).map(([field, value]) => ({ field, left: Math.min(...value.line.words.slice(value.start, value.end).map((word) => word.left)), right: Math.max(...value.line.words.slice(value.start, value.end).map((word) => word.left + word.width)) })).sort((a, b) => a.left - b.left);
    const position = rowLabels.findIndex((label) => label.field === item.field);
    const leftLimit = position ? (rowLabels[position - 1].right + labelLeft) / 2 : -Infinity;
    const rightLimit = position + 1 < rowLabels.length ? (labelRight + rowLabels[position + 1].left) / 2 : Infinity;
    const words = valueWords(lines, found.line, labelRight, leftLimit, rightLimit, item.kind);
    if (!words) continue;
    const rawValue = words.map((word) => word.text).join(" ");
    const value = typedValue(rawValue, item.kind);
    if (value === null || !metadata.allowlisted_fields.includes(item.field)) continue;
    result.push({ field: item.field, value, raw_value: rawValue, page: pageNumber, bbox: pdfPointBox(page.view[2], page.view[3], pixelWidth, pixelHeight, words), bbox_units: "pdf_points_bottom_left_origin", confidence: "medium", confidence_reason: "Known label, strict typed value, and geometric OCR source box matched. OCR evidence remains review-required.", extraction_method: "ocr", ocr_confidence: Math.round(Math.min(...labelWords.concat(words).map((word) => word.confidence)) * 100) / 100, confirmation_state: "pending", document_id: metadata.document_id, purpose: metadata.purposes?.[item.field] || "Allowlisted source evidence." });
  }
  return result;
}

function abortable(promise, timeoutMs) {
  return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(`Browser OCR timed out after ${timeoutMs} ms.`)), timeoutMs))]);
}

export async function recoverDocument(bytes, metadata, onProgress = () => {}) {
  if (!window.Worker || !window.WebAssembly || !window.crypto?.subtle || !document.createElement("canvas").getContext) throw new Error("This browser cannot run the ephemeral OCR fallback.");
  let worker;
  let pdf;
  const fields = [];
  try {
    pdfjsLibPromise ||= import("./vendor/pdfjs/pdf.min.mjs");
    tesseractPromise ||= import("./vendor/tesseract/tesseract.esm.min.js");
    const pdfjsLib = await pdfjsLibPromise;
    const { createWorker } = (await tesseractPromise).default;
    pdfjsLib.GlobalWorkerOptions.workerSrc = "./vendor/pdfjs/pdf.worker.min.mjs";
    onProgress("Rendering supplied PDF in this browser");
    pdf = await pdfjsLib.getDocument({ data: new Uint8Array(bytes) }).promise;
    worker = await abortable(createWorker("eng", 1, { workerPath: "./vendor/tesseract/worker.min.js", corePath: "./vendor/tesseract/tesseract-core.wasm.js", langPath: "./vendor/tesseract", cacheMethod: "none", logger: (message) => onProgress(message.status || "Recovering in this browser") }), OCR_TIMEOUT_MS);
    await worker.setParameters({ tessedit_pageseg_mode: "6", preserve_interword_spaces: "1" });
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: OCR_DPI / 72 });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width; canvas.height = viewport.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      await page.render({ canvasContext: context, viewport, background: "white" }).promise;
      const recognized = await abortable(worker.recognize(canvas, {}, { tsv: true }), OCR_TIMEOUT_MS);
      const tsvParsed = recognized.data?.tsv ? parseTsv(recognized.data.tsv) : null;
      const parsed = tsvParsed?.lines.length ? tsvParsed : { lines: parseBlocks(recognized.data), text: recognized.data?.text || "", malformed: false };
      if (parsed.malformed || !parsed.lines.length) throw new Error(`Browser OCR returned malformed or empty output (${Object.keys(recognized.data || {}).join(",")}; text=${(recognized.data?.text || "").length}; tsv=${JSON.stringify(String(recognized.data?.tsv || "").slice(0, 160))}).`);
      fields.push(...extractPageFields(page, pageNumber, canvas.width, canvas.height, parsed.lines, metadata.labels, { ...metadata, allowlisted_fields: metadata.allowlisted_fields }));
      canvas.width = 1; canvas.height = 1;
      page.cleanup();
      onProgress(`Recovered ${fields.length} candidate field${fields.length === 1 ? "" : "s"}`);
    }
    const expected = metadata.labels.length;
    const unique = [...new Map(fields.map((field) => [field.field, field])).values()];
    return { ...metadata.document, extraction_engine: "browser_tesseract_ocr_v1", extraction_status: unique.length === expected ? "extracted" : unique.length ? "partial" : "abstained", extraction_method: "ocr", confidence: "medium", extraction_summary: `Recovered ${unique.length} of ${expected} allowlisted fields from OCR with every used token at or above 90% confidence.${unique.length < expected ? ` Unrecovered fields remain for qualified human review.` : ""}`, abstention_reason: unique.length ? null : "No allowlisted label/value pairs qualified for browser OCR at the required 90% token-confidence threshold.", contains_untrusted_content: false, fields: unique };
  } finally {
    if (worker) await worker.terminate().catch(() => {});
    if (pdf) await pdf.cleanup().catch(() => {});
  }
}
