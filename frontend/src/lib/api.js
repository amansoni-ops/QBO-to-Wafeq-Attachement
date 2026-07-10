const BASE = import.meta.env.BASE_URL.replace(/\/$/, "")

async function jf(path, opt = {}) {
  const r = await fetch(BASE + path, { credentials: "include", ...opt })
  const ct = r.headers.get("content-type") || ""
  const d = ct.includes("json") ? await r.json() : await r.text()
  if (!r.ok) throw new Error((d && d.error) || r.statusText || "Request failed")
  return d
}
function jpost(path, body) {
  return jf(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  })
}

export const api = {
  me: () => jf("/api/auth/me"),
  login: (username, password) => jpost("/api/auth/login", { username, password }),
  logout: () => jpost("/api/auth/logout", {}),
  changePassword: (old_password, new_password) =>
    jpost("/api/auth/change-password", { old_password, new_password }),

  companies: () => jf("/api/companies"),
  deleteCompany: (rid) => jf("/api/companies/" + rid, { method: "DELETE" }),
  authUrl: () => jf("/api/qbo/auth-url"),
  testQbo: (rid) => jf("/api/qbo/test/" + rid),

  saveKey: (realm_id, api_key, key_name, set_active = true) =>
    jpost("/api/wafeq/key", { realm_id, api_key, key_name, set_active }),
  activateKey: (realm_id, key_id) => jpost("/api/wafeq/key/activate", { realm_id, key_id }),
  deleteKey: (realm_id, key_id) => jpost("/api/wafeq/key/delete", { realm_id, key_id }),
  testWafeq: (rid) => jf("/api/wafeq/test/" + rid),

  index: (rid) => jf("/api/index/" + rid),
  report: (rid) => jf("/api/report/" + rid),
  manualMatch: (realm_id, qb_bill_id, wafeq_bill_id, wafeq_type) =>
    jpost("/api/manual-match", { realm_id, qb_bill_id, wafeq_bill_id, wafeq_type }),

  fetchUrl: (rid, params = {}) => BASE + "/api/fetch/" + rid + qs(params),
  matchUrl: (rid, params = {}) => BASE + "/api/match/" + rid + qs(params),
  uploadUrl: (rid, params = {}) => BASE + "/api/upload/" + rid + qs(params),

  exportXlsxUrl: (rid) => BASE + "/api/export/" + rid,
  reportXlsxUrl: (rid) => BASE + "/api/report/" + rid + "?format=xlsx",

  adminUsers: () => jf("/api/admin/users"),
  createUser: (username, password, role) => jpost("/api/admin/users", { username, password, role }),
  resetPassword: (target, new_password) =>
    jpost("/api/admin/users/" + target + "/reset-password", { new_password }),
  deleteUser: (target) => jf("/api/admin/users/" + target, { method: "DELETE" }),
  auditLog: (limit = 500, user) =>
    jf("/api/admin/audit?limit=" + limit + (user ? "&user=" + encodeURIComponent(user) : "")),
  adminReport: () => jf("/api/admin/report"),
}

function qs(params) {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v)
  })
  const s = p.toString()
  return s ? "?" + s : ""
}
