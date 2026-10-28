import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontend = fileURLToPath(new URL("../frontend/", import.meta.url));
const lock = JSON.parse(
  fs.readFileSync(path.join(frontend, "package-lock.json"), "utf8"),
);
const frontendRequire = createRequire(path.join(frontend, "package.json"));
const viteRequire = createRequire(frontendRequire.resolve("vite"));
const postcssRequire = createRequire(viteRequire.resolve("postcss"));
const sourceMap = postcssRequire("source-map-js");
const postcss = viteRequire("postcss");
const hooksRequire = createRequire(
  frontendRequire.resolve("eslint-plugin-react-hooks"),
);
const errorRequire = createRequire(hooksRequire.resolve("zod-validation-error/v4"));
const { z } = hooksRequire("zod/v4");
const { fromZodError } = hooksRequire("zod-validation-error/v4");

// GHSA-mrhx-c7xc-m3w5: small collection checks, never a resource-exhaustion test.
// The upstream fix covers leading upper bounds; it does not bound Hooks options.
test("every locked and installed Zod copy uses the reviewed compatible release", () => {
  const copies = Object.entries(lock.packages).filter(([location]) =>
    location.endsWith("node_modules/zod"),
  );
  assert.ok(copies.length > 0);
  for (const [location, metadata] of copies) {
    assert.equal(metadata.version, "4.6.7", location);
    const installed = JSON.parse(
      fs.readFileSync(path.join(frontend, location, "package.json"), "utf8"),
    );
    assert.equal(installed.name, "zod", location);
    assert.equal(installed.version, metadata.version, location);
  }
});

test("Hooks and its error formatter resolve checked Zod v4 entrypoints", () => {
  const checked = Object.keys(lock.packages)
    .filter((location) => location.endsWith("node_modules/zod"))
    .map((location) => fs.realpathSync(path.join(frontend, location)));
  for (const [consumer, entrypoint, relative] of [
    [hooksRequire, "zod/v4", "v4/index.cjs"],
    [errorRequire, "zod/v4/core", "v4/core/index.cjs"],
  ]) {
    const root = path.dirname(
      fs.realpathSync(consumer.resolve("zod/package.json")),
    );
    assert.ok(checked.includes(root));
    assert.equal(
      fs.realpathSync(consumer.resolve(entrypoint)),
      path.join(root, relative),
    );
  }
});

for (const [name, makeSchema, oversized, ordinary, ordinaryVisits] of [
  ["array max", (item) => z.array(item).max(1), [0, 1], ["ok"], 1],
  ["array length", (item) => z.array(item).length(1), [0, 1], ["ok"], 1],
  ["set max", (item) => z.set(item).max(1), new Set([0, 1]), new Set(["ok"]), 1],
  ["set size", (item) => z.set(item).size(1), new Set([0, 1]), new Set(["ok"]), 1],
  [
    "map max",
    (item) => z.map(item, item).max(1),
    new Map([[0, 1], [2, 3]]),
    new Map([["key", "ok"]]),
    2,
  ],
  [
    "map size",
    (item) => z.map(item, item).size(1),
    new Map([[0, 1], [2, 3]]),
    new Map([["key", "ok"]]),
    2,
  ],
]) {
  test(`Zod ${name} rejects two entries before walking them and preserves one valid entry`, () => {
    let visits = 0;
    let laterChecks = 0;
    const item = z.any().superRefine((value, context) => {
      visits++;
      if (typeof value !== "string") {
        context.addIssue({ code: "custom", message: "Expected a string" });
      }
    });
    const schema = makeSchema(item).refine(() => {
      laterChecks++;
      return true;
    });
    const rejected = schema.safeParse(oversized);
    assert.equal(rejected.success, false);
    assert.equal(
      visits,
      0,
      "elements must not be visited before an upper-bound rejection",
    );
    assert.equal(laterChecks, 0, "later checks must not see unparsed elements");
    assert.equal(rejected.error.issues.length, 1);
    assert.equal(rejected.error.issues[0].code, "too_big");
    assert.equal(rejected.error.issues[0].maximum, 1);
    assert.deepEqual(schema.parse(ordinary), ordinary);
    assert.equal(visits, ordinaryVisits);
    assert.equal(laterChecks, 1);
  });
}

test("Zod preserves element errors within bounds and unbounded collection semantics", () => {
  const within = z.array(z.string()).max(2).safeParse([0]);
  assert.equal(within.success, false);
  assert.deepEqual(
    within.error.issues.map(({ code, path }) => ({ code, path })),
    [{ code: "invalid_type", path: [0] }],
  );
  const unbounded = z.array(z.string()).safeParse([0, 1]);
  assert.equal(unbounded.success, false);
  assert.equal(unbounded.error.issues.length, 2);
  const minimumOnly = z.array(z.string()).min(1).safeParse([0, 1]);
  assert.equal(minimumOnly.success, false);
  assert.equal(minimumOnly.error.issues.length, 2);
  // A preceding overwrite may shrink a collection: the later bound cannot move first.
  assert.deepEqual(
    z.array(z.string())
      .overwrite((items) => items.slice(0, 1))
      .max(1)
      .parse(["a", "b"]),
    ["a"],
  );
});

test("Zod's shipped bounded-union diagnostic retains nested size and path information", () => {
  const schema = z.object({
    values: z.union([z.array(z.string()).max(1), z.string()]),
  });
  assert.deepEqual(schema.parse({ values: ["ok"] }), { values: ["ok"] });
  const bounded = schema.safeParse({ values: ["a", "b"] });
  assert.equal(bounded.success, false);
  // 4.6.7 changes 4.5.4's top-level too_big to invalid_union. Upstream #6662
  // restores that precision but is not shipped here. Hooks' inspected collection
  // schemas are unbounded; this is a library behavior record, not their contract.
  const issue = bounded.error.issues[0];
  assert.equal(issue.code, "invalid_union");
  assert.deepEqual(issue.path, ["values"]);
  assert.equal(issue.errors.length, 2);
  assert.equal(issue.errors[0].length, 1);
  assert.equal(issue.errors[0][0].code, "too_big");
  assert.equal(issue.errors[0][0].maximum, 1);
  assert.equal(issue.errors[1][0].code, "invalid_type");
  assert.match(fromZodError(bounded.error).message, /Too big:.*at "values"/);
  const mismatched = schema.safeParse({ values: 7 });
  assert.equal(mismatched.success, false);
  assert.equal(mismatched.error.issues[0].code, "invalid_union");
  assert.equal(mismatched.error.issues[0].errors.length, 2);
  assert.match(fromZodError(mismatched.error).message, /values/);
});

test("Hooks lint accepts normal components and reports hook and effect violations", () => {
  const { Linter } = frontendRequire("eslint");
  const hooks = frontendRequire("eslint-plugin-react-hooks");
  const config = [
    {
      plugins: { "react-hooks": hooks },
      rules: hooks.configs.recommended.rules,
      languageOptions: { ecmaVersion: 2022, sourceType: "module" },
    },
  ];
  const linter = new Linter();
  const good = 'import { useState } from "react"; export function Counter() {\n' +
    'const [value] = useState(0); return value; }';
  assert.deepEqual(linter.verify(good, config), []);
  const bad = 'import { useState } from "react"; export function Counter({enabled}) {\n' +
    'if (enabled) { useState(0); } return null; }';
  assert.ok(linter.verify(bad, config).some(
    ({ ruleId }) => ruleId === "react-hooks/rules-of-hooks",
  ));
  const effect = 'import { useEffect } from "react"; export function Counter({value}) {\n' +
    'useEffect(() => { console.log(value); }, []); return null; }';
  assert.ok(linter.verify(effect, config).some(
    ({ ruleId, message }) => ruleId === "react-hooks/exhaustive-deps" &&
      message.includes("missing dependency: 'value'"),
  ));
});

test("Hooks retains small compiler-option validation through config and inline comments", () => {
  const { Linter } = frontendRequire("eslint");
  const hooks = frontendRequire("eslint-plugin-react-hooks");
  const source = "export function Counter() { return 1; }";
  for (const inline of [false, true]) {
    const verify = (options) => {
      const config = [{
        plugins: { "react-hooks": hooks },
        rules: {
          "react-hooks/config": inline ? "error" : ["error", options],
        },
        languageOptions: { ecmaVersion: 2022, sourceType: "module" },
      }];
      const comment = inline
        ? `/* eslint react-hooks/config: ["error", ${JSON.stringify(options)}] */\n`
        : "";
      return new Linter().verify(comment + source, config);
    };
    assert.deepEqual(verify({ customOptOutDirectives: ["use skip"] }), []);
    assert.deepEqual(verify({ target: "19" }), []);
    // The installed Hooks consumer throws these same errors on the old lock.
    // Small invalid values check compatibility, not availability under load.
    assert.throws(
      () => verify({ customOptOutDirectives: [7] }),
      /Could not parse custom opt out directives\..*expected string, received number at index 0/s,
    );
    assert.throws(
      () => verify({ target: 7 }),
      /Not a valid target\..*expected "17".*expected "18".*expected "19".*expected object/s,
    );
    assert.throws(
      () => verify({ environment: { customMacros: [7] } }),
      /Error in validating environment config\..*"customMacros",\s+0.*expected string, received number/s,
    );
  }
});

// These upstream advisories affect Vite's bundled launch-editor, not a separately
// overridable package: GHSA-698v-4r3x-3vcv, GHSA-587h-7wmj-h5pm, GHSA-r825-w8mm-5pxw.
// This checks dependency provenance, not native Windows/WSL exploit behavior.
test("the manifest and every locked and installed Vite copy use the reviewed patched release", () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(frontend, "package.json"), "utf8"),
  );
  assert.equal(manifest.devDependencies.vite, "8.2.4");
  assert.equal(lock.packages[""].devDependencies.vite, "8.2.4");
  const copies = Object.entries(lock.packages).filter(([location]) =>
    location.endsWith("node_modules/vite"),
  );
  assert.ok(copies.length > 0, "Vite must be present in the toolchain");
  for (const [location, metadata] of copies) {
    assert.equal(metadata.version, "8.2.4", location);
    const installed = JSON.parse(
      fs.readFileSync(path.join(frontend, location, "package.json"), "utf8"),
    );
    assert.equal(installed.name, "vite", location);
    assert.equal(installed.version, metadata.version, location);
  }
});

test("the frontend resolves a checked Vite copy", () => {
  const manifest = fs.realpathSync(frontendRequire.resolve("vite/package.json"));
  const checked = Object.keys(lock.packages)
    .filter((location) => location.endsWith("node_modules/vite"))
    .map((location) =>
      fs.realpathSync(path.join(frontend, location, "package.json")),
    );
  assert.ok(checked.includes(manifest), "Frontend must not use an unchecked Vite");
  assert.equal(JSON.parse(fs.readFileSync(manifest, "utf8")).version, "8.2.4");
});

test("each checked Vite bundle identifies the patched editor and middleware", () => {
  for (const location of Object.keys(lock.packages).filter((entry) =>
    entry.endsWith("node_modules/vite"),
  )) {
    // This release bundles these packages instead of resolving a lock override.
    // Keep this provenance check tied to the exact Vite release above.
    const bundle = fs.readFileSync(
      path.join(frontend, location, "dist/node/chunks/node.js"),
      "utf8",
    );
    const versions = [
      ...bundle.matchAll(/\/launch-editor(?:-middleware)?@(\d+\.\d+\.\d+)\//g),
    ].map((match) => match[1]);
    assert.ok(versions.length > 0, location);
    assert.deepEqual([...new Set(versions)], ["2.14.2"], location);
    assert.ok(
      bundle.includes("/launch-editor@2.14.2/node_modules/launch-editor/index.js"),
      location,
    );
    assert.ok(
      bundle.includes(
        "/launch-editor-middleware@2.14.2/node_modules/launch-editor-middleware/index.js",
      ),
      location,
    );
  }
});

// GHSA-68fv-2mgg-jv7q: pin the reviewed release, including any nested copies.
// npm ci checks archive integrity; these tests do not reproduce resource exhaustion.
test("every locked and installed source-map-js copy uses the reviewed patched release", () => {
  const copies = Object.entries(lock.packages).filter(([location]) =>
    location.endsWith("node_modules/source-map-js"),
  );
  assert.ok(
    copies.length > 0,
    "source-map-js must be present in the toolchain",
  );
  for (const [location, metadata] of copies) {
    assert.equal(metadata.version, "1.2.2", location);
    const installed = JSON.parse(
      fs.readFileSync(path.join(frontend, location, "package.json"), "utf8"),
    );
    assert.equal(installed.name, "source-map-js", location);
    assert.equal(installed.version, metadata.version, location);
  }
});

test("Vite's PostCSS resolves a checked source-map-js copy", () => {
  const manifest = fs.realpathSync(
    postcssRequire.resolve("source-map-js/package.json"),
  );
  const checked = Object.keys(lock.packages)
    .filter((location) => location.endsWith("node_modules/source-map-js"))
    .map((location) =>
      fs.realpathSync(path.join(frontend, location, "package.json")),
    );
  assert.ok(
    checked.includes(manifest),
    "PostCSS must not use an unchecked copy",
  );
  assert.equal(JSON.parse(fs.readFileSync(manifest, "utf8")).version, "1.2.2");
});

test("ordinary flat source maps retain names, content and original positions", () => {
  const generator = new sourceMap.SourceMapGenerator({ file: "output.js" });
  generator.addMapping({
    generated: { line: 1, column: 0 },
    original: { line: 2, column: 3 },
    source: "input.js",
    name: "value",
  });
  generator.setSourceContent("input.js", "// input\n   value;\n");
  const consumer = new sourceMap.SourceMapConsumer(generator.toString());
  assert.deepEqual(consumer.originalPositionFor({ line: 1, column: 0 }), {
    source: "input.js",
    line: 2,
    column: 3,
    name: "value",
  });
  assert.equal(consumer.sourceContentFor("input.js"), "// input\n   value;\n");
  const roundTrip = new sourceMap.SourceMapConsumer(
    sourceMap.SourceMapGenerator.fromSourceMap(consumer).toString(),
  );
  assert.deepEqual(
    roundTrip.originalPositionFor({ line: 1, column: 0 }),
    consumer.originalPositionFor({ line: 1, column: 0 }),
  );
});

test("small legitimate indexed maps preserve section positions and generated code", () => {
  const leaf = (source, content) => ({
    version: 3,
    sources: [source],
    sourcesContent: [content],
    names: [],
    mappings: "AAAA",
  });
  const consumer = new sourceMap.SourceMapConsumer({
    version: 3,
    sections: [
      { offset: { line: 0, column: 0 }, map: leaf("a.css", "a{}") },
      { offset: { line: 1, column: 0 }, map: leaf("b.css", "b{}") },
    ],
  });
  const expected = [
    { source: "a.css", line: 1, column: 0, name: null },
    { source: "b.css", line: 1, column: 0, name: null },
  ];
  for (let index = 0; index < expected.length; index++) {
    const position = { line: index + 1, column: 1 };
    assert.deepEqual(consumer.originalPositionFor(position), expected[index]);
  }
  const code = "a{}\nb{}\n";
  const node = sourceMap.SourceNode.fromStringWithSourceMap(code, consumer);
  assert.equal(node.toString(), code);
  assert.equal(node.toStringWithSourceMap({ file: "bundle.css" }).code, code);
});

test("PostCSS transforms ordinary CSS while preserving a valid previous map", async () => {
  const previous = new sourceMap.SourceMapGenerator({ file: "output.css" });
  previous.addMapping({
    generated: { line: 1, column: 0 },
    original: { line: 1, column: 0 },
    source: "input.css",
  });
  previous.setSourceContent("input.css", "a { color: red }");
  const result = await postcss([
    {
      postcssPlugin: "authzest-source-map-compatibility",
      Declaration(declaration) {
        if (declaration.prop === "color") declaration.value = "blue";
      },
    },
  ]).process("a { color: red }", {
    from: "output.css",
    to: "bundle.css",
    map: { prev: previous.toJSON(), inline: false, annotation: false },
  });
  assert.equal(result.css, "a { color: blue }");
  assert.ok(result.map);
  const consumer = new sourceMap.SourceMapConsumer(result.map.toJSON());
  assert.deepEqual(consumer.originalPositionFor({ line: 1, column: 0 }), {
    source: "input.css",
    line: 1,
    column: 0,
    name: null,
  });
  assert.equal(consumer.sourceContentFor("input.css"), "a { color: red }");
});
