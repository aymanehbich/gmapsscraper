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
const inputPat = document.getElementById('input-pat');
const btnSavePat = document.getElementById('btn-save-pat');
const btnSettingsToggle = document.getElementById('btn-settings-toggle');
const btnCloseSettings = document.getElementById('btn-close-settings');
const settingsPanel = document.getElementById('settings-panel');
const patStatusDot = document.getElementById('pat-status-dot');
const btnTogglePatView = document.getElementById('btn-toggle-pat-view');

const scrapeForm = document.getElementById('scrape-form');
const inputNiche = document.getElementById('input-niche');
const selectCountry = document.getElementById('select-country');
const inputCity = document.getElementById('input-city');
const inputDepth = document.getElementById('input-depth');
const depthVal = document.getElementById('depth-val');
const toggleEnrich = document.getElementById('toggle-enrich');
const toggleN8n = document.getElementById('toggle-n8n');
const btnLaunch = document.getElementById('btn-launch');

const nicheChips = document.getElementById('niche-chips');
const cityChips = document.getElementById('city-chips');
const runsContainer = document.getElementById('runs-container');
const btnRefreshRuns = document.getElementById('btn-refresh-runs');
const toastContainer = document.getElementById('toast-container');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }

  loadStoredPat();
  updateCityChips(selectCountry.value);
  setupEventListeners();
  fetchRuns();

  // Auto-poll runs every 10 seconds
  pollInterval = setInterval(fetchRuns, 10000);
});

// Event Listeners
function setupEventListeners() {
  // Settings Drawer Toggle
  btnSettingsToggle.addEventListener('click', () => {
    settingsPanel.classList.remove('hidden');
    inputPat.focus();
  });

  btnCloseSettings.addEventListener('click', () => {
    settingsPanel.classList.add('hidden');
  });

  settingsPanel.addEventListener('click', (e) => {
    if (e.target === settingsPanel) {
      settingsPanel.classList.add('hidden');
    }
  });

  // Save PAT
  btnSavePat.addEventListener('click', () => {
    const token = inputPat.value.trim();
    if (!token) {
      localStorage.removeItem('gh_pat');
      updatePatStatus(false);
      showToast('Token cleared', 'info');
    } else {
      localStorage.setItem('gh_pat', token);
      updatePatStatus(true);
      showToast('GitHub token saved securely!', 'success');
      settingsPanel.classList.add('hidden');
      fetchRuns();
    }
  });

  // Toggle PAT visibility
  btnTogglePatView.addEventListener('click', () => {
    if (inputPat.type === 'password') {
      inputPat.type = 'text';
      btnTogglePatView.innerHTML = '<i data-lucide="eye-off"></i>';
    } else {
      inputPat.type = 'password';
      btnTogglePatView.innerHTML = '<i data-lucide="eye"></i>';
    }
    if (window.lucide) window.lucide.createIcons();
  });

  // Niche Chips selection
  nicheChips.addEventListener('click', (e) => {
    if (e.target.classList.contains('chip')) {
      document.querySelectorAll('#niche-chips .chip').forEach(c => c.classList.remove('active'));
      e.target.classList.add('active');
      inputNiche.value = e.target.dataset.niche;
    }
  });

  // Custom Niche Input typing
  inputNiche.addEventListener('input', () => {
    const currentVal = inputNiche.value.trim().toLowerCase();
    document.querySelectorAll('#niche-chips .chip').forEach(c => {
      if (c.dataset.niche.toLowerCase() === currentVal) {
        c.classList.add('active');
      } else {
        c.classList.remove('active');
      }
    });
  });

  // Country Selection Change
  selectCountry.addEventListener('change', () => {
    updateCityChips(selectCountry.value);
  });

  // Depth Slider
  inputDepth.addEventListener('input', () => {
    depthVal.textContent = inputDepth.value;
  });

  // Refresh Runs Button
  btnRefreshRuns.addEventListener('click', () => {
    btnRefreshRuns.querySelector('svg')?.classList.add('animate-spin');
    fetchRuns().finally(() => {
      btnRefreshRuns.querySelector('svg')?.classList.remove('animate-spin');
    });
  });

  // Form Submit (Launch)
  scrapeForm.addEventListener('submit', handleLaunch);
}

// Update City Chips on Country Change
function updateCityChips(country) {
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
      inputCity.value = city;
    });

    cityChips.appendChild(chip);
  });

  if (cities.length > 0 && !inputCity.value) {
    inputCity.value = cities[0];
  }
}

// PAT Storage Helpers
function loadStoredPat() {
  const stored = localStorage.getItem('gh_pat');
  if (stored) {
    inputPat.value = stored;
    updatePatStatus(true);
  } else {
    updatePatStatus(false);
  }
}

function updatePatStatus(hasToken) {
  if (hasToken) {
    patStatusDot.className = 'status-dot dot-online';
    patStatusDot.title = 'GitHub Token Active';
  } else {
    patStatusDot.className = 'status-dot dot-offline';
    patStatusDot.title = 'No Token Configured';
  }
}

// Form Launch Handler
async function handleLaunch(e) {
  e.preventDefault();

  const token = localStorage.getItem('gh_pat');
  if (!token) {
    showToast('Please set your GitHub Token first', 'error');
    settingsPanel.classList.remove('hidden');
    inputPat.focus();
    return;
  }

  const niche = inputNiche.value.trim();
  const city = inputCity.value.trim();
  const depth = inputDepth.value;
  const enrichEmails = toggleEnrich.checked;
  const sendToN8n = toggleN8n.checked;

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
          send_to_n8n: sendToN8n
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
