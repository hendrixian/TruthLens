const LOCAL_SCAN_ENDPOINT = "http://127.0.0.1:8765/scan";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "truthlens_save_scan") {
    return;
  }

  (async () => {
    try {
      const scanPayload = message.payload || {};
      const response = await fetch(LOCAL_SCAN_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(scanPayload)
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `Save server returned ${response.status}`);
      }

      sendResponse({
        ok: true,
        filePath: data.file_path || ""
      });
    } catch (error) {
      console.error("TruthLens save failed:", error);
      sendResponse({ ok: false, error: String(error) });
    }
  })();

  return true;
});
