import fs from "node:fs";

for (const file of ["index.html", "skill/scripts/studio.html"]) {
  const html = fs.readFileSync(file, "utf8");
  const scripts = [...html.matchAll(/<script(?![^>]*type=["']application\/json["'])[^>]*>([\s\S]*?)<\/script>/gi)];
  if (!scripts.length) throw new Error(`${file}: no se encontró JavaScript`);
  for (const [, source] of scripts) new Function(source);
  console.log(`${file}: ${scripts.length} bloque(s) JavaScript con sintaxis válida`);
}
