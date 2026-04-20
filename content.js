(function () {
  if (document.getElementById("my-extension-button")) return;

  // === Create Sidebar ===
  const sidebar = document.createElement("div");
  sidebar.id = "my-extension-sidebar";
  sidebar.style.display = "none";

  // === Create Floating Button ===
  const button = document.createElement("div");
  button.id = "my-extension-button";

  const img = document.createElement("img");
  img.src = chrome.runtime.getURL("img/TruthLens.png");
  button.appendChild(img);

  // === Toggle Logic ===
  button.addEventListener("click", () => {
    sidebar.style.display =
      sidebar.style.display === "none" ? "block" : "none";
  });

  document.body.appendChild(sidebar);
  document.body.appendChild(button);
})();