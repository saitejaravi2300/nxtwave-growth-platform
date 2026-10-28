
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

const api = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });

  const data = await response.json().catch(() => ({
    detail: 'Unexpected server response.'
  }));

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed. Please try again.');
  }

  return data;
};

const authHeaders = () => ({
  Authorization: `Bearer ${sessionStorage.getItem('growth_token') || ''}`
});

// Navigation and scrolling
document.querySelectorAll('[data-scroll]').forEach(btn => {
  btn.addEventListener('click', () => {
    $('#' + btn.dataset.scroll)?.scrollIntoView({
      behavior: 'smooth'
    });
  });
});

$('.menu-toggle')?.addEventListener('click', () => {
  $('nav')?.classList.toggle('open');
});

$$('nav a').forEach(a => {
  a.addEventListener('click', () => $('nav')?.classList.remove('open'));
});

// Referral link handling
const params = new URLSearchParams(location.search);
const ref = params.get('ref');

if (ref && $('#referral-code')) {
  $('#referral-code').value = ref.toUpperCase();
}

// Public workshop configuration
api('/api/public-config')
  .then(config => {
    const dateElement = $('#workshop-date');

    if (dateElement) {
      dateElement.textContent = `${config.date} · ${config.mode}`;
    }

    document.title = `${config.title} | NxtWave`;
  })
  .catch(err => {
    console.error('Could not load public configuration:', err);
  });

// Student registration
$('#registration-form')?.addEventListener('submit', async e => {
  e.preventDefault();

  const form = e.currentTarget;
  const message = $('#form-message');
  const button = $('.btn-submit', form);

  message.classList.remove('error');
  message.textContent = 'Submitting your registration…';

  if (button) button.disabled = true;

  const fd = new FormData(form);
  const payload = Object.fromEntries(fd.entries());

  payload.graduation_year = Number(payload.graduation_year);
  payload.source = ref ? 'referral' : 'website';
  payload.referral_code =
    (payload.referral_code || '').trim().toUpperCase() || null;

  try {
    const result = await api('/api/register', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    message.textContent =
      `✓ ${result.message} Your reference number is #${result.registration_id}.`;

    form.reset();

    if (ref && $('#referral-code')) {
      $('#referral-code').value = ref.toUpperCase();
    }
  } catch (err) {
    message.textContent = err.message;
    message.classList.add('error');
  } finally {
    if (button) button.disabled = false;
  }
});

// Admin modal
const modal = $('#admin-modal');

$('#open-admin')?.addEventListener('click', () => {
  if (!modal) return;

  modal.hidden = false;
  document.body.style.overflow = 'hidden';
});

$('#close-admin')?.addEventListener('click', closeModal);

modal?.addEventListener('click', e => {
  if (e.target === modal) closeModal();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

function closeModal() {
  if (!modal) return;

  modal.hidden = true;
  document.body.style.overflow = '';
}

// Admin login
$('#login-form')?.addEventListener('submit', async e => {
  e.preventDefault();

  const form = e.currentTarget;
  const msg = $('#login-message');

  msg.textContent = 'Signing in…';
  msg.classList.remove('error');

  const payload = Object.fromEntries(new FormData(form).entries());

  try {
    const data = await api('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    sessionStorage.setItem('growth_token', data.access_token);

    form.hidden = true;
    $('#admin-panel').hidden = false;

    await loadAdmin();
  } catch (err) {
    msg.textContent = err.message;
    msg.classList.add('error');
  }
});

// Load admin data
async function loadAdmin() {
  const [overview, registrations, ambassadors] = await Promise.all([
    api('/api/admin/overview', {
      headers: authHeaders()
    }),
    api('/api/admin/registrations', {
      headers: authHeaders()
    }),
    api('/api/admin/ambassadors', {
      headers: authHeaders()
    })
  ]);

  $('#admin-metrics').innerHTML = `
    <div class="metric">
      <span>Total registrations</span>
      <b>${overview.total_registrations}</b>
    </div>
    <div class="metric">
      <span>Today's registrations</span>
      <b>${overview.today}</b>
    </div>
    <div class="metric">
      <span>Target remaining</span>
      <b>${overview.remaining}</b>
    </div>
  `;

  renderRegistrations(registrations);
  renderAmbassadors(ambassadors);

  const search = $('#registration-search');

  if (search) {
    search.oninput = async e => {
      try {
        const rows = await api(
          '/api/admin/registrations?q=' +
            encodeURIComponent(e.target.value),
          { headers: authHeaders() }
        );

        renderRegistrations(rows);
      } catch (err) {
        showAdminError(err);
      }
    };
  }
}

// Escape user-provided text before inserting it into HTML
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}

// Render registrations
function renderRegistrations(rows) {
  const tbody = $('#registration-rows');

  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML =
      '<tr><td colspan="4">No registrations found yet.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>
        ${escapeHtml(r.full_name)}
        <br>
        <span class="muted">${escapeHtml(r.email)}</span>
      </td>
      <td>${escapeHtml(r.college)}</td>
      <td>${escapeHtml(r.source)}</td>
      <td>
        ${r.created_at
          ? escapeHtml(new Date(r.created_at).toLocaleString())
          : ''}
      </td>
    </tr>
  `).join('');
}

// Render ambassadors
function renderAmbassadors(rows) {
  const list = $('#ambassador-list');

  if (!list) return;

  list.innerHTML = rows.length
    ? '<h3>Ambassadors and referral codes</h3>' +
      rows.map(a => `
        <div class="ambassador-row">
          <span>
            <b>${escapeHtml(a.name)}</b>
            <br>
            <span class="muted">
              ${escapeHtml(a.college)} · ${a.referrals} referrals
            </span>
          </span>
          <code>${escapeHtml(a.code)}</code>
        </div>
      `).join('')
    : '<p class="muted">No ambassadors added yet.</p>';
}

function showAdminError(err) {
  const message = $('#login-message');

  if (!message) {
    console.error(err);
    return;
  }

  message.textContent = err.message;
  message.classList.add('error');
}

// Export registrations as CSV
$('#export-csv')?.addEventListener('click', async () => {
  let objectUrl;

  try {
    const response = await fetch('/api/admin/export.csv', {
      headers: authHeaders()
    });

    if (!response.ok) {
      throw new Error('Could not export registrations.');
    }

    const blob = await response.blob();
    objectUrl = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = 'registrations.csv';

    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (err) {
    showAdminError(err);
  } finally {
    if (objectUrl) {
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }
  }
});

// Create ambassador and referral code
$('#ambassador-form')?.addEventListener('submit', async e => {
  e.preventDefault();

  // IMPORTANT: Save the form before awaiting the API request.
  const form = e.currentTarget;
  const msg = $('#ambassador-result');

  msg.textContent = 'Creating code…';
  msg.classList.remove('error');

  const submitButton = form.querySelector(
    'button[type="submit"], input[type="submit"]'
  );

  if (submitButton) submitButton.disabled = true;

  try {
    const payload = Object.fromEntries(
      new FormData(form).entries()
    );

    const created = await api('/api/admin/ambassadors', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    });

    msg.textContent =
      `Created referral code ${created.code}. ` +
      `Share a registration link ending in ?ref=${created.code}`;

    // Fixed: use the saved form reference, not e.currentTarget.
    form.reset();

    await loadAdmin();
  } catch (err) {
    msg.textContent = err.message;
    msg.classList.add('error');
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
});

// Admin logout
$('#logout-admin')?.addEventListener('click', () => {
  sessionStorage.removeItem('growth_token');

  const panel = $('#admin-panel');
  const loginForm = $('#login-form');
  const loginMessage = $('#login-message');

  if (panel) panel.hidden = true;

  if (loginForm) {
    loginForm.hidden = false;
    loginForm.reset();
  }

  if (loginMessage) {
    loginMessage.textContent = 'Signed out.';
    loginMessage.classList.remove('error');
  }
});
