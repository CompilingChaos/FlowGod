// --- CONFIGURATION ---
const GH_TOKEN = "YOUR_GITHUB_PAT_HERE";
const OWNER = "CompilingChaos";
const REPO = "FlowGod";

/**
 * Main entry point: Schedules the next run and triggers GitHub
 */
function triggerFlowGod() {
  const now = new Date();

  // 1. Convert current time to EST (New York Time)
  const estTime = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
  const day = estTime.getDay(); // 0 = Sun, 1 = Mon, ..., 6 = Sat
  const hour = estTime.getHours();
  const minute = estTime.getMinutes();

  const isWeekend = (day === 0 || day === 6);
  // US Market Hours: 9:30 AM - 4:00 PM EST
  const isMarketHours = (hour >= 9 && hour < 16) || (hour === 9 && minute >= 30);
  
  // New Trigger: Every Market Day after Close (4:30 PM EST)
  const isAfterCloseDaily = (!isWeekend && hour === 16 && minute >= 30);
  
  // Specific trigger for End-of-Day Report at 4:05 PM EST
  const isEODReportTime = (!isWeekend && hour === 16 && minute >= 5 && minute < 10);

  // 2. Logic: What should we trigger?
  
  if (isEODReportTime) {
    callGitHubAPI("monitor.yml");
    console.log("📊 End-of-Day Report Triggered!");
    scheduleNextRun(60, 60);
    return;
  }

  // Daily Calibration Audit (Post-Market)
  if (isAfterCloseDaily && minute < 55) {
    callGitHubAPI("audit.yml");
    console.log("⚖️ Daily Audit Triggered!");
    scheduleNextRun(60, 60); // Check again in an hour (will be outside window)
    return;
  }

  // Standard Market Monitoring (Discord alerts)
  if (!isWeekend && isMarketHours) {
    callGitHubAPI("monitor.yml");
    console.log("🚀 Market is Open. GitHub Discord Monitor Triggered!");
    
    // Randomized interval (17-22 minutes) to emulate human-like behavior
    scheduleNextRun(17, 22); 
  }
  else {
    console.log("💤 Market is Closed or Weekend. Sleeping...");
    // If it's after hours or weekend, check back in 1 hour
    scheduleNextRun(60, 60);
  }
}

/**
 * Triggers a GitHub Workflow via API
 */
function callGitHubAPI(workflowId) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflowId}/dispatches`;
  const options = {
    method: "post",
    headers: {
      "Authorization": "Bearer " + GH_TOKEN,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    payload: JSON.stringify({ ref: "main" }),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    if (response.getResponseCode() !== 204) {
      console.log("⚠️ API Warning [" + workflowId + "]: " + response.getContentText());
    }
  } catch (e) {
    console.log("❌ API Error: " + e);
  }
}

/**
 * Clears old triggers and schedules a new one based on random delay
 */
function scheduleNextRun(min, max) {
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }

  const randomMinutes = Math.floor(Math.random() * (max - min + 1)) + min;

  ScriptApp.newTrigger("triggerFlowGod")
    .timeBased()
    .after(randomMinutes * 60 * 1000)
    .create();
}
