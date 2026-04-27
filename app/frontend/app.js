const API = '';
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
let markers = {}, pendingMarker = null, searchPin = null, expenseCache = {};
let searchDebounce = null;

// ── Map init ─────────────────────────────────────────────────────────────────

function initMap() {
  map = L.map('map', { zoomControl: true }).setView([39.5, -98.35], 4);

  streetLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
  });

  satelliteLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: '© Esri, Maxar, Earthstar Geographics', maxZoom: 19 }
  );

  streetLayer.addTo(map);

  map.on('click', onMapClick);
  loadExpenses();
}

function toggleLayer() {
  const btn = document.getElementById('layer-toggle');
  if (isSatellite) {
    map.removeLayer(satelliteLayer);
    streetLayer.addTo(map);
    btn.textContent = '🛰 Satellite';
    btn.classList.remove('active');
  } else {
    map.removeLayer(streetLayer);
    satelliteLayer.addTo(map);
    btn.textContent = '🗺 Map';
    btn.classList.add('active');
  }
  isSatellite = !isSatellite;
}

// ── Map click → reverse geocode → modal ──────────────────────────────────────

async function onMapClick(e) {
  const { lat, lng } = e.latlng;

  if (pendingMarker) map.removeLayer(pendingMarker);
  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }
  pendingMarker = L.circleMarker([lat, lng], {
    radius: 10,
    color: '#6366f1',
    weight: 2,
    fillColor: '#6366f1',
    fillOpacity: 0.3,
  }).addTo(map);

  document.getElementById('f-lat').value = lat;
  document.getElementById('f-lng').value = lng;
  document.getElementById('f-city').value = '';
  document.getElementById('modal-address').textContent = 'Detecting location…';
  openModal();

  try {
    const res = await fetch(
      `${NOMINATIM}/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: NOMINATIM_HEADERS }
    );
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

// ── Search ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('search-input');
  const clearBtn = document.getElementById('search-clear');

  input.addEventListener('input', () => {
    const q = input.value.trim();
    clearBtn.classList.toggle('hidden', !q);
    clearTimeout(searchDebounce);
    if (q.length < 2) return hideResults();
    searchDebounce = setTimeout(() => runSearch(q), 400);
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') clearSearch();
  });

  document.addEventListener('click', e => {
    if (!document.getElementById('search-container').contains(e.target)) hideResults();
  });

  initMap();
});

async function runSearch(q) {
  try {
    const params = new URLSearchParams({
      q,
      format: 'json',
      limit: 6,
      addressdetails: 1,
      namedetails: 1,
      'accept-language': 'en',
    });
    const res = await fetch(`${NOMINATIM}/search?${params}`, { headers: NOMINATIM_HEADERS });
    const results = await res.json();
    showResults(results);
  } catch {
    hideResults();
  }
}

function formatSub(r) {
  const a = r.address || {};
  const parts = [];
  // Specific place → show its street/road context
  if (a.road) parts.push(a.road);
  // Always include city then state
  const city = a.city || a.town || a.village || a.suburb || a.county;
  if (city) parts.push(city);
  const state = a.state;
  if (state) parts.push(state);
  const country = a.country;
  if (country && country !== 'United States') parts.push(country);
  return parts.join(', ') || r.display_name.split(',').slice(1, 4).join(',').trim();
}

function showResults(results) {
  const box = document.getElementById('search-results');
  if (!results.length) {
    box.innerHTML = '<div class="search-no-results">No places found</div>';
    box.classList.remove('hidden');
    return;
  }
  box.innerHTML = results.map((r, i) => {
    const icon = placeIcon(r.type, r.class);
    // Use namedetails or first part of display_name for the main label
    const main = (r.namedetails && r.namedetails.name) || r.display_name.split(',')[0];
    const sub = formatSub(r);
    return `<div class="search-result" onclick="selectResult(${i})">
      <span class="search-result-icon">${icon}</span>
      <div>
        <div class="search-result-main">${main}</div>
        <div class="search-result-sub">${sub}</div>
      </div>
    </div>`;
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

  const lat = parseFloat(r.lat);
  const lng = parseFloat(r.lon);
  const bbox = r.boundingbox;

  // Remove any previous search pin
  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }

  // Drop a pin at the exact result location
  searchPin = L.marker([lat, lng], { icon: makeSearchPinIcon() }).addTo(map);

  const sub = formatSub(r);
  searchPin.bindPopup(
    `<div style="padding:12px;font-family:-apple-system,sans-serif;min-width:180px">
      <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:2px">${placeName}</div>
      <div style="font-size:11px;color:#94a3b8;margin-bottom:10px">${sub}</div>
      <button onclick="addExpenseAtSearchPin(${lat},${lng},'${placeName.replace(/'/g, "\\'")}','${sub.replace(/'/g, "\\'")}')"
        style="width:100%;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border:none;
               padding:8px 12px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer">
        + Add Expense Here
      </button>
    </div>`,
    { maxWidth: 240 }
  ).openPopup();

  if (bbox) {
    map.fitBounds(
      [[parseFloat(bbox[0]), parseFloat(bbox[2])], [parseFloat(bbox[1]), parseFloat(bbox[3])]],
      { maxZoom: 16, animate: true, duration: 1 }
    );
  } else {
    map.setView([lat, lng], 16, { animate: true, duration: 1 });
  }
}

function makeSearchPinIcon() {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:0;height:0;
      border-left:10px solid transparent;
      border-right:10px solid transparent;
      border-top:0;
      border-bottom:28px solid #6366f1;
      filter:drop-shadow(0 2px 4px rgba(99,102,241,0.5));
      position:relative;top:-28px
    "></div>
    <div style="
      width:8px;height:8px;
      background:#6366f1;border-radius:50%;
      position:relative;top:-28px;left:6px;
      margin-top:-4px
    "></div>`,
    iconSize: [20, 32],
    iconAnchor: [10, 32],
    popupAnchor: [0, -34],
  });
}

window.addExpenseAtSearchPin = function(lat, lng, placeName, address) {
  document.getElementById('f-lat').value = lat;
  document.getElementById('f-lng').value = lng;

  // Extract city from address string (first segment before first comma)
  const city = address.split(',')[0].trim() || placeName;
  document.getElementById('f-city').value = city;
  document.getElementById('modal-address').textContent = address || placeName;

  if (searchPin) searchPin.closePopup();
  openModal();
};

function hideResults() {
  document.getElementById('search-results').classList.add('hidden');
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear').classList.add('hidden');
  hideResults();
}

function placeIcon(type, cls) {
  if (cls === 'amenity' || type === 'restaurant' || type === 'cafe') return '🍽️';
  if (cls === 'highway' || type === 'motorway') return '🛣️';
  if (type === 'airport') return '✈️';
  if (cls === 'railway' || type === 'station') return '🚉';
  if (type === 'hotel' || type === 'motel') return '🏨';
  if (cls === 'building' || cls === 'office') return '🏢';
  if (cls === 'natural' || cls === 'water') return '🌊';
  if (type === 'park' || cls === 'leisure') return '🌳';
  if (cls === 'place' || cls === 'boundary') return '📍';
  return '📍';
}

// ── Expense markers ──────────────────────────────────────────────────────────

function makeMarkerIcon(category, amount) {
  const color = CATEGORY_COLORS[category] || '#6b7280';
  const size = amount > 500 ? 36 : amount > 100 ? 28 : 22;
  return L.divIcon({
    className: '',
    html: `<div style="
      width:${size}px;height:${size}px;
      background:${color};border:2px solid white;border-radius:50%;
      box-shadow:0 2px 8px rgba(0,0,0,0.5);
      display:flex;align-items:center;justify-content:center;
      font-size:${Math.round(size * 0.38)}px;color:white;font-weight:700
    ">$</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function buildPopup(e) {
  const date = new Date(e.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const deductLabel = e.tax_deductible
    ? `<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">✓ Tax Deductible</span>`
    : `<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">✗ Not Deductible</span>`;
  const aiNote = e.ai_note
    ? `<div style="font-size:11px;color:#64748b;border-top:1px solid #f1f5f9;padding-top:8px;margin-top:8px;line-height:1.5">
         <span style="color:#7c3aed;font-weight:600">✨ AI:</span> ${e.ai_note}
       </div>` : '';
  return `<div style="padding:14px;min-width:230px;font-family:-apple-system,sans-serif">
    <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:3px">${e.title}</div>
    <div style="font-size:12px;color:#94a3b8;margin-bottom:8px">${e.vendor} · ${e.city}</div>
    <div style="font-size:22px;font-weight:700;color:#2563eb;margin-bottom:8px">$${e.amount.toFixed(2)}</div>
    <span style="background:#eff6ff;color:#1d4ed8;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600">${e.category}</span>
    <span style="margin-left:6px">${deductLabel}</span>
    <div style="font-size:11px;color:#94a3b8;margin-top:8px">${date}</div>
    ${aiNote}
  </div>`;
}

// ── Data loading ─────────────────────────────────────────────────────────────

async function loadExpenses() {
  const [expRes, sumRes] = await Promise.all([
    fetch(`${API}/api/expenses`),
    fetch(`${API}/api/expenses/summary`),
  ]);
  const expenses = await expRes.json();
  const summary = await sumRes.json();

  expenseCache = Object.fromEntries(expenses.map(e => [e.id, e]));

  Object.values(markers).forEach(m => map.removeLayer(m));
  markers = {};

  expenses.forEach(e => {
    const marker = L.marker([e.latitude, e.longitude], { icon: makeMarkerIcon(e.category, e.amount) })
      .addTo(map)
      .bindPopup(buildPopup(e), { maxWidth: 280 });
    markers[e.id] = marker;
  });

  updateSidebar(expenses, summary);
}

function updateSidebar(expenses, summary) {
  document.getElementById('total-amount').textContent =
    `$${summary.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  document.getElementById('expense-count').textContent = `${summary.count} transactions`;
  document.getElementById('deductible-amount').textContent =
    `$${summary.tax_deductible.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  document.getElementById('savings-amount').textContent =
    `Est. $${summary.potential_savings.toLocaleString('en-US', { minimumFractionDigits: 0 })} savings`;

  const categoryList = document.getElementById('category-list');
  categoryList.innerHTML = '';
  const maxVal = Math.max(...Object.values(summary.by_category));
  Object.entries(summary.by_category).forEach(([cat, amt]) => {
    const color = CATEGORY_COLORS[cat] || '#6b7280';
    const pct = (amt / maxVal) * 100;
    categoryList.innerHTML += `
      <div class="category-row">
        <div style="flex:1">
          <div style="display:flex;justify-content:space-between">
            <span class="category-name" style="color:${color}">${cat}</span>
            <span class="category-amount">$${amt.toLocaleString()}</span>
          </div>
          <div class="category-bar-wrap">
            <div class="category-bar" style="width:${pct}%;background:${color}"></div>
          </div>
        </div>
      </div>`;
  });

  const expenseList = document.getElementById('expense-list');
  expenseList.innerHTML = '';
  expenses.forEach(e => {
    const date = new Date(e.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    expenseList.innerHTML += `
      <div class="expense-item" onclick="flyTo(${e.id}, ${e.latitude}, ${e.longitude})">
        <div class="expense-left">
          <div class="expense-title">${e.title}</div>
          <div class="expense-meta">${e.vendor} · ${date}</div>
        </div>
        <div class="expense-right">
          <div class="expense-amount">$${e.amount.toFixed(2)}</div>
          ${e.tax_deductible
            ? '<span class="deductible-badge">✓ Deductible</span>'
            : '<span class="non-deductible-badge">✗ No</span>'}
        </div>
      </div>`;
  });
}

function flyTo(id, lat, lng) {
  map.flyTo([lat, lng], 14, { duration: 1.2 });
  setTimeout(() => markers[id]?.openPopup(), 1300);
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openModal() {
  document.getElementById('modal-overlay').classList.remove('hidden');
  setTimeout(() => document.getElementById('f-title').focus(), 50);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('expense-form').reset();
  if (pendingMarker) { map.removeLayer(pendingMarker); pendingMarker = null; }
  if (searchPin) { map.removeLayer(searchPin); searchPin = null; }
}

async function submitExpense(e) {
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  const text = document.getElementById('submit-text');
  const spinner = document.getElementById('submit-spinner');
  btn.disabled = true;
  text.classList.add('hidden');
  spinner.classList.remove('hidden');

  const payload = {
    title:     document.getElementById('f-title').value,
    amount:    parseFloat(document.getElementById('f-amount').value),
    vendor:    document.getElementById('f-vendor').value,
    city:      document.getElementById('f-city').value || 'Unknown',
    latitude:  parseFloat(document.getElementById('f-lat').value),
    longitude: parseFloat(document.getElementById('f-lng').value),
  };

  try {
    const res = await fetch(`${API}/api/expenses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeModal();
      await loadExpenses();
      const newest = Object.values(expenseCache).sort((a, b) => b.id - a.id)[0];
      if (newest) flyTo(newest.id, newest.latitude, newest.longitude);
    }
  } finally {
    btn.disabled = false;
    text.classList.remove('hidden');
    spinner.classList.add('hidden');
  }
}
