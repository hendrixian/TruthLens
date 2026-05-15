(function () {
  if (document.getElementById("my-extension-button")) return;

  // === Sidebar container ===
  const sidebar = document.createElement("div");
  sidebar.id = "my-extension-sidebar";
  sidebar.style.display = "none";
  sidebar.innerHTML = `
    <div id="truthlens-shell">
      <div id="truthlens-header">
        <div>
          <h2 id="truthlens-title">TruthLens</h2>
          <p id="truthlens-subtitle">See beyond the words</p>
        </div>
        <button id="truthlens-close" type="button" aria-label="Close panel">&rarr;</button>
      </div>
      <div id="truthlens-status" aria-live="polite"></div>
    </div>
  `;

  const statusEl = sidebar.querySelector("#truthlens-status");
  const closeBtn = sidebar.querySelector("#truthlens-close");

  function setStatus(message, state) {
    statusEl.textContent = message;
    statusEl.className = "";
    statusEl.classList.add("truthlens-status");
    if (state) {
      statusEl.classList.add(`truthlens-status-${state}`);
    }
  }

  function formatPrediction(label, confidence) {
    const normalizedLabel = String(label || "").trim().toLowerCase();
    if (!normalizedLabel) return "";

    const score =
      typeof confidence === "number" && Number.isFinite(confidence)
        ? confidence.toFixed(4)
        : "n/a";

    return `${normalizedLabel} (confidence: ${score})`;
  }

  function getArticleText() {
    const NOISE_LINE_PATTERNS = [
      /^advertisement$/i,
      /^skip advertisement$/i,
      /^share full article$/i,
      /^related content$/i,
      /^read \d+ comments$/i
    ];

    function normalizeLine(value) {
      return (value || "").replace(/\s+/g, " ").trim();
    }

    function isNoiseLine(value) {
      const line = normalizeLine(value);
      if (!line) return true;
      return NOISE_LINE_PATTERNS.some((p) => p.test(line));
    }

    function collectParagraphText(root) {
      if (!root) return "";
      const lines = Array.from(root.querySelectorAll("p"))
        .map((p) => normalizeLine(p.innerText))
        .filter((line) => !isNoiseLine(line));
      return lines.join("\n\n").trim();
    }

    const articleNode =
      document.querySelector("article") ||
      document.querySelector('[itemprop="articleBody"]') ||
      document.querySelector(".article-body") ||
      document.querySelector(".post-content") ||
      document.querySelector(".entry-content") ||
      document.querySelector("main");

    const scopedParagraphText = collectParagraphText(articleNode);
    if (scopedParagraphText.length > 120) {
      return scopedParagraphText;
    }

    if (articleNode && articleNode.innerText) {
      const text = articleNode.innerText
        .split("\n")
        .map((line) => normalizeLine(line))
        .filter((line) => !isNoiseLine(line))
        .join("\n")
        .trim();
      if (text.length > 120) return text;
    }

    const pText = collectParagraphText(document);

    if (pText.length > 120) return pText;
    return (document.body?.innerText || "").trim();
  }

  function getArticleTitle() {
    const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
    const h1Title = document.querySelector("h1")?.innerText;
    const pageTitle = document.title;
    return (ogTitle || h1Title || pageTitle || "untitled_article").trim();
  }

  function openContainer() {
    sidebar.style.display = "block";
    button.style.display = "none";
  }

  function closeContainer() {
    sidebar.style.display = "none";
    button.style.display = "flex";
    setStatus("", null);
  }

  async function runScan() {
    openContainer();
    setStatus("Scanning...", "progress");

    const payload = {
      title: getArticleTitle(),
      articleText: getArticleText(),
      url: location.href
    };

    try {
      const response = await chrome.runtime.sendMessage({
        type: "truthlens_save_scan",
        payload
      });

      if (response && response.ok) {
        const predictionText = formatPrediction(response.label, response.confidence);
        setStatus(predictionText || "Prediction unavailable", "success");
      } else {
        setStatus("Scan failed", "error");
      }
    } catch (e) {
      setStatus("Scan failed", "error");
      console.error("TruthLens scan failed:", e);
    }
  }

  // === Floating button ===
  const button = document.createElement("div");
  button.id = "my-extension-button";

  const img = document.createElement("img");
  img.src = chrome.runtime.getURL("assets/icons/TruthLens.png");
  button.appendChild(img);

  // === Scan on click ===
  button.addEventListener("click", runScan);
  closeBtn.addEventListener("click", closeContainer);

  document.body.appendChild(sidebar);
  document.body.appendChild(button);
})();
