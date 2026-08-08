const domainInput = document.getElementById("domain-input");
const addBtn = document.getElementById("add-btn");
const domainList = document.getElementById("domain-list");
const countEl = document.getElementById("count");
const emptyMsg = document.getElementById("empty-msg");
const enabledToggle = document.getElementById("enabled");
const statusText = document.getElementById("status-text");

function normalizeDomain(raw) {
  return raw
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/\/.*$/, "");
}

function isValidDomain(domain) {
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(domain);
}

async function load() {
  const { blockedDomains = [], enabled = true } = await chrome.storage.sync.get([
    "blockedDomains",
    "enabled",
  ]);
  enabledToggle.checked = enabled;
  updateStatus(enabled);
  renderList(blockedDomains);
}

function updateStatus(enabled) {
  statusText.textContent = enabled ? "مسدودسازی فعال است" : "مسدودسازی غیرفعال است";
}

function renderList(domains) {
  domainList.innerHTML = "";
  countEl.textContent = domains.length;
  emptyMsg.classList.toggle("hidden", domains.length > 0);

  domains.forEach((domain) => {
    const li = document.createElement("li");
    li.innerHTML =
      '<span class="domain-name">' +
      domain +
      '</span><button class="remove-btn" data-domain="' +
      domain +
      '">حذف</button>';
    domainList.appendChild(li);
  });
}

async function save(domains) {
  await chrome.storage.sync.set({ blockedDomains: domains });
  renderList(domains);
}

addBtn.addEventListener("click", async () => {
  const domain = normalizeDomain(domainInput.value);
  if (!domain) return;
  if (!isValidDomain(domain)) {
    alert("دامنه معتبر نیست. مثال: twitter.com");
    return;
  }

  const { blockedDomains = [] } = await chrome.storage.sync.get("blockedDomains");
  if (blockedDomains.includes(domain)) {
    alert("این سایت قبلاً اضافه شده.");
    return;
  }

  blockedDomains.push(domain);
  await save(blockedDomains);
  domainInput.value = "";
  domainInput.focus();
});

domainInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addBtn.click();
});

domainList.addEventListener("click", async (e) => {
  if (!e.target.classList.contains("remove-btn")) return;
  const domain = e.target.dataset.domain;
  const { blockedDomains = [] } = await chrome.storage.sync.get("blockedDomains");
  await save(blockedDomains.filter((d) => d !== domain));
});

enabledToggle.addEventListener("change", async () => {
  const enabled = enabledToggle.checked;
  await chrome.storage.sync.set({ enabled });
  updateStatus(enabled);
});

load();
