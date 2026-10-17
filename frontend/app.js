const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let toastTimer;
function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('visible'), 3200);
}
window.toast = toast;

function parseCSV(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') { cell += '"'; index += 1; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ',') { row.push(cell); cell = ''; }
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[index + 1] === '\n') index += 1;
      row.push(cell);
      if (row.some(value => value.trim() !== '')) rows.push(row);
      row = [];
      cell = '';
    } else cell += char;
  }
  if (cell.length || row.length) {
    row.push(cell);
    if (row.some(value => value.trim() !== '')) rows.push(row);
  }
  return rows;
}

function renderCSV(rows, filename) {
  const count = Math.max(0, rows.length - 1);
  $('#dataset-name').textContent = filename.replace(/\.csv$/i, '').replace(/[_-]+/g, ' ');
  $('.dataset-meta span:nth-child(2)').textContent = filename;
  $('#row-count').textContent = `${count.toLocaleString()} rows`;
  const footer = $('.page-footer b');
  if (footer) footer.textContent = `${count.toLocaleString()} records`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

const fileInput = $('#file-input');
$('#browse-btn').addEventListener('click', () => fileInput.click());
$('.tiny-plus').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files?.[0]) window.loadFile(fileInput.files[0]);
  fileInput.value = '';
});
const uploadZone = $('#upload-zone');
uploadZone.addEventListener('dragover', event => { event.preventDefault(); uploadZone.classList.add('dragging'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragging'));
uploadZone.addEventListener('drop', event => {
  event.preventDefault();
  uploadZone.classList.remove('dragging');
  if (event.dataTransfer.files?.[0]) window.loadFile(event.dataTransfer.files[0]);
});

const modal = $('#chat-modal');
function openChat(question = '') {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  setTimeout(() => {
    if (question) window.sendMessage(question);
    else $('#chat-input').focus();
  }, 80);
}
function closeChat() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
$('#ask-btn').addEventListener('click', () => openChat());
$('#close-chat').addEventListener('click', closeChat);
modal.addEventListener('click', event => { if (event.target === modal) closeChat(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeChat(); });

const themeButton = $('#theme-toggle');
if (localStorage.getItem('pivot-theme') === 'dark') document.body.dataset.theme = 'dark';
function refreshThemeControl() {
  const dark = document.body.dataset.theme === 'dark';
  themeButton.innerHTML = `<span class="theme-icon">${dark ? '☼' : '◐'}</span><span>${dark ? 'Light mode' : 'Dark mode'}</span>`;
  themeButton.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
}
refreshThemeControl();
themeButton.addEventListener('click', () => {
  document.body.dataset.theme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('pivot-theme', document.body.dataset.theme);
  refreshThemeControl();
});

$$('.nav-item').forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  $$('.nav-item').forEach(item => item.classList.remove('active'));
  link.classList.add('active');
  if (link.getAttribute('href') === '#datasets') $('#datasets').scrollIntoView({ behavior: 'smooth' });
  else if (link.getAttribute('href') === '#reports') $('#artifact-downloads').scrollIntoView({ behavior: 'smooth' });
  else window.scrollTo({ top: 0, behavior: 'smooth' });
}));
$('.help-button').addEventListener('click', () => toast('Choose the included sample or mark an upload as sample/public before analysis. Private data is blocked.'));

window.parseCSV = parseCSV;
window.renderCSV = renderCSV;
window.escapeHtml = escapeHtml;
window.openPivotChat = openChat;
