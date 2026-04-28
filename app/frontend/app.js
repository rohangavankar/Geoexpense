const NOMINATIM = 'https://nominatim.openstreetmap.org';
const NOMINATIM_HEADERS = { 'Accept-Language': 'en', 'User-Agent': 'GeoExpense/1.0' };

const CATEGORY_COLORS = {
  'Meals & Entertainment':    '#f59e0b',
  'Travel':                   '#3b82f6',
  'Software & Tech':          '#8b5cf6',
  'Office Supplies':          '#10b981',
  'Transportation':           '#06b6d4',
  'Professional Development': '#ec4899',
  'Other':                    '#6b7280',
  'Uncategorized':            '#6b7280',
};

let map, streetLayer, satelliteLayer, isSatellite = false;
let markerCluster, markers = {}, pendingMarker = null, searchPin = null;
let expenseCache = {}, currentUser = null;
let searchDebounce = null;
let editingId = null;
let dateFrom = null, dateTo = null;

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.requireAuth()) return;

  currentUser = Auth.getUser();
  renderUserMenu();

  // Keyboard shortcut: N = add expense at map center
  document.addEventListener('keydown', e => {
    if (e.key === 'n' && !e.target.matches('input,textarea')) openModalAtCenter();
  });

  const input = document.getElementById('search-input');
  const clearBtn = document.getElementById('search-clear');
  input.addEventListener('input', () => {
    const q = input.value.trim();
    clearBtn.classList.toggle('hidden', !q);
    clearTimeout(searchDebounce);
    if (q.length < 2) return hideResults();
    searchDebounce = setTimeout(() => runSearch(q), 400);
  });
  input.addEventListener('keydown', e => { if (e.key === 'Escape') clearSearch(); });
  document.addEventListener('click', e => {
    if (!document.getElementById('search-container').contains(e.target)) hideResults();
  });

  // Date filters
  document.getElementById('filter-from').addEventListener('change', e => { dateFrom = e.target.value || null; loadExpenses(); });
  document.getElementById('filter-to').addEventListener('change', e => { dateTo = e.target.value || null; loadExpenses(); });

  initMap();
});

function renderUserMenu() {
  if (!currentUser) return;
  document.getElementById('user-name').textContent = currentUser.name;
  document.getElementById('company-name').textContent = currentUser.company_name || '';
  const isAdmin = ['owner', 'admin'].includes(currentUser.role);
  document.getElementById('pending-section').classList.toggle('hidden', !isAdmin);
}

// ── Map ───────────────────────────────────────────────────────────────────────

function initMap() {
  map = L.map('map', { zoomControl: true }).setView([39.5, -98.35], 4);

  streetLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd', maxZoom: 19,
  });

  satelliteLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: '© Esri, Maxar, Earthstar Geographics', maxZoom: 19 }
  );

  streetLayer.addTo(map);
  markerCluster = L.markerClusterGroup({ maxClusterRadius: 50, showCoverageOnHover: false });
  map.addLayer(markerCluster);
  map.on('click', onMapClick);
  loadExpenses();
}

function toggleLayer() {
  const btn = document.getElementById('layer-toggle');
  if (isSatellite) {
    map.removeLayer(satelliteLayer); streetLayer.addTo(map);
    btn.textContent = '🛰 Satellite'; btn.classList.remove('active');
  } else {
    map.removeLayer(streetLayer); satelliteLayer.addTo(map);
    btn.textContent = '🗺 Map'; btn.classList.add('active');
  }
  isSatellite = !isSatellite;
}

// ── Map click ─────────────────────────────────────────────────────────────────

async function onMapClick(e) {
  const { lat, lng } = e.latlng;
  dropPendingPin(lat, lng);
  prefillCoords(lat, lng, 'Detecting location…');
  openModal();
  await reverseGeocode(lat, lng);
}

function openModalAtCenter() {
  const c = map.getCenter();
  dropPendingPin(c.lat, c.lng);
  prefillCoords(c.lat, c.lng, 'Detecting location…');
  openModal();
  reverseGeocode(c.lat, c.lng);
}

function dropPendingPin(lat, lng) {
  if (pendingMarker) map.removeLayer(pendingMarker);
  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }
  pendingMarker = L.circleMarker([lat, lng], {
    radius: 10, color: '#6366f1', weight: 2, fillColor: '#6366f1', fillOpacity: 0.3,
  }).addTo(map);
}

function prefillCoords(lat, lng, address) {
  document.getElementById('f-lat').value = lat;
  document.getElementById('f-lng').value = lng;
  document.getElementById('f-city').value = '';
  document.getElementById('modal-address').textContent = address;
}

async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(`${NOMINATIM}/reverse?lat=${lat}&lon=${lng}&format=json`, { headers: NOMINATIM_HEADERS });
    const data = await res.json();
    const addr = data.address || {};
    const city = addr.city || addr.town || addr.village || addr.county || data.display_name.split(',')[0];
    document.getElementById('f-city').value = city;
    document.getElementById('modal-address').textContent = data.display_name || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  } catch {
    const fallback = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    document.getElementById('f-city').value = fallback;
    document.getElementById('modal-address').textContent = fallback;
  }
}

// ── Search ────────────────────────────────────────────────────────────────────

async function runSearch(q) {
  try {
    const params = new URLSearchParams({ q, format: 'json', limit: 6, addressdetails: 1, namedetails: 1, 'accept-language': 'en' });
    const res = await fetch(`${NOMINATIM}/search?${params}`, { headers: NOMINATIM_HEADERS });
    showResults(await res.json());
  } catch { hideResults(); }
}

function formatSub(r) {
  const a = r.address || {};
  const parts = [];
  if (a.road) parts.push(a.road);
  const city = a.city || a.town || a.village || a.suburb || a.county;
  if (city) parts.push(city);
  if (a.state) parts.push(a.state);
  if (a.country && a.country !== 'United States') parts.push(a.country);
  return parts.join(', ') || r.display_name.split(',').slice(1, 4).join(',').trim();
}

function showResults(results) {
  const box = document.getElementById('search-results');
  if (!results.length) {
    box.innerHTML = '<div class="search-no-results">No places found</div>';
    box.classList.remove('hidden'); return;
  }
  box.innerHTML = results.map((r, i) => {
    const main = (r.namedetails && r.namedetails.name) || r.display_name.split(',')[0];
    return `<div class="search-result" onclick="selectResult(${i})">
      <span class="search-result-icon">${placeIcon(r.type, r.class)}</span>
      <div>
        <div class="search-result-main">${main}</div>
        <div class="search-result-sub">${formatSub(r)}</div>
      </div></div>`;
  }).join('');
  box.dataset.results = JSON.stringify(results);
  box.classList.remove('hidden');
}

function selectResult(idx) {
  const results = JSON.parse(document.getElementById('search-results').dataset.results || '[]');
  const r = results[idx];
  if (!r) return;
  const placeName = (r.namedetails && r.namedetails.name) || r.display_name.split(',')[0];
  document.getElementById('search-input').value = placeName;
  hideResults();

  const lat = parseFloat(r.lat), lng = parseFloat(r.lon);
  const sub = formatSub(r);

  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }
  searchPin = L.marker([lat, lng], { icon: makeSearchPinIcon() }).addTo(map);
  searchPin.bindPopup(
    `<div style="padding:12px;font-family:-apple-system,sans-serif;min-width:180px">
      <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:2px">${placeName}</div>
      <div style="font-size:11px;color:#94a3b8;margin-bottom:10px">${sub}</div>
      <button onclick="addExpenseAtSearchPin(${lat},${lng},'${placeName.replace(/'/g, "\\'")}','${sub.replace(/'/g, "\\'")}')"
        style="width:100%;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border:none;
               padding:8px 12px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer">
        + Add Expense Here
      </button></div>`,
    { maxWidth: 240 }
  ).openPopup();

  const bbox = r.boundingbox;
  if (bbox) {
    map.fitBounds([[parseFloat(bbox[0]), parseFloat(bbox[2])], [parseFloat(bbox[1]), parseFloat(bbox[3])]], { maxZoom: 16, animate: true, duration: 1 });
  } else {
    map.setView([lat, lng], 16, { animate: true, duration: 1 });
  }
}

function makeSearchPinIcon() {
  return L.divIcon({
    className: '',
    html: `<div style="width:0;height:0;border-left:10px solid transparent;border-right:10px solid transparent;border-bottom:28px solid #6366f1;filter:drop-shadow(0 2px 4px rgba(99,102,241,0.5));position:relative;top:-28px"></div>
           <div style="width:8px;height:8px;background:#6366f1;border-radius:50%;position:relative;top:-28px;left:6px;margin-top:-4px"></div>`,
    iconSize: [20, 32], iconAnchor: [10, 32], popupAnchor: [0, -34],
  });
}

window.addExpenseAtSearchPin = (lat, lng, placeName, address) => {
  const city = address.split(',')[0].trim() || placeName;
  document.getElementById('f-lat').value = lat;
  document.getElementById('f-lng').value = lng;
  document.getElementById('f-city').value = city;
  document.getElementById('modal-address').textContent = address || placeName;
  if (searchPin) searchPin.closePopup();
  openModal();
};

function hideResults() { document.getElementById('search-results').classList.add('hidden'); }
function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear').classList.add('hidden');
  hideResults();
}

function placeIcon(type, cls) {
  if (cls === 'amenity' || type === 'restaurant' || type === 'cafe') return '🍽️';
  if (type === 'airport') return '✈️';
  if (cls === 'railway' || type === 'station') return '🚉';
  if (type === 'hotel' || type === 'motel') return '🏨';
  if (cls === 'building' || cls === 'office') return '🏢';
  if (cls === 'natural' || cls === 'water') return '🌊';
  if (type === 'park' || cls === 'leisure') return '🌳';
  return '📍';
}

// ── Markers ───────────────────────────────────────────────────────────────────

function makeMarkerIcon(category, amount) {
  const color = CATEGORY_COLORS[category] || '#6b7280';
  const size = amount > 500 ? 36 : amount > 100 ? 28 : 22;
  return L.divIcon({
    className: '',
    html: `<div style="width:${size}px;height:${size}px;background:${color};border:2px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;font-size:${Math.round(size*0.38)}px;color:white;font-weight:700">$</div>`,
    iconSize: [size, size], iconAnchor: [size/2, size/2],
  });
}

function buildPopup(e) {
  const isAdmin = ['owner', 'admin'].includes(currentUser?.role);
  const canEdit = isAdmin || e.user_id === currentUser?.id;
  const date = new Date(e.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const deductBadge = e.tax_deductible
    ? `<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">✓ Tax Deductible</span>`
    : `<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">✗ Not Deductible</span>`;

  const statusBadge = e.status === 'pending'
    ? `<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px">⏳ Pending</span>`
    : e.status === 'rejected'
    ? `<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px">✗ Rejected</span>`
    : '';

  const aiNote = e.ai_note
    ? `<div style="font-size:11px;color:#64748b;border-top:1px solid #f1f5f9;padding-top:8px;margin-top:8px;line-height:1.5"><span style="color:#7c3aed;font-weight:600">✨ AI:</span> ${e.ai_note}</div>`
    : '';

  const receipt = e.receipt_url
    ? `<div style="margin-top:8px"><a href="${e.receipt_url}" target="_blank" style="font-size:11px;color:#6366f1">📎 View Receipt</a></div>`
    : '';

  const submitter = e.submitter_name && e.submitter_name !== currentUser?.name
    ? `<div style="font-size:11px;color:#94a3b8;margin-top:4px">Submitted by ${e.submitter_name}</div>` : '';

  const actions = canEdit ? `
    <div style="display:flex;gap:8px;margin-top:10px">
      <button onclick="openEditModal(${e.id})" style="flex:1;background:#f1f5f9;border:1px solid #e2e8f0;color:#334155;padding:6px;border-radius:6px;font-size:12px;cursor:pointer">✏️ Edit</button>
      <button onclick="deleteExpense(${e.id})" style="flex:1;background:#fee2e2;border:1px solid #fecaca;color:#991b1b;padding:6px;border-radius:6px;font-size:12px;cursor:pointer">🗑 Delete</button>
    </div>` : '';

  const approvalActions = isAdmin && e.status === 'pending' ? `
    <div style="display:flex;gap:8px;margin-top:8px">
      <button onclick="approveExpense(${e.id})" style="flex:1;background:#d1fae5;border:1px solid #a7f3d0;color:#065f46;padding:6px;border-radius:6px;font-size:12px;cursor:pointer;font-weight:600">✓ Approve</button>
      <button onclick="rejectExpense(${e.id})" style="flex:1;background:#fee2e2;border:1px solid #fecaca;color:#991b1b;padding:6px;border-radius:6px;font-size:12px;cursor:pointer;font-weight:600">✗ Reject</button>
    </div>` : '';

  return `<div style="padding:14px;min-width:240px;font-family:-apple-system,sans-serif">
    <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:3px">${e.title}</div>
    <div style="font-size:12px;color:#94a3b8;margin-bottom:8px">${e.vendor} · ${e.city}</div>
    <div style="font-size:22px;font-weight:700;color:#2563eb;margin-bottom:8px">$${e.amount.toFixed(2)}</div>
    <span style="background:#eff6ff;color:#1d4ed8;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600">${e.category}</span>
    <span style="margin-left:6px">${deductBadge}</span>${statusBadge}
    <div style="font-size:11px;color:#94a3b8;margin-top:8px">${date}</div>
    ${submitter}${receipt}${aiNote}${approvalActions}${actions}
  </div>`;
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function loadExpenses() {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);

  const [expRes, sumRes] = await Promise.all([
    Auth.apiFetch(`/api/expenses?${params}`),
    Auth.apiFetch(`/api/expenses/summary?${params}`),
  ]);

  if (!expRes.ok) return;
  const expenses = await expRes.json();
  const summary = await sumRes.json();

  expenseCache = Object.fromEntries(expenses.map(e => [e.id, e]));

  markerCluster.clearLayers();
  markers = {};

  expenses.forEach(e => {
    if (e.status === 'rejected') return;
    const marker = L.marker([e.latitude, e.longitude], { icon: makeMarkerIcon(e.category, e.amount) })
      .bindPopup(buildPopup(e), { maxWidth: 300 });
    markers[e.id] = marker;
    markerCluster.addLayer(marker);
  });

  updateSidebar(expenses, summary);
}

function updateSidebar(expenses, summary) {
  document.getElementById('total-amount').textContent = `$${summary.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  document.getElementById('expense-count').textContent = `${summary.count} transactions`;
  document.getElementById('deductible-amount').textContent = `$${summary.tax_deductible.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  document.getElementById('savings-amount').textContent = `Est. $${summary.potential_savings.toLocaleString('en-US', { minimumFractionDigits: 0 })} savings`;

  // Pending badge
  if (summary.pending_count > 0) {
    document.getElementById('pending-badge').textContent = summary.pending_count;
    document.getElementById('pending-badge').classList.remove('hidden');
  } else {
    document.getElementById('pending-badge').classList.add('hidden');
  }

  const maxVal = Math.max(...Object.values(summary.by_category), 1);
  document.getElementById('category-list').innerHTML = Object.entries(summary.by_category).map(([cat, amt]) => {
    const color = CATEGORY_COLORS[cat] || '#6b7280';
    return `<div class="category-row"><div style="flex:1">
      <div style="display:flex;justify-content:space-between">
        <span class="category-name" style="color:${color}">${cat}</span>
        <span class="category-amount">$${amt.toLocaleString()}</span>
      </div>
      <div class="category-bar-wrap"><div class="category-bar" style="width:${(amt/maxVal)*100}%;background:${color}"></div></div>
    </div></div>`;
  }).join('');

  document.getElementById('expense-list').innerHTML = expenses.map(e => {
    const date = new Date(e.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const statusDot = e.status === 'pending' ? '🟡 ' : e.status === 'rejected' ? '🔴 ' : '';
    return `<div class="expense-item" onclick="flyTo(${e.id},${e.latitude},${e.longitude})">
      <div class="expense-left">
        <div class="expense-title">${statusDot}${e.title}</div>
        <div class="expense-meta">${e.vendor} · ${date}</div>
      </div>
      <div class="expense-right">
        <div class="expense-amount">$${e.amount.toFixed(2)}</div>
        ${e.tax_deductible ? '<span class="deductible-badge">✓ Deductible</span>' : '<span class="non-deductible-badge">✗ No</span>'}
      </div></div>`;
  }).join('');
}

function flyTo(id, lat, lng) {
  map.flyTo([lat, lng], 14, { duration: 1.2 });
  setTimeout(() => markers[id]?.openPopup(), 1300);
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openModal() {
  editingId = null;
  document.getElementById('modal-title-text').textContent = 'Add Expense';
  document.getElementById('submit-text').textContent = '✨ Add with AI';
  document.getElementById('modal-overlay').classList.remove('hidden');
  setTimeout(() => document.getElementById('f-title').focus(), 50);
}

function openEditModal(id) {
  const e = expenseCache[id];
  if (!e) return;
  editingId = id;

  document.getElementById('modal-title-text').textContent = 'Edit Expense';
  document.getElementById('submit-text').textContent = 'Save Changes';
  document.getElementById('f-title').value = e.title;
  document.getElementById('f-amount').value = e.amount;
  document.getElementById('f-vendor').value = e.vendor;
  document.getElementById('f-lat').value = e.latitude;
  document.getElementById('f-lng').value = e.longitude;
  document.getElementById('f-city').value = e.city;
  document.getElementById('modal-address').textContent = e.city;

  document.getElementById('modal-overlay').classList.remove('hidden');
  setTimeout(() => document.getElementById('f-title').focus(), 50);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('expense-form').reset();
  document.getElementById('receipt-preview').classList.add('hidden');
  document.getElementById('receipt-preview-img').src = '';
  document.getElementById('f-receipt-url').value = '';
  editingId = null;
  if (pendingMarker) { map.removeLayer(pendingMarker); pendingMarker = null; }
  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }
}

async function submitExpense(e) {
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  const text = document.getElementById('submit-text');
  const spinner = document.getElementById('submit-spinner');
  btn.disabled = true; text.classList.add('hidden'); spinner.classList.remove('hidden');

  const payload = {
    title: document.getElementById('f-title').value,
    amount: parseFloat(document.getElementById('f-amount').value),
    vendor: document.getElementById('f-vendor').value,
    city: document.getElementById('f-city').value || 'Unknown',
    latitude: parseFloat(document.getElementById('f-lat').value),
    longitude: parseFloat(document.getElementById('f-lng').value),
    receipt_url: document.getElementById('f-receipt-url').value || null,
  };

  try {
    let res;
    if (editingId) {
      res = await Auth.apiFetch(`/api/expenses/${editingId}`, {
        method: 'PUT', body: JSON.stringify(payload),
      });
    } else {
      res = await Auth.apiFetch('/api/expenses', {
        method: 'POST', body: JSON.stringify(payload),
      });
    }
    if (res.ok) {
      closeModal();
      await loadExpenses();
      if (!editingId) {
        const newest = Object.values(expenseCache).sort((a, b) => b.id - a.id)[0];
        if (newest) flyTo(newest.id, newest.latitude, newest.longitude);
      }
    }
  } finally {
    btn.disabled = false; text.classList.remove('hidden'); spinner.classList.add('hidden');
  }
}

// ── Receipt upload ────────────────────────────────────────────────────────────

async function handleReceiptUpload(input) {
  const file = input.files[0];
  if (!file) return;

  const preview = document.getElementById('receipt-preview');
  const img = document.getElementById('receipt-preview-img');
  img.src = URL.createObjectURL(file);
  preview.classList.remove('hidden');

  const uploadBtn = document.getElementById('receipt-upload-btn');
  uploadBtn.textContent = '⏳ Scanning…';
  uploadBtn.disabled = true;

  try {
    const form = new FormData();
    form.append('file', file);
    const res = await Auth.apiFetch('/api/receipts/extract', { method: 'POST', body: form });
    if (res.ok) {
      const { receipt_url, extracted } = await res.json();
      document.getElementById('f-receipt-url').value = receipt_url;
      if (extracted.vendor) document.getElementById('f-vendor').value = extracted.vendor;
      if (extracted.amount) document.getElementById('f-amount').value = extracted.amount;
      if (extracted.title) document.getElementById('f-title').value = extracted.title;
      if (extracted.city) {
        document.getElementById('f-city').value = extracted.city;
        document.getElementById('modal-address').textContent = extracted.city;
      }
      uploadBtn.textContent = '✓ Receipt scanned';
    }
  } catch (err) {
    uploadBtn.textContent = '📎 Upload Receipt';
    console.error(err);
  } finally {
    uploadBtn.disabled = false;
  }
}

// ── Expense actions ───────────────────────────────────────────────────────────

window.deleteExpense = async (id) => {
  if (!confirm('Delete this expense?')) return;
  const res = await Auth.apiFetch(`/api/expenses/${id}`, { method: 'DELETE' });
  if (res.ok) { map.closePopup(); await loadExpenses(); }
};

window.approveExpense = async (id) => {
  const res = await Auth.apiFetch(`/api/expenses/${id}/approve`, { method: 'PATCH' });
  if (res.ok) { map.closePopup(); await loadExpenses(); }
};

window.rejectExpense = async (id) => {
  const note = prompt('Reason for rejection (optional):') || '';
  const res = await Auth.apiFetch(`/api/expenses/${id}/reject`, {
    method: 'PATCH', body: JSON.stringify({ note }),
  });
  if (res.ok) { map.closePopup(); await loadExpenses(); }
};

window.openEditModal = openEditModal;

// ── Export ────────────────────────────────────────────────────────────────────

async function exportCSV() {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  const a = document.createElement('a');
  a.href = `/api/expenses/export/csv?${params}`;
  // Use fetch to add auth header, then trigger download via blob
  const res = await Auth.apiFetch(`/api/expenses/export/csv?${params}`);
  const blob = await res.blob();
  a.href = URL.createObjectURL(blob);
  a.download = 'expenses.csv';
  a.click();
}

// ── User menu ─────────────────────────────────────────────────────────────────

function toggleUserMenu() {
  document.getElementById('user-dropdown').classList.toggle('hidden');
}

document.addEventListener('click', e => {
  if (!document.getElementById('user-menu-wrap')?.contains(e.target)) {
    document.getElementById('user-dropdown')?.classList.add('hidden');
  }
});

async function copyInviteLink() {
  const res = await Auth.apiFetch('/api/company/invite', {
    method: 'POST', body: JSON.stringify({ role: 'member' }),
  });
  if (res.ok) {
    const { invite_token } = await res.json();
    const link = `${location.origin}/login?invite=${invite_token}`;
    navigator.clipboard.writeText(link);
    alert('Invite link copied to clipboard!');
  }
}
