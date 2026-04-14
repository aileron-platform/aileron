import type {
  GetStateMessage,
  SetStateMessage,
  SetGlowEnabledMessage,
  StateResponse,
  GetConfigMessage,
  SetConfigMessage,
  ResetConfigMessage,
  ConfigResponse,
  RelayConfig,
} from "../../utils/types";

const toggle = document.getElementById("active-toggle") as HTMLInputElement;
const statusText = document.getElementById("status-text") as HTMLSpanElement;
const glowToggle = document.getElementById("glow-toggle") as HTMLInputElement;

// Config form elements
const hostInput = document.getElementById("host-input") as HTMLInputElement;
const portInput = document.getElementById("port-input") as HTMLInputElement;
const pathInput = document.getElementById("path-input") as HTMLInputElement;
const saveConfigBtn = document.getElementById("save-config") as HTMLButtonElement;
const resetConfigBtn = document.getElementById("reset-config") as HTMLButtonElement;

function updateUI(state: StateResponse): void {
  toggle.checked = state.isActive;
  statusText.textContent = state.isActive ? "已啟用" : "已停用";

  // 更新光暈開關
  glowToggle.checked = state.glowEnabled ?? true;
}

function refreshState(): void {
  chrome.runtime.sendMessage<GetStateMessage, StateResponse>({ type: "getState" }, (response) => {
    if (response) {
      updateUI(response);
    }
  });
}

// Load initial state
refreshState();

// Poll for state updates while popup is open (every 3 seconds to reduce requests)
const pollInterval = setInterval(refreshState, 3000);

// Clean up on popup close
window.addEventListener("unload", () => {
  clearInterval(pollInterval);
});

// Handle toggle changes
toggle.addEventListener("change", () => {
  const isActive = toggle.checked;
  chrome.runtime.sendMessage<SetStateMessage, StateResponse>(
    { type: "setState", isActive },
    (response) => {
      if (response) {
        updateUI(response);
      }
    }
  );
});

// Handle glow toggle changes
glowToggle.addEventListener("change", () => {
  const enabled = glowToggle.checked;
  chrome.runtime.sendMessage<SetGlowEnabledMessage, StateResponse>(
    { type: "setGlowEnabled", enabled },
    (response) => {
      if (response) {
        updateUI(response);
      }
    }
  );
});

// Config UI functions
function updateConfigUI(config: RelayConfig): void {
  hostInput.value = config.host;
  portInput.value = String(config.port);
  pathInput.value = config.basePath;
}

function refreshConfig(): void {
  chrome.runtime.sendMessage<GetConfigMessage, ConfigResponse>({ type: "getConfig" }, (response) => {
    if (response) {
      updateConfigUI(response.config);
    }
  });
}

// Load initial config
refreshConfig();

// Handle save config
saveConfigBtn.addEventListener("click", () => {
  const config: Partial<RelayConfig> = {
    host: hostInput.value.trim() || "localhost",
    port: parseInt(portInput.value, 10) || 3002,
    basePath: pathInput.value.trim() || "/api/v1/client-browser-relay",
  };

  chrome.runtime.sendMessage<SetConfigMessage, ConfigResponse>(
    { type: "setConfig", config },
    (response) => {
      if (response) {
        updateConfigUI(response.config);
        // Refresh state to show new connection status
        setTimeout(refreshState, 500);
      }
    }
  );
});

// Handle reset config
resetConfigBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage<ResetConfigMessage, ConfigResponse>(
    { type: "resetConfig" },
    (response) => {
      if (response) {
        updateConfigUI(response.config);
        // Refresh state to show new connection status
        setTimeout(refreshState, 500);
      }
    }
  );
});
