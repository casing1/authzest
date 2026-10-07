import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const DEFAULT_ROOT = fileURLToPath(new URL("../", import.meta.url));
const MAX_CONFIG_BYTES = 4096;
const MAX_ENTRIES = 10000;
const MAX_DEPTH = 32;
const SECTIONS = new Set(["*", "*.py", "Makefile"]);
const VALUES = {
  charset: new Set(["utf-8"]),
  end_of_line: new Set(["lf", "crlf", "cr"]),
  indent_style: new Set(["space", "tab"]),
  insert_final_newline: new Set(["true", "false"]),
  trim_trailing_whitespace: new Set(["true", "false"]),
};

function refuse(message) {
  throw new Error(message);
}

// Validate data only, before importing or starting the bundled formatter.
export function validateEditorConfig(text) {
  if (
    typeof text !== "string" ||
    Buffer.byteLength(text, "utf8") > MAX_CONFIG_BYTES ||
    /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\ufeff]/u.test(text)
  ) {
    refuse(
      "EditorConfig must be bounded UTF-8 text without control characters",
    );
  }
  const sections = new Set();
  let properties = new Set();
  let section;
  let rootSeen = false;
  for (const raw of text.split(/\r\n|\n|\r/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith(";")) continue;
    if (line.startsWith("[")) {
      const match = /^\[([^\]]+)\]$/.exec(line);
      if (!match || !SECTIONS.has(match[1]) || sections.has(match[1])) {
        refuse(
          "EditorConfig section needs a reviewed pattern; duplicates are forbidden",
        );
      }
      section = match[1];
      sections.add(section);
      properties = new Set();
      continue;
    }
    const match = /^([a-z_]+)\s*=\s*(.*?)$/.exec(line);
    if (!match) refuse("Malformed EditorConfig property");
    const [, key, value] = match;
    if (!section) {
      if (key !== "root" || value !== "true" || rootSeen) {
        refuse("EditorConfig requires exactly one global root = true");
      }
      rootSeen = true;
      continue;
    }
    if (properties.has(key)) refuse("Duplicate EditorConfig property");
    properties.add(key);
    const valid =
      key === "indent_size"
        ? value === "tab" || /^(?:[1-9]|1[0-6])$/.test(value)
        : VALUES[key]?.has(value);
    if (!valid) refuse("EditorConfig property/value needs review");
  }
  if (!rootSeen || !sections.has("*")) {
    refuse("EditorConfig requires global root = true and the [*] section");
  }
}

function regularFile(file) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.nlink !== 1)
    refuse("Expected a non-linked regular file");
  return stat;
}

function boundedText(file, limit) {
  const stat = regularFile(file);
  if (stat.size > limit) refuse("Configuration exceeds its byte limit");
  const fd = fs.openSync(
    file,
    fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0),
  );
  try {
    const opened = fs.fstatSync(fd);
    if (
      !opened.isFile() ||
      opened.nlink !== 1 ||
      opened.size > limit ||
      opened.dev !== stat.dev ||
      opened.ino !== stat.ino
    )
      refuse("Configuration changed during preflight");
    const bytes = Buffer.alloc(limit + 1);
    let length = 0;
    while (length <= limit) {
      const read = fs.readSync(fd, bytes, length, bytes.length - length, null);
      if (!read) break;
      length += read;
    }
    if (length > limit) refuse("Configuration exceeds its byte limit");
    return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
      bytes.subarray(0, length),
    );
  } finally {
    fs.closeSync(fd);
  }
}

function directoryEntries(directory, budget) {
  if (!fs.lstatSync(directory).isDirectory())
    refuse("Expected a non-symlink directory");
  const entries = [];
  const handle = fs.opendirSync(directory);
  try {
    for (let entry; (entry = handle.readSync());) {
      if (++budget.count > MAX_ENTRIES)
        refuse("Formatting discovery exceeds its entry limit");
      entries.push(entry);
    }
  } finally {
    handle.closeSync();
  }
  return entries;
}

function checkConfigNames(directory, root, entries) {
  for (const entry of entries) {
    if (entry.name.toLowerCase() !== ".editorconfig") continue;
    if (directory !== root || entry.name !== ".editorconfig") {
      refuse("Nested or case-aliased EditorConfig needs review");
    }
  }
}

function walkFrontend(directory, root, budget, depth = 0) {
  if (depth > MAX_DEPTH) refuse("Formatting discovery exceeds its depth limit");
  const entries = directoryEntries(directory, budget);
  checkConfigNames(directory, root, entries);
  for (const entry of entries) {
    // These exact root exclusions are checked against .prettierignore below.
    if (depth === 0 && ["node_modules", "dist"].includes(entry.name)) continue;
    const file = path.join(directory, entry.name);
    const stat = fs.lstatSync(file);
    if (stat.isSymbolicLink())
      refuse("Frontend formatting does not follow symlinks");
    if (stat.isDirectory()) walkFrontend(file, root, budget, depth + 1);
    else if (!stat.isFile())
      refuse("Frontend formatting requires ordinary files");
  }
}

export function preflight(inputRoot, mode) {
  if (!["frontend", "markdown"].includes(mode))
    refuse("Unknown formatting scope");
  const root = fs.realpathSync(inputRoot);
  if (/[{}*?\[\],]/.test(root))
    refuse("Checkout path must not contain glob metacharacters");
  const marker = fs.lstatSync(path.join(root, ".git"));
  if (!marker.isDirectory() && !marker.isFile())
    refuse("Expected a Git checkout marker");
  const budget = { count: 0 };
  checkConfigNames(root, root, directoryEntries(root, budget));
  validateEditorConfig(
    boundedText(path.join(root, ".editorconfig"), MAX_CONFIG_BYTES),
  );
  if (!fs.lstatSync(path.join(root, "scripts")).isDirectory())
    refuse("Expected scripts directory");
  const options = JSON.parse(
    boundedText(path.join(root, "scripts/prettier-options.json"), 64),
  );
  if (
    !options ||
    Array.isArray(options) ||
    typeof options !== "object" ||
    Object.keys(options).length
  ) {
    refuse("Formatter options must remain the reviewed empty JSON object");
  }
  const frontend = path.join(root, "frontend");
  if (!fs.lstatSync(frontend).isDirectory())
    refuse("Expected frontend directory");
  const ignoreText = boundedText(path.join(frontend, ".prettierignore"), 1024);
  if (/\r(?!\n)/u.test(ignoreText))
    refuse("Frontend ignore file requires LF or CRLF line endings");
  // Preserve raw patterns: leading whitespace changes Prettier's ignore meaning.
  const ignores = ignoreText
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"));
  if (
    ignores.length !== 3 ||
    [...new Set(ignores)].sort().join("\n") !==
      "dist\nnode_modules\npackage-lock.json"
  ) {
    refuse("Frontend ignore discovery changes require guard review");
  }
  if (mode === "frontend") {
    walkFrontend(frontend, root, budget);
    return { root, cwd: frontend, files: ["."] };
  }
  const files = execFileSync("git", ["ls-files", "-z", "--", "*.md"], {
    cwd: root,
    encoding: "utf8",
    timeout: 5000,
    maxBuffer: 1024 * 1024,
  })
    .split("\0")
    .filter(Boolean);
  if (files.length > MAX_ENTRIES) refuse("Too many tracked Markdown targets");
  const checked = new Set([root]);
  for (const file of files) {
    const parts = file.split("/");
    if (
      !file.endsWith(".md") ||
      /[\u0000-\u001f\u007f\\]/u.test(file) ||
      parts.length > MAX_DEPTH ||
      parts.some((part) => !part || part === "." || part === "..") ||
      path.isAbsolute(file)
    )
      refuse("Invalid tracked Markdown path");
    let directory = root;
    for (const part of parts.slice(0, -1)) {
      directory = path.join(directory, part);
      if (!checked.has(directory)) {
        checkConfigNames(directory, root, directoryEntries(directory, budget));
        checked.add(directory);
      }
    }
    regularFile(path.join(root, file));
  }
  return { root, cwd: root, files };
}

export function runFormatter({
  root = DEFAULT_ROOT,
  mode,
  operation,
  spawn = spawnSync,
  env = process.env,
}) {
  if (!["--check", "--write"].includes(operation))
    refuse("Expected --check or --write without extra arguments");
  const plan = preflight(root, mode);
  if (!plan.files.length) return 0;
  const childEnv = Object.fromEntries(
    Object.entries(env).filter(
      ([key]) =>
        !["PRETTIER_EXPERIMENTAL_CLI", "NODE_OPTIONS", "NODE_PATH"].includes(
          key.toUpperCase(),
        ),
    ),
  );
  const cli = path.join(
    plan.root,
    "frontend/node_modules/prettier/bin/prettier.cjs",
  );
  const result = spawn(
    process.execPath,
    [
      cli,
      "--editorconfig",
      "--config",
      path.join(plan.root, "scripts/prettier-options.json"),
      operation,
      "--",
      ...plan.files.map((file) => (mode === "markdown" ? `./${file}` : file)),
    ],
    {
      cwd: plan.cwd,
      env: childEnv,
      shell: false,
      stdio: "inherit",
      timeout: 120000,
      killSignal: "SIGKILL",
    },
  );
  if (
    result.error ||
    result.signal ||
    result.status === null ||
    result.status === undefined
  ) {
    refuse("Formatter failed to complete within the bounded child execution");
  }
  return result.status;
}

function isDirectInvocation() {
  try {
    return (
      fs.realpathSync(process.argv[1]) ===
      fs.realpathSync(fileURLToPath(import.meta.url))
    );
  } catch {
    return false;
  }
}

if (isDirectInvocation()) {
  try {
    if (process.argv.length !== 4)
      refuse(
        "Usage: node scripts/format.mjs <frontend|markdown> <--check|--write>",
      );
    process.exitCode = runFormatter({
      mode: process.argv[2],
      operation: process.argv[3],
    });
  } catch (error) {
    console.error(`[format] Refusing formatting: ${error.message}`);
    process.exitCode = 2;
  }
}
