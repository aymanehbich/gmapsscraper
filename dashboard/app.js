/**
 * LeadLaunch — Scraper & Outreach Web Dashboard Controller
 */

// City Presets Database
const COUNTRY_CITY_PRESETS = {
  United_States: ['Austin', 'Miami', 'Houston', 'Los Angeles', 'Chicago', 'Atlanta', 'Dallas', 'Phoenix'],
  France: ['Paris', 'Lyon', 'Marseille', 'Bordeaux', 'Toulouse', 'Nice', 'Nantes', 'Lille'],
  Morocco: ['Casablanca', 'Rabat', 'Marrakech', 'Tangier', 'Agadir', 'Fes'],
  United_Kingdom: ['London', 'Manchester', 'Birmingham', 'Leeds', 'Glasgow'],
  Canada: ['Toronto', 'Montreal', 'Vancouver', 'Calgary', 'Ottawa'],
  Switzerland: ['Geneva', 'Zurich', 'Lausanne', 'Basel', 'Bern'],
  custom: ['Custom Location']
};

const GITHUB_OWNER = 'aymanehbich';
const GITHUB_REPO = 'gmapsscraper';
const WORKFLOW_FILE = 'scrape.yml';

// State
let pollInterval = null;

// DOM Elements
let inputPat, btnSavePat, btnSettingsToggle, btnCloseSettings, settingsPanel, patStatusDot, btnTogglePatView;
let scrapeForm, inputNiche, selectCountry, inputCity, inputDepth, depthVal, toggleEnrich, toggleN8n, btnLaunch;
let nicheChips, cityChips, runsContainer, btnRefreshRuns, toastContainer;
let selectService, inputCustomService, btnToggleCopy, copyPanel, inputCustomSubject, inputCustomPitch, inputDemoLink;

// Brevo Elements
let inputBrevoKey, btnToggleBrevoView, btnRefreshQuota, quotaStatusBadge;
let quotaRemainingVal, quotaCapVal, quotaSentVal, quotaPercentVal, quotaProgressBar;
let quotaResetCountdown, brevoApiStatusNote, linkConfigureBrevo;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  // Grab Elements
  inputPat = document.getElementById('input-pat');
  btnSavePat = document.getElementById('btn-save-pat');
  btnSettingsToggle = document.getElementById('btn-settings-toggle');
  btnCloseSettings = document.getElementById('btn-close-settings');
  settingsPanel = document.getElementById('settings-panel');
  patStatusDot = document.getElementById('pat-status-dot');
  btnTogglePatView = document.getElementById('btn-toggle-pat-view');

  scrapeForm = document.getElementById('scrape-form');
  inputNiche = document.getElementById('input-niche');
  selectCountry = document.getElementById('select-country');
  inputCity = document.getElementById('input-city');
  inputDepth = document.getElementById('input-depth');
  depthVal = document.getElementById('depth-val');
  toggleEnrich = document.getElementById('toggle-enrich');
  toggleN8n = document.getElementById('toggle-n8n');
  btnLaunch = document.getElementById('btn-launch');

  selectService = document.getElementById('select-service');
  inputCustomService = document.getElementById('input-custom-service');
  btnToggleCopy = document.getElementById('btn-toggle-copy');
  copyPanel = document.getElementById('copy-panel');
  inputCustomSubject = document.getElementById('input-custom-subject');
  inputCustomPitch = document.getElementById('input-custom-pitch');
  inputDemoLink = document.getElementById('input-demo-link');

  nicheChips = document.getElementById('niche-chips');
  cityChips = document.getElementById('city-chips');
  runsContainer = document.getElementById('runs-container');
  btnRefreshRuns = document.getElementById('btn-refresh-runs');
  toastContainer = document.getElementById('toast-container');

  // Brevo Elements
  inputBrevoKey = document.getElementById('input-brevo-key');
  btnToggleBrevoView = document.getElementById('btn-toggle-brevo-view');
  btnRefreshQuota = document.getElementById('btn-refresh-quota');
  quotaStatusBadge = document.getElementById('quota-status-badge');
  quotaRemainingVal = document.getElementById('quota-remaining-val');
  quotaCapVal = document.getElementById('quota-cap-val');
  quotaSentVal = document.getElementById('quota-sent-val');
  quotaPercentVal = document.getElementById('quota-percent-val');
  quotaProgressBar = document.getElementById('quota-progress-bar');
  quotaResetCountdown = document.getElementById('quota-reset-countdown');
  brevoApiStatusNote = document.getElementById('brevo-api-status-note');
  linkConfigureBrevo = document.getElementById('link-configure-brevo');

  if (window.lucide) {
    window.lucide.createIcons();
  }

  loadStoredPat();
  loadStoredBrevoKey();
  updateCityChips(selectCountry ? selectCountry.value : 'United_States');
  setupEventListeners();
  initBrevoIntegration();
  fetchRuns();
  pingN8nWebhook();

  // Auto-poll runs and n8n status every 12 seconds
  pollInterval = setInterval(() => {
    fetchRuns();
    pingN8nWebhook();
  }, 12000);
});

async function pingN8nWebhook() {
  const n8nPill = document.getElementById('n8n-live-pill');
  if (!n8nPill) return;
  try {
    const res = await fetch('https://aymane-hbich-n8n-c2967382a5d9.herokuapp.com/healthz', { mode: 'no-cors' });
    n8nPill.classList.remove('status-offline');
    n8nPill.innerHTML = '<span class="pulse-dot"></span><span>n8n Online</span>';
    n8nPill.title = 'n8n instance is responsive';
  } catch (e) {
    n8nPill.innerHTML = '<span class="pulse-dot"></span><span>n8n Ready</span>';
  }
}

// Event Listeners
function setupEventListeners() {
  // Settings Drawer Toggle
  if (btnSettingsToggle) {
    btnSettingsToggle.addEventListener('click', () => {
      openSettings();
    });
  }

  if (btnCloseSettings) {
    btnCloseSettings.addEventListener('click', () => {
      closeSettings();
    });
  }

  if (settingsPanel) {
    settingsPanel.addEventListener('click', (e) => {
      if (e.target === settingsPanel) {
        closeSettings();
      }
    });
  }

  // Toggle PAT Visibility
  if (btnTogglePatView && inputPat) {
    btnTogglePatView.addEventListener('click', () => {
      const isPwd = inputPat.type === 'password';
      inputPat.type = isPwd ? 'text' : 'password';
      const icon = btnTogglePatView.querySelector('svg');
      if (icon) icon.style.opacity = isPwd ? '1' : '0.5';
    });
  }

  // Toggle Brevo Visibility
  if (btnToggleBrevoView && inputBrevoKey) {
    btnToggleBrevoView.addEventListener('click', () => {
      const isPwd = inputBrevoKey.type === 'password';
      inputBrevoKey.type = isPwd ? 'text' : 'password';
      const icon = btnToggleBrevoView.querySelector('svg');
      if (icon) icon.style.opacity = isPwd ? '1' : '0.5';
    });
  }

  // Save Settings Button
  if (btnSavePat) {
    btnSavePat.addEventListener('click', () => {
      // Save PAT
      const patVal = inputPat ? inputPat.value.trim() : '';
      if (patVal) {
        localStorage.setItem('gh_pat', patVal);
        updatePatStatus(true);
      } else {
        localStorage.removeItem('gh_pat');
        updatePatStatus(false);
      }

      // Save Brevo Key
      const brevoVal = inputBrevoKey ? inputBrevoKey.value.trim() : '';
      if (brevoVal) {
        localStorage.setItem('brevo_api_key', brevoVal);
        showToast('Settings & Brevo API Key saved!', 'success');
        fetchBrevoQuota();
      } else {
        localStorage.removeItem('brevo_api_key');
        showToast('Settings saved!', 'success');
        fetchBrevoQuota();
      }

      closeSettings();
      fetchRuns();
    });
  }

  // Niche Chips
  if (nicheChips) {
    nicheChips.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      document.querySelectorAll('#niche-chips .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (inputNiche) inputNiche.value = chip.dataset.niche;
    });
  }

  // Service Selection Change
  if (selectService) {
    selectService.addEventListener('change', () => {
      if (inputCustomService) {
        if (selectService.value === 'custom') {
          inputCustomService.classList.remove('hidden');
          inputCustomService.focus();
        } else {
          inputCustomService.classList.add('hidden');
        }
      }
    });
  }

  // Toggle Custom Email Copy Accordion
  if (btnToggleCopy && copyPanel) {
    btnToggleCopy.addEventListener('click', () => {
      copyPanel.classList.toggle('hidden');
      const icon = document.getElementById('accordion-icon');
      if (icon) {
        icon.style.transform = copyPanel.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(180deg)';
        icon.style.transition = 'transform 0.2s ease';
      }
    });
  }

  // Click on variable chips to insert into active input
  document.querySelectorAll('.variables-bar code').forEach(codeEl => {
    codeEl.addEventListener('click', () => {
      const varText = codeEl.textContent.trim();
      if (inputCustomPitch) {
        inputCustomPitch.value += ` ${varText}`;
        inputCustomPitch.focus();
        showToast(`Inserted ${varText}`, 'info');
      }
    });
  });

  // Country Selection Change
  if (selectCountry) {
    selectCountry.addEventListener('change', () => {
      updateCityChips(selectCountry.value);
    });
  }

  // Depth Slider
  if (inputDepth && depthVal) {
    inputDepth.addEventListener('input', () => {
      depthVal.textContent = inputDepth.value;
      updateDepthEstimate(inputDepth.value);
    });
  }

  // Keyboard Shortcut: Ctrl + Enter to launch
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (scrapeForm && !btnLaunch.disabled) {
        scrapeForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    }
  });

  // Refresh Runs Button
  if (btnRefreshRuns) {
    btnRefreshRuns.addEventListener('click', () => {
      btnRefreshRuns.querySelector('svg')?.classList.add('animate-spin');
      fetchRuns().finally(() => {
        btnRefreshRuns.querySelector('svg')?.classList.remove('animate-spin');
      });
    });
  }

  // Form Submit (Launch)
  if (scrapeForm) {
    scrapeForm.addEventListener('submit', handleLaunch);
  }
}

function updateDepthEstimate(val) {
  const estimateEl = document.getElementById('depth-estimate');
  if (estimateEl) {
    estimateEl.textContent = `~${val} leads`;
  }
}

function openSettings(focusField = 'pat') {
  if (!settingsPanel) return;
  settingsPanel.classList.remove('hidden');
  if (focusField === 'brevo' && inputBrevoKey) {
    inputBrevoKey.focus();
  } else if (inputPat) {
    inputPat.focus();
  }
}

function closeSettings() {
  if (settingsPanel) {
    settingsPanel.classList.add('hidden');
  }
}

// Update City Chips on Country Change
function updateCityChips(country) {
  if (!cityChips) return;
  const cities = COUNTRY_CITY_PRESETS[country] || [];
  cityChips.innerHTML = '';

  if (cities.length === 0 || country === 'custom') {
    cityChips.innerHTML = '<span class="text-sub" style="font-size: 0.75rem;">Type your city name in the input above.</span>';
    return;
  }

  cities.forEach((city, idx) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = `chip ${idx === 0 && !inputCity.value ? 'active' : ''}`;
    chip.dataset.city = city;
    chip.textContent = city;
    
    chip.addEventListener('click', () => {
      document.querySelectorAll('#city-chips .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (inputCity) inputCity.value = city;
    });

    cityChips.appendChild(chip);
  });

  if (cities.length > 0 && inputCity && !inputCity.value) {
    inputCity.value = cities[0];
  }
}

// PAT Storage Helpers
function loadStoredPat() {
  const stored = localStorage.getItem('gh_pat');
  if (stored && inputPat) {
    inputPat.value = stored;
    updatePatStatus(true);
  } else {
    updatePatStatus(false);
  }
}

function loadStoredBrevoKey() {
  const storedBrevo = localStorage.getItem('brevo_api_key');
  if (storedBrevo && inputBrevoKey) {
    inputBrevoKey.value = storedBrevo;
  }
}

function updatePatStatus(hasToken) {
  if (!patStatusDot) return;
  if (hasToken) {
    patStatusDot.className = 'status-dot dot-online';
    patStatusDot.title = 'GitHub Token Active';
  } else {
    patStatusDot.className = 'status-dot dot-offline';
    patStatusDot.title = 'No Token Configured';
  }
}

// ==========================================================================
// Brevo Quota & Account Management
// ==========================================================================

function initBrevoIntegration() {
  // Direct click handler on Connect API Key link
  if (linkConfigureBrevo) {
    linkConfigureBrevo.addEventListener('click', (e) => {
      e.preventDefault();
      openSettings('brevo');
    });
  }

  // Refresh quota button
  if (btnRefreshQuota) {
    btnRefreshQuota.addEventListener('click', () => {
      btnRefreshQuota.querySelector('svg')?.classList.add('animate-spin');
      fetchBrevoQuota().finally(() => {
        btnRefreshQuota.querySelector('svg')?.classList.remove('animate-spin');
      });
    });
  }

  // Update countdown timer immediately and every minute
  updateResetCountdown();
  setInterval(updateResetCountdown, 60000);

  // Initial quota display
  fetchBrevoQuota();
}

function updateResetCountdown() {
  if (!quotaResetCountdown) return;
  const now = new Date();
  const nextUtcMidnight = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0));
  const diffMs = nextUtcMidnight - now;
  
  if (diffMs > 0) {
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    quotaResetCountdown.textContent = `Resets in ${hours}h ${mins}m (00:00 UTC)`;
  } else {
    quotaResetCountdown.textContent = 'Quota resets soon (00:00 UTC)';
  }
}

async function fetchBrevoQuota() {
  const brevoKey = localStorage.getItem('brevo_api_key');
  
  // If no Brevo API Key is entered yet, show clean ready state
  if (!brevoKey) {
    if (quotaRemainingVal) quotaRemainingVal.textContent = '300';
    if (quotaSentVal) quotaSentVal.textContent = '0';
    if (quotaPercentVal) quotaPercentVal.textContent = '0%';
    if (quotaProgressBar) {
      quotaProgressBar.style.width = '0%';
      quotaProgressBar.className = 'quota-progress-bar';
    }
    if (quotaStatusBadge) {
      quotaStatusBadge.className = 'badge badge-success';
      quotaStatusBadge.innerHTML = '<span class="pulse-dot"></span> Ready';
    }
    if (brevoApiStatusNote) {
      brevoApiStatusNote.innerHTML = '<a href="#" class="link-highlight" id="link-configure-brevo-dyn">Connect API Key</a>';
      document.getElementById('link-configure-brevo-dyn')?.addEventListener('click', (e) => {
        e.preventDefault();
        openSettings('brevo');
      });
    }
    return;
  }

  if (brevoApiStatusNote) {
    brevoApiStatusNote.innerHTML = '<span style="color: #10b981; font-weight: 600; font-size: 0.72rem;">⚡ Live Brevo Synced</span>';
  }

  try {
    const res = await fetch('https://api.brevo.com/v3/account', {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'api-key': brevoKey
      }
    });

    if (!res.ok) {
      if (res.status === 401) {
        showToast('Invalid Brevo API Key. Please check settings.', 'error');
        if (quotaStatusBadge) {
          quotaStatusBadge.className = 'badge badge-failure';
          quotaStatusBadge.textContent = 'Invalid Key';
        }
      }
      return;
    }

    const data = await res.json();
    const plans = data.plan || [];
    
    // Find daily transactional / sendLimit plan
    const sendPlan = plans.find(p => p.creditsType === 'sendLimit') || plans.find(p => p.type === 'free') || { credits: 300 };
    const remainingCredits = typeof sendPlan.credits === 'number' ? Math.round(sendPlan.credits) : 300;
    const totalDaily = 300;
    const estimatedSent = Math.max(0, totalDaily - remainingCredits);
    const percentUsed = Math.min(100, Math.round((estimatedSent / totalDaily) * 100));

    if (quotaRemainingVal) quotaRemainingVal.textContent = remainingCredits;
    if (quotaSentVal) quotaSentVal.textContent = estimatedSent;
    if (quotaPercentVal) quotaPercentVal.textContent = `${percentUsed}%`;

    if (quotaProgressBar) {
      quotaProgressBar.style.width = `${percentUsed}%`;
      if (remainingCredits <= 20) {
        quotaProgressBar.className = 'quota-progress-bar danger';
      } else if (remainingCredits <= 60) {
        quotaProgressBar.className = 'quota-progress-bar warning';
      } else {
        quotaProgressBar.className = 'quota-progress-bar';
      }
    }

    if (quotaStatusBadge) {
      if (remainingCredits <= 20) {
        quotaStatusBadge.className = 'badge badge-failure';
        quotaStatusBadge.innerHTML = '<span class="pulse-dot" style="background:#ef4444;"></span> Cap Reached (Paused)';
      } else if (remainingCredits <= 60) {
        quotaStatusBadge.className = 'badge badge-warning';
        quotaStatusBadge.innerHTML = '<span class="pulse-dot" style="background:#f59e0b;"></span> Low Quota';
      } else {
        quotaStatusBadge.className = 'badge badge-success';
        quotaStatusBadge.innerHTML = '<span class="pulse-dot"></span> Active';
      }
    }
  } catch (error) {
    console.error('Brevo API Quota Error:', error);
  }
}

// Form Launch Handler
async function handleLaunch(e) {
  e.preventDefault();

  const token = localStorage.getItem('gh_pat');
  if (!token) {
    showToast('Please set your GitHub Token first', 'error');
    openSettings('pat');
    return;
  }

  const niche = inputNiche ? inputNiche.value.trim() : '';
  const city = inputCity ? inputCity.value.trim() : '';
  const depth = inputDepth ? inputDepth.value : '20';
  const enrichEmails = toggleEnrich ? toggleEnrich.checked : true;
  const sendToN8n = toggleN8n ? toggleN8n.checked : true;

  // Read Service & Custom Copy
  let service = selectService ? selectService.value : 'web_design';
  if (service === 'custom' && inputCustomService) {
    service = inputCustomService.value.trim() || 'custom';
  }
  const customSubject = inputCustomSubject ? inputCustomSubject.value.trim() : '';
  const customPitch = inputCustomPitch ? inputCustomPitch.value.trim() : '';
  const demoLink = inputDemoLink ? inputDemoLink.value.trim() : '';

  if (!niche) {
    showToast('Please specify a target niche', 'error');
    return;
  }

  // Set Loading State
  btnLaunch.disabled = true;
  const origBtnContent = btnLaunch.innerHTML;
  btnLaunch.innerHTML = '<i data-lucide="loader-2" class="animate-spin"></i> <span>Triggering Cloud Runner...</span>';
  if (window.lucide) window.lucide.createIcons();

  try {
    const response = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`, {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: {
          niche: niche,
          city: city,
          depth: depth,
          enrich_emails: enrichEmails,
          send_to_n8n: sendToN8n,
          service: service,
          custom_subject: customSubject,
          custom_pitch: customPitch,
          demo_link: demoLink
        }
      })
    });

    if (response.status === 204) {
      showToast(`🚀 Scraper launched for ${niche} in ${city || 'all cities'}!`, 'success');
      setTimeout(fetchRuns, 1500);
    } else {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.message || `GitHub returned status ${response.status}`);
    }
  } catch (error) {
    showToast(`Failed to launch: ${error.message}`, 'error');
    console.error('Dispatch error:', error);
  } finally {
    btnLaunch.disabled = false;
    btnLaunch.innerHTML = origBtnContent;
    if (window.lucide) window.lucide.createIcons();
  }
}

// Fetch Recent Workflow Runs from GitHub
async function fetchRuns() {
  const token = localStorage.getItem('gh_pat');
  const headers = { 'Accept': 'application/vnd.github.v3+json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=5`, {
      headers
    });

    if (!res.ok) {
      if (res.status === 404) {
        renderRunsMessage('Workflow file not found or repository is private (Token required).');
      } else if (res.status === 401) {
        renderRunsMessage('Invalid GitHub Token. Please check token permissions.');
      }
      return;
    }

    const data = await res.json();
    renderRuns(data.workflow_runs || []);
  } catch (error) {
    console.error('Fetch runs error:', error);
  }
}

// Render Runs List
function renderRuns(runs) {
  if (!runsContainer) return;
  if (runs.length === 0) {
    renderRunsMessage('No workflow runs found yet.');
    return;
  }

  runsContainer.innerHTML = '';
  runs.forEach(run => {
    const runEl = document.createElement('div');
    runEl.className = 'run-item';

    const statusBadge = getStatusBadge(run.status, run.conclusion);
    const timeAgo = formatTimeAgo(new Date(run.created_at));

    runEl.innerHTML = `
      <div class="run-top">
        <div class="run-title">
          <i data-lucide="play-circle"></i>
          <span>#${run.run_number} — ${run.display_title || 'Lead Scrape'}</span>
        </div>
        ${statusBadge}
      </div>
      <div class="run-meta">
        <span>Triggered ${timeAgo}</span>
        <a href="${run.html_url}" target="_blank" rel="noopener" class="run-link">
          <span>View Logs</span>
          <i data-lucide="external-link" style="width: 12px; height: 12px;"></i>
        </a>
      </div>
    `;

    runsContainer.appendChild(runEl);
  });

  if (window.lucide) window.lucide.createIcons();
}

function renderRunsMessage(msg) {
  if (!runsContainer) return;
  runsContainer.innerHTML = `
    <div class="empty-runs">
      <i data-lucide="inbox"></i>
      <p>${msg}</p>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

// Helper: Status Badge
function getStatusBadge(status, conclusion) {
  if (status === 'in_progress') {
    return `<span class="run-badge badge-in-progress"><span class="pulse-dot"></span> Running</span>`;
  }
  if (status === 'queued') {
    return `<span class="run-badge badge-queued">Queued</span>`;
  }
  if (conclusion === 'success') {
    return `<span class="run-badge badge-success"><i data-lucide="check" style="width: 10px; height: 10px;"></i> Success</span>`;
  }
  if (conclusion === 'failure') {
    return `<span class="run-badge badge-failure"><i data-lucide="x" style="width: 10px; height: 10px;"></i> Failed</span>`;
  }
  return `<span class="run-badge badge-queued">${status}</span>`;
}

// Helper: Time ago formatter
function formatTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// Toast Notifications
function showToast(message, type = 'info') {
  if (!toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const iconName = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info';
  toast.innerHTML = `<i data-lucide="${iconName}"></i> <span>${message}</span>`;

  toastContainer.appendChild(toast);
  if (window.lucide) window.lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
