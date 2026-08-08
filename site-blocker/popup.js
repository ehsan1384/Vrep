const dot = document.getElementById("dot");
const status = document.getElementById("status");
const count = document.getElementById("count");

chrome.storage.sync.get(["blockedDomains", "enabled"], ({ blockedDomains = [], enabled = true }) => {
  count.textContent = blockedDomains.length;
  if (enabled) {
    dot.classList.remove("off");
    status.textContent = "فعال";
  } else {
    dot.classList.add("off");
    status.textContent = "غیرفعال";
  }
});

document.getElementById("open-options").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});
