import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distIndex = resolve(rootDir, "dist", "index.html");
const viteBin = resolve(rootDir, "node_modules", "vite", "bin", "vite.js");

function getFreePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();

    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        if (address && typeof address === "object") {
          resolvePort(address.port);
          return;
        }

        reject(new Error("Could not reserve a local preview port."));
      });
    });
  });
}

async function fetchWithTimeout(url, timeoutMs = 2500) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForPreview(baseUrl, previewProcess, logs) {
  const deadline = Date.now() + 15_000;

  while (Date.now() < deadline) {
    if (previewProcess.exitCode !== null) {
      throw new Error(`Vite preview exited early.\n${logs.join("")}`);
    }

    try {
      const response = await fetchWithTimeout(baseUrl);
      if (response.ok) {
        return;
      }
    } catch {
      // The server is still starting.
    }

    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }

  throw new Error(`Timed out waiting for Vite preview at ${baseUrl}.\n${logs.join("")}`);
}

async function expectHtml(baseUrl, path) {
  const response = await fetchWithTimeout(`${baseUrl}${path}`);

  if (!response.ok) {
    throw new Error(`Expected ${path} to return 2xx, received ${response.status}.`);
  }

  const html = await response.text();

  if (!html.includes('<div id="root"></div>')) {
    throw new Error(`Expected ${path} to serve the React application shell.`);
  }

  return html;
}

async function expectAssets(baseUrl, html) {
  const assetPaths = [
    ...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"/g),
    ...html.matchAll(/<link\b[^>]*\bhref="([^"]+)"/g),
  ].map((match) => match[1]);

  if (assetPaths.length === 0) {
    throw new Error("Expected the preview HTML to reference at least one built asset.");
  }

  for (const assetPath of assetPaths) {
    const response = await fetchWithTimeout(`${baseUrl}${assetPath}`);

    if (!response.ok) {
      throw new Error(`Expected asset ${assetPath} to return 2xx, received ${response.status}.`);
    }
  }
}

async function main() {
  if (!existsSync(distIndex)) {
    throw new Error("Missing dist/index.html. Run `npm run build` before `npm run smoke:preview`.");
  }

  const port = await getFreePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const logs = [];
  const previewProcess = spawn(
    process.execPath,
    [viteBin, "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    {
      cwd: rootDir,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  previewProcess.stdout.on("data", (chunk) => logs.push(chunk.toString()));
  previewProcess.stderr.on("data", (chunk) => logs.push(chunk.toString()));

  try {
    await waitForPreview(baseUrl, previewProcess, logs);
    const kioskHtml = await expectHtml(baseUrl, "/");
    await expectHtml(baseUrl, "/admin");
    await expectAssets(baseUrl, kioskHtml);
    console.log(`Frontend preview smoke passed at ${baseUrl}`);
  } finally {
    previewProcess.kill("SIGTERM");
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
