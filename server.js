import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const outputDir = process.env.KAMYABI_OUTPUT_DIR || fileURLToPath(new URL("./output/", import.meta.url));

function sendJson(response, status, body) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(body);
}

createServer(async (request, response) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.setHeader("Allow", "GET, HEAD");
    return sendJson(response, 405, '{"error":"Method not allowed"}');
  }

  const path = request.url.split("?", 1)[0];
  if (path === "/health") {
    return sendJson(response, 200, '{"status":"ok"}');
  }
  if (path === "/") {
    return sendJson(response, 200, '{"service":"Kamyabi recruitment monitor","notices":"/notices.json"}');
  }
  if (path !== "/notices.json") {
    return sendJson(response, 404, '{"error":"Not found"}');
  }

  try {
    const notices = await readFile(resolve(outputDir, "notices.json"), "utf8");
    return sendJson(response, 200, notices);
  } catch (error) {
    if (error.code === "ENOENT") {
      return sendJson(response, 503, '{"error":"Recruitment monitor output has not been deployed"}');
    }
    console.error("Could not read recruitment monitor output", error.code);
    return sendJson(response, 500, '{"error":"Recruitment output is unavailable"}');
  }
}).listen(Number(process.env.PORT || 3000), "0.0.0.0");
