const RULE_ID_START = 1;

function domainToRule(domain, ruleId) {
  const clean = domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  if (!clean) return null;

  return {
    id: ruleId,
    priority: 1,
    action: {
      type: "redirect",
      redirect: { extensionPath: "/blocked.html?site=" + encodeURIComponent(clean) },
    },
    condition: {
      urlFilter: "||" + clean + "^",
      resourceTypes: ["main_frame"],
    },
  };
}

async function getSettings() {
  const { blockedDomains = [], enabled = true } = await chrome.storage.sync.get([
    "blockedDomains",
    "enabled",
  ]);
  return { blockedDomains, enabled };
}

async function applyRules() {
  const { blockedDomains, enabled } = await getSettings();
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  const removeIds = existing.map((rule) => rule.id);

  const addRules = [];
  if (enabled) {
    blockedDomains.forEach((domain, index) => {
      const rule = domainToRule(domain, RULE_ID_START + index);
      if (rule) addRules.push(rule);
    });
  }

  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: removeIds,
    addRules,
  });
}

chrome.runtime.onInstalled.addListener(() => applyRules());
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "sync" && (changes.blockedDomains || changes.enabled)) {
    applyRules();
  }
});

applyRules();
