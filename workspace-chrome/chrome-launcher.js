const { spawn } = require("child_process");
const { chromium } = require("playwright");

// Read configuration from environment variables
const cdpPort = process.env.CDP_PORT || 9222;

// Chromium path (dynamically obtained from Playwright to avoid version hardcoding)
const chromiumPath = chromium.executablePath();

console.log("Starting Chrome in normal mode with address bar...");
console.log(`Chromium path: ${chromiumPath}`);

// GPU acceleration setting (enabled by default)
const enableGpu = process.env.ENABLE_GPU !== "false";

const chromeArgs = [

  `--remote-debugging-port=${cdpPort}`,


  "--window-size=1440,900",
  "--window-position=0,0",
  "--disable-session-crashed-bubble",
  "--noerrdialogs",
  "--disable-features=Translate",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-blink-features=AutomationControlled",
  "--user-data-dir=/tmp/chrome-user-data",
  "--disable-background-networking",
  "--disable-sync",
  "about:blank"  // Initial page
];

// GPU-related parameters
if (enableGpu) {
  console.log("GPU acceleration: ENABLED");
  chromeArgs.push(
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--ignore-gpu-blocklist"
  );
} else {
  console.log("GPU acceleration: DISABLED");
  chromeArgs.push(
    "--disable-gpu",
    "--disable-software-rasterizer"
  );
}

const chrome = spawn(chromiumPath, chromeArgs, {
  stdio: ["ignore", "pipe", "pipe"],
  env: {
    ...process.env,
    DISPLAY: process.env.DISPLAY || ":99",
    // Input method environment variables
    GTK_IM_MODULE: "fcitx",
    QT_IM_MODULE: "fcitx",
    XMODIFIERS: "@im=fcitx",
    DBUS_SESSION_BUS_ADDRESS: "unix:path=/tmp/dbus-session-bus",
    // Chinese locale
    LANG: "zh_TW.UTF-8",
    LC_ALL: "zh_TW.UTF-8",
    // Disable Google API key warnings
    GOOGLE_API_KEY: "no",
    GOOGLE_DEFAULT_CLIENT_ID: "no",
    GOOGLE_DEFAULT_CLIENT_SECRET: "no"
  }
});

chrome.stdout.on("data", (data) => {
  console.log(`Chrome stdout: ${data}`);
});

chrome.stderr.on("data", (data) => {
  console.log(`Chrome stderr: ${data}`);
});

chrome.on("error", (error) => {
  console.error(`Failed to start Chrome: ${error.message}`);
  console.error(`Error code: ${error.code}`);
  if (error.code === 'ENOENT') {
    console.error(`Chrome binary not found at: ${chromiumPath}`);
    console.error(`Please ensure Playwright Chromium is installed.`);
  }
  process.exit(1);
});

chrome.on("close", (code) => {
  console.log(`Chrome process exited with code ${code}`);
  process.exit(code);
});

console.log("Waiting for Chrome to start...");
setTimeout(() => {
  console.log(`Chrome started in normal mode`);
  console.log(`CDP endpoint available on port ${cdpPort}`);
}, 3000);

process.on("SIGINT", () => {
  console.log("Shutting down Chrome...");
  chrome.kill("SIGTERM");
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("Shutting down Chrome...");
  chrome.kill("SIGTERM");
  process.exit(0);
});
