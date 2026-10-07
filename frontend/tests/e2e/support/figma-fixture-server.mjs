import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import next from "next";

const support = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(support, "../../..");
const repository = path.resolve(frontend, "..");
const native = path.join(repository, ".superpowers/figma/q1/native");
const app = next({
  dev: true,
  hostname: "127.0.0.1",
  port: 3300,
  dir: path.join(support, "figma-host"),
});
await app.prepare();
const handle = app.getRequestHandler();
const mime = {
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
  ".css": "text/css",
  ".js": "text/javascript",
  ".html": "text/html",
};
const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:3300");
  if (url.pathname === "/fixture-health") {
    response.end("test-only fixture host");
    return;
  }
  const roots = [
    ["/native/", native],
    ["/resources/", path.join(native, "resources")],
    ["/common/", path.join(native, "common")],
    ...["brand", "fonts", "icons"].map((name) => [
      `/${name}/`,
      path.join(frontend, "public", name),
    ]),
  ];
  for (const [prefix, root] of roots) {
    if (!url.pathname.startsWith(prefix)) continue;
    const target = path.resolve(
      root,
      decodeURIComponent(url.pathname.slice(prefix.length)),
    );
    if (
      !target.startsWith(`${path.resolve(root)}${path.sep}`) ||
      request.method !== "GET" ||
      !fs.existsSync(target) ||
      !fs.statSync(target).isFile()
    ) {
      response.writeHead(404).end();
      return;
    }
    response.setHeader(
      "content-type",
      `${mime[path.extname(target)] ?? "application/octet-stream"}; charset=utf-8`,
    );
    fs.createReadStream(target).pipe(response);
    return;
  }
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/session")) {
    response
      .writeHead(501)
      .end("Fixture request must be explicitly intercepted");
    return;
  }
  handle(request, response);
});
server.listen(3300, "127.0.0.1");
async function stop() {
  server.close();
  await app.close();
  process.exit(0);
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
