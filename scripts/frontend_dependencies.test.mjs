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
