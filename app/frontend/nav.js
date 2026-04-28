// Shared navigation — injected into every page
const Nav = (() => {
  function init(activePage) {
    const user = Auth.getUser();
    if (!user) return;

    const isAdmin = ['owner', 'admin'].includes(user.role);

    const nav = document.getElementById('nav');
    if (!nav) return;

    nav.innerHTML = `
      <div class="nav-brand">
        <span>📍</span>
        <div>
          <div class="nav-brand-name">GeoExpense</div>
          <div class="nav-brand-company">${esc(user.company_name || '')}</div>
        </div>
      </div>
      <div class="nav-links">
        <a href="/" class="nav-link ${activePage === 'map' ? 'active' : ''}">🗺 Map</a>
        ${isAdmin ? `<a href="/approvals" class="nav-link ${activePage === 'approvals' ? 'active' : ''}" id="nav-approvals">⏳ Approvals</a>` : ''}
        ${isAdmin ? `<a href="/members" class="nav-link ${activePage === 'members' ? 'active' : ''}">👥 Members</a>` : ''}
        <a href="/profile" class="nav-link ${activePage === 'profile' ? 'active' : ''}">👤 Profile</a>
      </div>
      <button class="nav-signout" onclick="Auth.logout()">Sign Out</button>
    `;

    // Load pending count for admins
    if (isAdmin) {
      Auth.apiFetch('/api/expenses/summary').then(r => r.json()).then(s => {
        if (s.pending_count > 0) {
          const el = document.getElementById('nav-approvals');
          if (el) el.innerHTML += ` <span class="nav-badge">${s.pending_count}</span>`;
        }
      }).catch(() => {});
    }
  }

  return { init };
})();

function esc(s) {
  return (s == null ? '' : String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
}
