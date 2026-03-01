/**
 * API helper for the Parking Structure backend.
 * All calls go through the Vite proxy (same origin).
 */

const BASE = '';

async function request(method, path, body = null, token = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${BASE}${path}`, opts);
    const data = await res.json();
    if (!res.ok) return { ...data, _status: res.status, _error: true };
    return { ...data, _status: res.status, _error: false };
}

// ── Global status ──────────────────────────────────────────
export const getStatus = () => request('GET', '/status');

// ── Gate ───────────────────────────────────────────────────
export const getGateStatus = (id) => request('GET', `/gate/status/${id}`);
export const getAllGateStatus = () => request('GET', '/gate/status');
export const vehicleDetected = (gateId, active) =>
    request('POST', '/gate/vehicle-detected', { gate_id: gateId, active });
export const vehicleEntered = (gateId, active) =>
    request('POST', '/gate/vehicle-entered', { gate_id: gateId, active });
export const rfidScan = (gateId, badgeUid) =>
    request('POST', '/gate/rfid-scan', { gate_id: gateId, badge_uid: badgeUid });

// ── Parking ────────────────────────────────────────────────
export const getOccupancy = () => request('GET', '/parking/occupancy');
export const getFloor = (floorId) => request('GET', `/parking/floor/${floorId}`);
export const spotUpdate = (spotId, occupied) =>
    request('POST', '/parking/spot-update', { spot_id: spotId, occupied });

// ── Admin ──────────────────────────────────────────────────
export const adminLogin = (username, password) =>
    request('POST', '/admin/login', { username, password });
export const adminLogout = (token) =>
    request('POST', '/admin/logout', null, token);

export const gateOverride = (token, gateId, override, state) =>
    request('POST', '/admin/gate-override', { gate_id: gateId, override, state }, token);

export const getBadges = (token) => request('GET', '/admin/badges', null, token);
export const addBadge = (token, badgeUid) =>
    request('POST', '/admin/badges', { badge_uid: badgeUid }, token);
export const removeBadge = (token, uid) =>
    request('DELETE', `/admin/badges/${uid}`, null, token);

export const getCameras = (token) => request('GET', '/admin/cctv', null, token);
export const getCamera = (token, id) =>
    request('GET', `/admin/cctv/${id}`, null, token);

export const getEvents = (token, limit = 50) =>
    request('GET', `/admin/events?limit=${limit}`, null, token);
