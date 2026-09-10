import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const DEFAULT_ROOT = fileURLToPath(new URL("../", import.meta.url));
const READMES = [
  "README.md",
  "docs/i18n/README.ko.md",
  "docs/i18n/README.ja.md",
  "docs/i18n/README.ru.md",
];
const INDEXES = ["docs/README.md", "docs/i18n/INDEX.ko.md"];
const EXCLUDED = new Set([
  "node_modules",
  "vendor",
  ".venv",
  "venv",
  "dist",
  "build",
  ".git",
]);

export function koreanCounterpart(file) {
  if (file === "docs/README.md") return "docs/i18n/INDEX.ko.md";
  if (file.toLowerCase() === ".github/pull_request_template.md") {
    return "docs/i18n/PULL_REQUEST_TEMPLATE.ko.md";
  }
  return `docs/i18n/${path.posix.basename(file).replace(/\.md$/i, "")}.ko.md`;
}

function stripHtmlTagsSafely(value) {
  let previous;
  let current = value;
  do {
    previous = current;
    current = current.replace(/<[^>]*>/g, "");
  } while (current !== previous);
  return current;
}

function parseMarkdown(source, file, issues) {
  const prose = [];
  const blocks = [];
  let fence;
  for (const [index, line] of source.split(/\r?\n/).entries()) {
    const match = /^(\s*)(`{3,}|~{3,})(.*)$/.exec(line);
    if (!fence && match) {
      fence = {
        char: match[2][0],
        length: match[2].length,
        indent: match[1].length,
        language: match[3].trim(),
        start: index + 1,
        lines: [],
      };
      prose.push("");
    } else if (fence) {
      if (
        match &&
        match[2][0] === fence.char &&
        match[2].length >= fence.length &&
        !match[3].trim()
      ) {
        blocks.push({ ...fence, code: fence.lines.join("\n") + "\n" });
        fence = undefined;
      } else {
        fence.lines.push(
          line.startsWith(" ".repeat(fence.indent))
            ? line.slice(fence.indent)
            : line,
        );
      }
      prose.push("");
    } else {
      prose.push(line);
    }
  }
  if (fence) issues.push(`${file}:${fence.start}: unclosed code fence`);
  const text = prose
    .join("\n")
    .replace(/<!--[\s\S]*?-->/g, (comment) => comment.replace(/[^\n]/g, " "));
  const headings = new Set();
  const repeated = new Map();
  // GitHub-style ATX heading anchors for the source syntax used in these guides.
  for (const heading of text.matchAll(/^#{1,6}\s+(.+?)\s*#*\s*$/gm)) {
    const slug = stripHtmlTagsSafely(heading[1])
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, "")
      .replace(/\s/g, "-");
    const duplicates = repeated.get(slug) || 0;
    repeated.set(slug, duplicates + 1);
    headings.add(duplicates ? `${slug}-${duplicates}` : slug);
  }
  for (const anchor of text.matchAll(/\b(?:id|name)=["']([^"']+)["']/g))
    headings.add(anchor[1]);
  const todos = [...text.matchAll(/^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]/gm)].map(
    (match) => match[1].toLowerCase(),
  );
  const commands = [
    ...new Set(
      [
        ...text.matchAll(
          /`((?:authzest|codex|pipx|npm|node|git|gh|ruff|pytest|uvicorn|shasum|chmod|python(?:3(?:\.12)?)?|py)\s[^`\n]+)`/g,
        ),
      ].map((match) => match[1].trim()),
    ),
  ].sort();
  return { text, headings, blocks, todos, commands, destinations: new Set() };
}

function localTarget(from, destination) {
  let value = destination.replace(/&amp;/g, "&");
  const repositoryUrl =
    /^https:\/\/github\.com\/casing1\/authzest\/(?:blob|tree)\/main\//;
  if (repositoryUrl.test(value)) value = "/" + value.replace(repositoryUrl, "");
  else if (/^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith("//"))
    return undefined;
  const hash = value.indexOf("#");
  const fragment = hash >= 0 ? decodeURIComponent(value.slice(hash + 1)) : "";
  const beforeHash = hash >= 0 ? value.slice(0, hash) : value;
  const target = decodeURIComponent(beforeHash.split("?")[0]);
  const relative = target
    ? path.posix.normalize(
        target.startsWith("/")
          ? target.slice(1)
          : path.posix.join(path.posix.dirname(from), target),
      )
    : from;
  return { relative, fragment };
}

function codePayloads(document, readme = false) {
  return document.blocks.map((block) => ({
    language: block.language,
    // README structure diagrams may translate comments; executable examples must match exactly.
    code:
      readme && block.language === "text"
        ? block.code
            .split("\n")
            .map((line) => line.replace(/\s+#.*$/, "").trimEnd())
            .join("\n")
        : block.code,
  }));
}

const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);

export function checkDocs(root = DEFAULT_ROOT, options = {}) {
  root = path.resolve(root);
  const listed =
    options.files ??
    execFileSync(
      "git",
      ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
      { cwd: root, encoding: "utf8" },
    )
      .split("\0")
      .filter(Boolean);
  const tracked = new Set(
    listed.filter(
      (file) => !file.split("/").some((part) => EXCLUDED.has(part)),
    ),
  );
  const files = [...tracked].filter((file) => /\.md$/i.test(file)).sort();
  const issues = [];
  const notes = [];
  const counts = {
    markdown: files.length,
    links: 0,
    images: 0,
    fragments: 0,
    remote: 0,
    pairs: 0,
    bash: 0,
    bashSkipped: 0,
  };
  const documents = new Map();
  for (const file of files) {
    try {
      documents.set(
        file,
        parseMarkdown(
          fs.readFileSync(path.join(root, file), "utf8"),
          file,
          issues,
        ),
      );
    } catch (error) {
      issues.push(`${file}: cannot read document: ${error.message}`);
    }
  }

  function checkLink(from, destination, offset, image) {
    const document = documents.get(from);
    const line = document.text.slice(0, offset).split("\n").length;
    let target;
    try {
      target = localTarget(from, destination);
    } catch (error) {
      issues.push(
        `${from}:${line}: invalid link ${destination}: ${error.message}`,
      );
      return;
    }
    if (!target) {
      counts.remote += 1;
      return;
    }
    counts.links += 1;
    if (image) counts.images += 1;
    document.destinations.add(target.relative);
    if (target.relative === ".." || target.relative.startsWith("../")) {
      issues.push(`${from}:${line}: link escapes repository: ${destination}`);
      return;
    }
    const absolute = path.join(root, target.relative);
    if (!fs.existsSync(absolute)) {
      issues.push(`${from}:${line}: missing link/image target: ${destination}`);
      return;
    }
    if (fs.statSync(absolute).isFile() && !tracked.has(target.relative)) {
      issues.push(
        `${from}:${line}: wrong-case or excluded link target: ${destination}`,
      );
    }
    if (target.fragment && documents.has(target.relative)) {
      counts.fragments += 1;
      if (!documents.get(target.relative).headings.has(target.fragment)) {
        issues.push(
          `${from}:${line}: missing heading #${target.fragment} in ${target.relative}`,
        );
      }
    }
  }

  let bashUnavailable = false;
  for (const [file, document] of documents) {
    for (const link of document.text.matchAll(
      /(!?)\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+["'][^\n]*?["'])?\s*\)/g,
    )) {
      checkLink(file, link[2] || link[3], link.index, Boolean(link[1]));
    }
    for (const link of document.text.matchAll(
      /<(a|img)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["'][^>]*>/g,
    )) {
      checkLink(file, link[2], link.index, link[1] === "img");
    }
    for (const link of document.text.matchAll(
      /^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|([^\s]+))/gm,
    )) {
      checkLink(file, link[1] || link[2], link.index, false);
    }
    for (const block of document.blocks.filter((block) =>
      /^(bash|sh|shell)$/.test(block.language),
    )) {
      if (bashUnavailable) {
        counts.bashSkipped += 1;
        continue;
      }
      // Parse only: never execute documentation examples, installers, or publish commands.
      const result = spawnSync("bash", ["-n"], {
        input: block.code,
        encoding: "utf8",
      });
      if (result.error?.code === "ENOENT") {
        bashUnavailable = true;
        counts.bashSkipped += 1;
        notes.push("Bash is unavailable; shell syntax checks were skipped.");
      } else {
        counts.bash += 1;
        if (result.status !== 0)
          issues.push(
            `${file}:${block.start}: Bash syntax: ${result.error?.message || result.stderr.trim()}`,
          );
      }
    }
  }

  for (const required of [...READMES, ...INDEXES]) {
    if (!documents.has(required))
      issues.push(`Missing required document: ${required}`);
  }
  const sources = files.filter((file) => !file.startsWith("docs/i18n/"));
  for (const english of sources) {
    const korean = koreanCounterpart(english);
    if (!documents.has(korean)) {
      issues.push(`${english}: missing Korean counterpart ${korean}`);
      continue;
    }
    if (!documents.has(english)) continue;
    counts.pairs += 1;
    const source = documents.get(english);
    const translation = documents.get(korean);
    for (const [from, to] of [
      [english, korean],
      [korean, english],
    ]) {
      if (!documents.get(from).destinations.has(to))
        issues.push(`${from}: missing reciprocal language link to ${to}`);
    }
    if (
      !same(
        codePayloads(source, english === "README.md"),
        codePayloads(translation, english === "README.md"),
      )
    ) {
      issues.push(`${english} / ${korean}: code blocks differ`);
    }
    if (!same(source.commands, translation.commands))
      issues.push(`${english} / ${korean}: inline command parity differs`);
    if (!same(source.todos, translation.todos))
      issues.push(`${english} / ${korean}: TODO completion sequence differs`);
    for (const index of INDEXES) {
      if (!documents.has(index)) continue;
      for (const guide of [english, korean]) {
        if (guide !== index && !documents.get(index).destinations.has(guide))
          issues.push(`${index}: missing guide ${guide}`);
      }
    }
  }
  for (const korean of files.filter((file) =>
    /^docs\/i18n\/.*\.ko\.md$/.test(file),
  )) {
    if (
      sources.filter((file) => koreanCounterpart(file) === korean).length !== 1
    ) {
      issues.push(`${korean}: expected exactly one English source`);
    }
  }
  const englishReadme = documents.get("README.md");
  if (englishReadme) {
    for (const translated of READMES.slice(1)) {
      const document = documents.get(translated);
      if (!document) continue;
      if (
        !same(codePayloads(englishReadme, true), codePayloads(document, true))
      ) {
        issues.push(`README command/structure parity differs: ${translated}`);
      }
      if (!same(englishReadme.commands, document.commands))
        issues.push(`README inline command parity differs: ${translated}`);
    }
  }
  for (const from of READMES) {
    if (!documents.has(from)) continue;
    for (const to of READMES.filter((candidate) => candidate !== from)) {
      if (!documents.get(from).destinations.has(to))
        issues.push(`${from}: missing README language link to ${to}`);
    }
  }
  return { counts, notes, issues };
}

function isDirectInvocation() {
  if (!process.argv[1]) return false;
  try {
    return (
      fs.realpathSync(process.argv[1]) ===
      fs.realpathSync(fileURLToPath(import.meta.url))
    );
  } catch {
    // Importing this helper from a process with a non-file argv must stay side-effect free.
    return false;
  }
}

if (isDirectInvocation()) {
  try {
    const report = checkDocs(process.argv[2] || DEFAULT_ROOT);
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    process.exitCode = report.issues.length ? 1 : 0;
  } catch (error) {
    process.stderr.write(`Documentation check failed: ${error.message}\n`);
    process.exitCode = 1;
  }
}
