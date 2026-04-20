(function () {
  if (document.getElementById("my-extension-button")) return;

  // === Sidebar container ===
  const sidebar = document.createElement("div");
  sidebar.id = "my-extension-sidebar";
  sidebar.style.display = "none";

  // === Load HTML into sidebar ===
  fetch(chrome.runtime.getURL("main.html"))
    .then(res => res.text())
    .then(html => {
      sidebar.innerHTML = html;
    });

  // === Floating button ===
  const button = document.createElement("div");
  button.id = "my-extension-button";

  const img = document.createElement("img");
  img.src = chrome.runtime.getURL("img/TruthLens.png");
  button.appendChild(img);

  // === Toggle ===
  button.addEventListener("click", () => {
    sidebar.style.display =
      sidebar.style.display === "none" ? "block" : "none";
  });

  document.body.appendChild(sidebar);
  document.body.appendChild(button);
})();