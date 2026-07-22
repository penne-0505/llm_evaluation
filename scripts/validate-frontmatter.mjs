// Deno版バリデータ: npm / remote import 依存なしで front-matter と stale ロジックを検証

import { loadScope, makeInScope } from "./scope.mjs";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MS_PER_DAY = 1000 * 60 * 60 * 24;
const STALE_DAYS = 30;
const RISKS = ["Low", "Medium", "High", "Critical"];
const QA_STATUS_VALUES = [
  "planned",
  "in-progress",
  "verified",
  "partial",
  "failed",
  "blocked",
];
const REQUIRED_KEYS = [
  "title",
  "status",
  "draft_status",
  "created_at",
  "updated_at",
  "references",
  "related_issues",
  "related_prs",
];
const REQUIRED_SCALARS = [
  "title",
  "status",
  "draft_status",
  "created_at",
  "updated_at",
];
const STATUS_VALUES = ["proposed", "active", "superseded", "obsolete"];
const DRAFT_STATUS_VALUES = ["idea", "exploring", "paused", "n/a"];
const COMMON_KEYS = new Set(REQUIRED_KEYS);
const DRAFT_ONLY_KEYS = new Set([
  "stale_exempt_until",
  "stale_exempt_reason",
  "stale_extensions",
]);
const QA_ONLY_KEYS = new Set(["qa_status", "risk", "qa_schema"]);
const INTENT_ONLY_KEYS = new Set(["intent_schema"]);

const isStringArray = (val) =>
  Array.isArray(val) && val.every((v) => typeof v === "string");
const isIntegerArray = (val) =>
  Array.isArray(val) && val.every((v) => Number.isInteger(v));
const isNonNegativeInt = (val) => Number.isInteger(val) && val >= 0;

const parseDate = (value) => {
  if (typeof value !== "string" || !DATE_RE.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const d = new Date(Date.UTC(year, month - 1, day));
  if (
    d.getUTCFullYear() !== year ||
    d.getUTCMonth() !== month - 1 ||
    d.getUTCDate() !== day
  ) {
    return null;
  }
  return d;
};

const diffDays = (from, to) =>
  Math.floor((to.getTime() - from.getTime()) / MS_PER_DAY);
const normalizePath = (path) => path.replaceAll("\\", "/");
const isInArchives = (path) =>
  normalizePath(path).split("/").includes("archives");
const isDraftPath = (path) => normalizePath(path).split("/").includes("draft");
const isQaPath = (path) => normalizePath(path).split("/").includes("qa");
const isIntentPath = (path) =>
  normalizePath(path).split("/").includes("intent");
const isInStandards = (path) =>
  normalizePath(path).split("/").includes("standards");

const walkMarkdown = async function* (dir) {
  for await (const entry of Deno.readDir(dir)) {
    const path = `${dir}/${entry.name}`;
    if (entry.isDirectory) {
      yield* walkMarkdown(path);
    } else if (entry.isFile && entry.name.endsWith(".md")) {
      yield path;
    }
  }
};

const stripInlineComment = (value) => {
  let quote = null;
  for (let i = 0; i < value.length; i += 1) {
    const ch = value[i];
    if ((ch === '"' || ch === "'") && value[i - 1] !== "\\") {
      quote = quote === ch ? null : quote ?? ch;
    }
    if (ch === "#" && quote === null) {
      return value.slice(0, i).trim();
    }
  }
  return value.trim();
};

const splitInlineArray = (value) => {
  const items = [];
  let current = "";
  let quote = null;
  for (const ch of value) {
    if ((ch === '"' || ch === "'") && current.at(-1) !== "\\") {
      quote = quote === ch ? null : quote ?? ch;
    }
    if (ch === "," && quote === null) {
      items.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  if (current.trim() !== "") items.push(current.trim());
  return items;
};

const parseScalar = (raw) => {
  const value = stripInlineComment(raw);
  if (value === "") return "";
  if (value === "[]") return [];
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (inner === "") return [];
    return splitInlineArray(inner).map(parseScalar);
  }
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  if (/^-?\d+$/.test(value)) return Number(value);
  return value;
};

const parseFrontMatter = (src) => {
  const lines = src.split(/\r?\n/);
  if (lines[0] !== "---") {
    return { attrs: null, error: "missing front matter" };
  }

  const end = lines.findIndex((line, index) => index > 0 && line === "---");
  if (end === -1) {
    return { attrs: null, error: "front matter is not closed" };
  }

  const attrs = {};
  for (let i = 1; i < end; i += 1) {
    const line = lines[i];
    if (line.trim() === "" || line.trimStart().startsWith("#")) continue;

    const match = line.match(/^([A-Za-z0-9_]+):(?:\s*(.*))?$/);
    if (!match) {
      return { attrs: null, error: `unsupported front matter line: ${line}` };
    }

    const [, key, rest = ""] = match;
    if (key in attrs) {
      return { attrs: null, error: `duplicate front matter field: ${key}` };
    }
    if (rest.trim() !== "") {
      attrs[key] = parseScalar(rest);
      continue;
    }

    const values = [];
    let cursor = i + 1;
    while (cursor < end) {
      const item = lines[cursor].match(/^\s+-\s+(.*)$/);
      if (!item) break;
      values.push(parseScalar(item[1]));
      cursor += 1;
    }
    if (values.length > 0) {
      attrs[key] = values;
      i = cursor - 1;
    } else {
      attrs[key] = "";
    }
  }

  return { attrs, error: null };
};

const loadFrontMatter = async (file) => {
  const src = await Deno.readTextFile(file);
  return parseFrontMatter(src);
};

const optionalValue = (value) => value === "" ? undefined : value;

const todayDate = () => parseDate(new Date().toISOString().slice(0, 10));

const parseArgs = (args) => {
  if (args.length === 0) return { roots: ["_docs"], fixtureMode: false };
  if (args[0] === "--fixture") {
    return { roots: args.slice(1), fixtureMode: true };
  }
  return { roots: args, fixtureMode: false };
};

const fileKind = async (path) => {
  try {
    const stat = await Deno.stat(path);
    if (stat.isFile) return "file";
    if (stat.isDirectory) return "directory";
  } catch (err) {
    if (err instanceof Deno.errors.NotFound) return null;
    throw err;
  }
  return null;
};

const collectMarkdown = async function* (roots) {
  for (const root of roots) {
    const kind = await fileKind(root);
    if (kind === "file") {
      if (root.endsWith(".md")) yield root;
    } else if (kind === "directory") {
      yield* walkMarkdown(root);
    }
  }
};

const allowedKeysFor = (file, fixtureMode) => {
  const allowed = new Set(COMMON_KEYS);
  if (isDraftPath(file)) {
    for (const key of DRAFT_ONLY_KEYS) allowed.add(key);
  }
  if (isQaPath(file)) {
    for (const key of QA_ONLY_KEYS) allowed.add(key);
  }
  if (isIntentPath(file)) {
    for (const key of INTENT_ONLY_KEYS) allowed.add(key);
  }
  if (fixtureMode) allowed.add("fixture_path");
  return allowed;
};

const report = (prefix, file, messages, logger) => {
  logger(`${prefix}: ${file}`);
  for (const msg of messages) logger(`  - ${msg}`);
};

const run = async () => {
  const errors = [];
  const warnings = [];
  const inScope = makeInScope(await loadScope());
  const { roots, fixtureMode } = parseArgs(Deno.args);

  if (roots.length === 0) {
    errors.push({
      file: "(args)",
      messages: ["--fixture requires at least one path"],
    });
  }

  for await (const file of collectMarkdown(roots)) {
    if (!fixtureMode && (isInArchives(file) || isInStandards(file))) continue;
    if (!inScope(file)) continue;

    const { attrs: data, error } = await loadFrontMatter(file);
    const fileErrors = [];
    const fileWarnings = [];
    if (error) {
      errors.push({ file, messages: [error] });
      continue;
    }
    const effectiveFile = fixtureMode && typeof data.fixture_path === "string"
      ? normalizePath(data.fixture_path)
      : file;
    if (isInArchives(effectiveFile)) continue;
    if (isInStandards(effectiveFile)) continue;

    for (const key of REQUIRED_KEYS) {
      if (!(key in data)) {
        fileErrors.push(`missing required field: ${key}`);
      }
    }
    for (const key of REQUIRED_SCALARS) {
      if (
        key in data &&
        (typeof data[key] !== "string" || data[key].trim() === "")
      ) {
        fileErrors.push(`required field must be a non-empty string: ${key}`);
      }
    }

    const status = data.status;
    const draftStatus = data.draft_status;
    if ("status" in data && !STATUS_VALUES.includes(status)) {
      fileErrors.push(`status must be one of ${STATUS_VALUES.join(", ")}`);
    }
    if ("draft_status" in data && !DRAFT_STATUS_VALUES.includes(draftStatus)) {
      fileErrors.push(
        `draft_status must be one of ${DRAFT_STATUS_VALUES.join(", ")}`,
      );
    }

    const createdAt = parseDate(data.created_at);
    const updatedAt = parseDate(data.updated_at);
    if (!createdAt) fileErrors.push("created_at must be YYYY-MM-DD");
    if (!updatedAt) fileErrors.push("updated_at must be YYYY-MM-DD");

    if (!isStringArray(data.references)) {
      fileErrors.push("references must be an array of strings (can be empty)");
    }
    if (!isIntegerArray(data.related_issues)) {
      fileErrors.push(
        "related_issues must be an array of integers (can be empty)",
      );
    }

    if (isQaPath(effectiveFile)) {
      if (!("qa_status" in data)) {
        fileErrors.push("missing required QA field: qa_status");
      } else if (!QA_STATUS_VALUES.includes(data.qa_status)) {
        fileErrors.push(
          `qa_status must be one of ${QA_STATUS_VALUES.join(", ")}`,
        );
      }

      if (!("risk" in data)) {
        fileErrors.push("missing required QA field: risk");
      } else if (!RISKS.includes(data.risk)) {
        fileErrors.push(`risk must be one of ${RISKS.join(", ")}`);
      }
    }
    if ("qa_schema" in data) {
      if (!isQaPath(effectiveFile)) {
        fileErrors.push("qa_schema is allowed only on QA documents");
      } else if (data.qa_schema !== 2) {
        fileErrors.push("qa_schema must be integer 2 when provided");
      }
    }
    if ("intent_schema" in data) {
      if (!isIntentPath(effectiveFile)) {
        fileErrors.push("intent_schema is allowed only on intent documents");
      } else if (data.intent_schema !== 2) {
        fileErrors.push("intent_schema must be integer 2 when provided");
      }
    }
    if (!isIntegerArray(data.related_prs)) {
      fileErrors.push(
        "related_prs must be an array of integers (can be empty)",
      );
    }

    const staleExemptUntilRaw = optionalValue(data.stale_exempt_until);
    const staleExemptReason = optionalValue(data.stale_exempt_reason);
    const staleExtensions = optionalValue(data.stale_extensions);

    if (staleExemptUntilRaw !== undefined) {
      const parsed = parseDate(staleExemptUntilRaw);
      if (!parsed) {
        fileErrors.push("stale_exempt_until must be YYYY-MM-DD when provided");
      } else if (updatedAt && parsed < updatedAt) {
        fileErrors.push(
          "stale_exempt_until must not be earlier than updated_at",
        );
      }
    }
    if (
      staleExemptReason !== undefined &&
      typeof staleExemptReason !== "string"
    ) {
      fileErrors.push("stale_exempt_reason must be a string when provided");
    }
    if (staleExtensions !== undefined && !isNonNegativeInt(staleExtensions)) {
      fileErrors.push(
        "stale_extensions must be a non-negative integer when provided",
      );
    }

    if (isDraftPath(effectiveFile) && status === "proposed" && updatedAt) {
      const today = todayDate();
      const daysSinceUpdate = diffDays(updatedAt, today);
      if (daysSinceUpdate > STALE_DAYS) {
        const parsedExempt = staleExemptUntilRaw
          ? parseDate(staleExemptUntilRaw)
          : null;
        if (!parsedExempt || parsedExempt < today) {
          fileErrors.push(
            `draft is stale (${daysSinceUpdate} days since updated_at) without valid stale_exempt_until`,
          );
        }
        if (
          staleExemptUntilRaw &&
          (!staleExemptReason || staleExemptReason.trim() === "")
        ) {
          fileErrors.push(
            "stale_exempt_reason is required when stale_exempt_until is set",
          );
        }
      } else if (staleExemptUntilRaw) {
        fileWarnings.push(
          "stale_exempt_until is set but draft is not stale yet (<=30 days)",
        );
      }
    }

    if (isDraftPath(effectiveFile) && status && status !== "proposed") {
      fileWarnings.push(
        `draft has status "${status}" (consider elevating to plan/intent or align status)`,
      );
    }

    const allowedKeys = allowedKeysFor(effectiveFile, fixtureMode);
    for (const key of Object.keys(data)) {
      if (!allowedKeys.has(key)) fileErrors.push(`unknown field: ${key}`);
    }

    if (fileErrors.length) errors.push({ file, messages: fileErrors });
    if (fileWarnings.length) warnings.push({ file, messages: fileWarnings });
  }

  for (const { file, messages } of warnings) {
    report("WARN", file, messages, console.warn);
  }

  if (errors.length) {
    for (const { file, messages } of errors) {
      report("ERROR", file, messages, console.error);
    }
    Deno.exit(1);
  }
};

run().catch((err) => {
  console.error(err);
  Deno.exit(1);
});
