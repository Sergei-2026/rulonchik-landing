/* ── Helpers ─────────────────────────────────────────────────────── */

const API = "";

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function fmt(amount) {
  if (amount == null) return "—";
  const sign = amount >= 0 ? "" : "−";
  return sign + Math.abs(amount).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " ₽";
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" })
       + " " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function delta(val) {
  if (val == null) return '<span class="delta-neu">—</span>';
  const cls = val > 0 ? "delta-pos" : val < 0 ? "delta-neg" : "delta-neu";
  const sign = val > 0 ? "▲" : val < 0 ? "▼" : "";
  return `<span class="${cls}">${sign}${Math.abs(val)}%</span>`;
}

let toastTimer;
function toast(msg, type = "") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast" + (type ? " " + type : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.add("hidden"); }, 3000);
}

/* ── Navigation ──────────────────────────────────────────────────── */

document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + tab).classList.add("active");
    if (tab === "dashboard")    loadDashboard();
    if (tab === "transactions") loadTransactions();
    if (tab === "reports")      { loadMonthly(); loadBreakdown(); }
    if (tab === "categories")   loadCategories();
  });
});

/* ── Modals ──────────────────────────────────────────────────────── */

document.querySelectorAll("[data-modal]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.getElementById(btn.dataset.modal).classList.add("hidden");
  });
});

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

/* ── DASHBOARD ───────────────────────────────────────────────────── */

async function loadDashboard() {
  const now = new Date();
  document.getElementById("dashDate").textContent =
    now.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });

  try {
    const d = await api("/api/reports/dashboard");

    document.getElementById("todayIncome").textContent  = fmt(d.today_income);
    document.getElementById("todayExpense").textContent = fmt(d.today_expense);
    const tp = document.getElementById("todayProfit");
    tp.textContent = fmt(d.today_profit);
    tp.style.color = d.today_profit >= 0 ? "var(--green)" : "var(--red)";

    document.getElementById("monthIncome").textContent  = fmt(d.month_income);
    document.getElementById("monthExpense").textContent = fmt(d.month_expense);
    const mp = document.getElementById("monthProfit");
    mp.textContent = fmt(d.month_profit);
    mp.style.color = d.month_profit >= 0 ? "var(--green)" : "var(--red)";

    const fv = document.getElementById("forecastValue");
    if (d.forecast_end_of_month != null) {
      fv.textContent = fmt(d.forecast_end_of_month);
      fv.style.color = d.forecast_end_of_month >= 0 ? "var(--green)" : "var(--red)";
    } else {
      document.getElementById("forecastBlock").style.display = "none";
    }
  } catch (e) {
    toast("Ошибка загрузки дашборда: " + e.message, "error");
  }

  // Recent 10 transactions
  try {
    const txs = await api("/api/transactions/?limit=10");
    const tbody = document.getElementById("recentBody");
    tbody.innerHTML = txs.map(renderTxRow).join("");
  } catch (e) { /* silent */ }
}

function renderTxRow(tx, showDelete = false) {
  const typeLabel = tx.type === "income"
    ? '<span class="badge badge-income">Приход</span>'
    : '<span class="badge badge-expense">Расход</span>';
  const amountClass = tx.type === "income" ? "amount-income" : "amount-expense";
  const sourceLabel = tx.source === "tbank"
    ? '<span class="badge badge-tbank">Т-Банк</span>'
    : '<span class="badge badge-manual">Вручную</span>';
  const del = showDelete
    ? `<button class="btn-icon" onclick="deleteTx(${tx.id})">✕</button>`
    : "";
  return `<tr>
    <td>${fmtDate(tx.transaction_date)}</td>
    <td>${typeLabel}</td>
    <td>${tx.category || "—"}</td>
    <td class="${amountClass}">${fmt(tx.amount)}</td>
    <td>${tx.description || "—"}</td>
    ${showDelete ? `<td>${sourceLabel}</td><td>${del}</td>` : ""}
  </tr>`;
}

/* ── TRANSACTIONS ────────────────────────────────────────────────── */

async function loadTransactions(params = {}) {
  const qs = new URLSearchParams(params).toString();
  try {
    const txs = await api("/api/transactions/?" + qs + "&limit=200");
    const tbody = document.getElementById("txBody");
    tbody.innerHTML = txs.length
      ? txs.map(tx => renderTxRow(tx, true)).join("")
      : '<tr><td colspan="7" style="text-align:center;color:var(--text-2);padding:2rem">Нет операций</td></tr>';
  } catch (e) {
    toast("Ошибка загрузки операций: " + e.message, "error");
  }
}

document.getElementById("btnFilter").addEventListener("click", () => {
  const params = {};
  const from = document.getElementById("filterFrom").value;
  const to   = document.getElementById("filterTo").value;
  const type = document.getElementById("filterType").value;
  if (from) params.date_from = from + "T00:00:00";
  if (to)   params.date_to   = to   + "T23:59:59";
  if (type) params.type      = type;
  loadTransactions(params);
});

window.deleteTx = async function(id) {
  if (!confirm("Удалить операцию?")) return;
  try {
    await api(`/api/transactions/${id}`, { method: "DELETE" });
    toast("Операция удалена", "success");
    loadTransactions();
    loadDashboard();
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
};

/* ── Add Transaction Modal ────────────────────────────────────────── */

let allCategories = [];

document.getElementById("btnAddTx").addEventListener("click", async () => {
  allCategories = await api("/api/categories/");
  populateCategorySelect();
  // Default datetime = now
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  document.getElementById("txDate").value = now.toISOString().slice(0, 16);
  document.getElementById("txAmount").value = "";
  document.getElementById("txDescription").value = "";
  openModal("modalTx");
});

document.getElementById("txType").addEventListener("change", populateCategorySelect);

function populateCategorySelect() {
  const type = document.getElementById("txType").value;
  const sel  = document.getElementById("txCategory");
  const cats = allCategories.filter(c => c.type === type);
  sel.innerHTML = cats.map(c => `<option value="${c.name}">${c.name}</option>`).join("");
}

document.getElementById("btnSaveTx").addEventListener("click", async () => {
  const amount = parseFloat(document.getElementById("txAmount").value);
  if (!amount || amount <= 0) { toast("Введите сумму", "error"); return; }

  const body = {
    type: document.getElementById("txType").value,
    amount,
    category: document.getElementById("txCategory").value || null,
    description: document.getElementById("txDescription").value || null,
    transaction_date: document.getElementById("txDate").value || null,
  };

  try {
    await api("/api/transactions/", { method: "POST", body: JSON.stringify(body) });
    document.getElementById("modalTx").classList.add("hidden");
    toast("Операция добавлена", "success");
    loadTransactions();
    loadDashboard();
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
});

/* ── REPORTS ─────────────────────────────────────────────────────── */

async function loadMonthly() {
  try {
    const rows = await api("/api/reports/monthly?months=6");
    const tbody = document.getElementById("reportBody");
    tbody.innerHTML = rows.map(r => `<tr>
      <td><strong>${r.month}</strong></td>
      <td class="amount-income">${fmt(r.income)}</td>
      <td class="amount-expense">${fmt(r.expense)}</td>
      <td style="color:${r.profit >= 0 ? 'var(--green)' : 'var(--red)'};font-weight:600">${fmt(r.profit)}</td>
      <td>${delta(r.income_change)}</td>
      <td>${delta(r.expense_change)}</td>
      <td>${delta(r.profit_change)}</td>
    </tr>`).join("");
  } catch (e) {
    toast("Ошибка загрузки отчёта: " + e.message, "error");
  }
}

async function loadBreakdown() {
  try {
    const rows = await api("/api/reports/expenses-breakdown");
    const tbody = document.getElementById("breakdownBody");
    tbody.innerHTML = rows.length
      ? rows.map(r => `<tr>
          <td>${r.category}</td>
          <td class="amount-expense">${fmt(r.amount)}</td>
          <td>
            <div style="display:flex;align-items:center;gap:.5rem">
              <div style="background:var(--red-light);border-radius:4px;height:8px;width:${r.percent}px;max-width:120px;min-width:4px;background:var(--red);opacity:.6"></div>
              ${r.percent}%
            </div>
          </td>
        </tr>`).join("")
      : '<tr><td colspan="3" style="text-align:center;color:var(--text-2);padding:1.5rem">Нет расходов за этот месяц</td></tr>';
  } catch (e) { /* silent */ }
}

/* ── CATEGORIES ──────────────────────────────────────────────────── */

async function loadCategories() {
  try {
    const cats = await api("/api/categories/");
    const expenses = cats.filter(c => c.type === "expense");
    const incomes  = cats.filter(c => c.type === "income");
    document.getElementById("catExpenseList").innerHTML = expenses.map(renderCatItem).join("");
    document.getElementById("catIncomeList").innerHTML  = incomes.map(renderCatItem).join("");
  } catch (e) {
    toast("Ошибка загрузки категорий: " + e.message, "error");
  }
}

function renderCatItem(cat) {
  const defaultMark = cat.is_default ? '<span class="cat-default">стандартная</span>' : "";
  const editBtn  = `<button class="btn-edit" onclick="editCat(${cat.id},'${cat.name.replace(/'/g,"\\'")}')">✎</button>`;
  const delBtn   = cat.is_default
    ? ""
    : `<button class="btn-icon" onclick="deleteCat(${cat.id})">✕</button>`;
  return `<li class="cat-item">
    <span class="cat-name">${cat.name}${defaultMark}</span>
    <div class="cat-actions">${editBtn}${delBtn}</div>
  </li>`;
}

let editingCatId = null;

document.getElementById("btnAddCat").addEventListener("click", () => {
  editingCatId = null;
  document.getElementById("modalCatTitle").textContent = "Новая категория";
  document.getElementById("catName").value = "";
  document.getElementById("catType").value = "expense";
  openModal("modalCat");
});

window.editCat = function(id, name) {
  editingCatId = id;
  document.getElementById("modalCatTitle").textContent = "Редактировать категорию";
  document.getElementById("catName").value = name;
  openModal("modalCat");
};

document.getElementById("btnSaveCat").addEventListener("click", async () => {
  const name = document.getElementById("catName").value.trim();
  if (!name) { toast("Введите название", "error"); return; }

  try {
    if (editingCatId) {
      await api(`/api/categories/${editingCatId}`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      });
      toast("Категория обновлена", "success");
    } else {
      await api("/api/categories/", {
        method: "POST",
        body: JSON.stringify({ name, type: document.getElementById("catType").value }),
      });
      toast("Категория добавлена", "success");
    }
    document.getElementById("modalCat").classList.add("hidden");
    loadCategories();
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
});

window.deleteCat = async function(id) {
  if (!confirm("Удалить категорию?")) return;
  try {
    await api(`/api/categories/${id}`, { method: "DELETE" });
    toast("Категория удалена", "success");
    loadCategories();
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
};

/* ── T-Bank sync button ───────────────────────────────────────────── */

document.getElementById("btnSync").addEventListener("click", async () => {
  const btn = document.getElementById("btnSync");
  btn.textContent = "Синхронизация...";
  btn.disabled = true;
  try {
    const res = await api("/api/tbank/sync", { method: "POST" });
    toast(res.message, "success");
    loadDashboard();
  } catch (e) {
    toast("Ошибка синхронизации: " + e.message, "error");
  } finally {
    btn.textContent = "Синхронизировать с Т-Банком";
    btn.disabled = false;
  }
});

/* ── Init ────────────────────────────────────────────────────────── */
loadDashboard();
