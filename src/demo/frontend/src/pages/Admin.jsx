import { useState, useEffect, useCallback, useRef } from 'react';
import {
    socket,
    adminLogin,
    adminLogout,
    gateOverride,
    getBadges,
    addBadge,
    removeBadge,
    getCameras,
    getCamera,
    getEvents,
    getAllGateStatus,
    setLockdown,
    getLockdownStatus,
} from '../api';

// ─── Styles ────────────────────────────────────────────────────────────────────
const S = {
    page: {
        minHeight: '100vh',
        background: '#1a1a2e',
        color: '#e0e0e0',
        fontFamily: "'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        padding: '0 0 40px',
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '18px 32px',
        background: '#16213e',
        borderBottom: '1px solid #0f3460',
    },
    headerTitle: { margin: 0, fontSize: '1.4rem', fontWeight: 600, letterSpacing: '.5px' },
    backLink: {
        color: '#4cc9f0',
        textDecoration: 'none',
        fontWeight: 500,
        fontSize: '.95rem',
    },
    main: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 24,
        padding: '24px 32px',
        alignItems: 'flex-start',
    },
    card: {
        background: '#16213e',
        border: '1px solid #0f3460',
        borderRadius: 12,
        padding: '20px 24px',
        flex: '1 1 400px',
        boxShadow: '0 4px 20px rgba(0,0,0,.35)',
    },
    cardFull: {
        background: '#16213e',
        border: '1px solid #0f3460',
        borderRadius: 12,
        padding: '20px 24px',
        flex: '1 1 100%',
        boxShadow: '0 4px 20px rgba(0,0,0,.35)',
    },
    cardTitle: { margin: '0 0 16px', fontSize: '1.15rem', fontWeight: 600, color: '#4cc9f0' },
    btn: {
        padding: '8px 18px',
        border: 'none',
        borderRadius: 8,
        cursor: 'pointer',
        fontWeight: 600,
        fontSize: '.85rem',
        transition: 'opacity .2s',
        color: '#fff',
    },
    btnPrimary: { background: '#3a86ff' },
    btnSuccess: { background: '#06d6a0' },
    btnDanger: { background: '#ef476f' },
    btnSmall: { padding: '5px 12px', fontSize: '.8rem' },
    btnRow: { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 10 },
    input: {
        padding: '8px 12px',
        borderRadius: 8,
        border: '1px solid #0f3460',
        background: '#0d1b3e',
        color: '#e0e0e0',
        fontSize: '.85rem',
        width: 200,
    },
    inputWide: {
        padding: '10px 14px',
        borderRadius: 8,
        border: '1px solid #0f3460',
        background: '#0d1b3e',
        color: '#e0e0e0',
        fontSize: '.95rem',
        width: '100%',
        boxSizing: 'border-box',
    },
    loginBox: {
        maxWidth: 380,
        margin: '80px auto',
        background: '#16213e',
        border: '1px solid #0f3460',
        borderRadius: 12,
        padding: '32px 28px',
        boxShadow: '0 4px 20px rgba(0,0,0,.35)',
    },
    loginTitle: {
        margin: '0 0 24px',
        fontSize: '1.3rem',
        fontWeight: 600,
        color: '#4cc9f0',
        textAlign: 'center',
    },
    loginField: { marginBottom: 14 },
    loginLabel: { display: 'block', marginBottom: 4, fontSize: '.85rem', color: '#aaa' },
    errorMsg: { color: '#ef476f', fontSize: '.85rem', marginTop: 8, textAlign: 'center' },
    gateSection: {
        marginBottom: 16,
        padding: 16,
        background: '#1a1a2e',
        borderRadius: 10,
        border: '1px solid #0f346066',
    },
    gateSectionTitle: { margin: '0 0 10px', fontSize: '.95rem', fontWeight: 600 },
    gateStatusRow: {
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        marginBottom: 10,
        flexWrap: 'wrap',
    },
    statusChip: (active, color) => ({
        padding: '3px 12px',
        borderRadius: 20,
        fontSize: '.8rem',
        fontWeight: 600,
        background: active ? `${color}33` : '#33333366',
        color: active ? color : '#888',
        border: `1px solid ${active ? color : '#555'}`,
    }),
    badgeList: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        margin: '12px 0',
    },
    badgePill: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 14px',
        background: '#0f3460',
        borderRadius: 20,
        fontSize: '.85rem',
        fontWeight: 500,
        border: '1px solid #3a86ff44',
    },
    badgeRemoveBtn: {
        background: 'none',
        border: 'none',
        color: '#ef476f',
        cursor: 'pointer',
        fontWeight: 700,
        fontSize: '.95rem',
        padding: 0,
        lineHeight: 1,
    },
    cameraSelector: {
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        marginBottom: 16,
    },
    cameraBtn: (active) => ({
        padding: '6px 14px',
        borderRadius: 8,
        border: active ? '1px solid #4cc9f0' : '1px solid #333',
        background: active ? '#0f3460' : 'transparent',
        color: active ? '#4cc9f0' : '#aaa',
        cursor: 'pointer',
        fontWeight: 600,
        fontSize: '.82rem',
        transition: 'all .2s',
    }),
    cameraFeed: {
        position: 'relative',
        borderRadius: 10,
        overflow: 'hidden',
        background: '#111',
        minHeight: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    cameraImg: {
        width: '100%',
        maxHeight: 360,
        objectFit: 'cover',
        display: 'block',
        borderRadius: 10,
    },
    cameraOverlay: {
        position: 'absolute',
        top: 10,
        left: 12,
        display: 'flex',
        gap: 8,
        alignItems: 'center',
    },
    cameraStatusDot: (online) => ({
        width: 10,
        height: 10,
        borderRadius: '50%',
        background: online ? '#06d6a0' : '#ef476f',
        boxShadow: online ? '0 0 8px #06d6a0' : '0 0 8px #ef476f',
    }),
    cameraLabel: {
        fontSize: '.8rem',
        fontWeight: 600,
        background: 'rgba(0,0,0,.6)',
        padding: '3px 10px',
        borderRadius: 6,
    },
    noFeed: {
        color: '#666',
        fontSize: '.95rem',
        padding: '40px 0',
        textAlign: 'center',
    },
    table: {
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '.85rem',
    },
    th: {
        textAlign: 'left',
        padding: '8px 12px',
        borderBottom: '1px solid #333',
        color: '#4cc9f0',
        fontWeight: 600,
        position: 'sticky',
        top: 0,
        background: '#16213e',
    },
    td: {
        padding: '7px 12px',
        borderBottom: '1px solid #1e1e3a',
        color: '#ccc',
    },
    scrollBox: {
        maxHeight: 300,
        overflowY: 'auto',
        borderRadius: 8,
        border: '1px solid #333',
    },
    msg: {
        marginTop: 6,
        fontSize: '.8rem',
        fontWeight: 500,
        minHeight: '1.2em',
    },
};

// ─── Helpers ───────────────────────────────────────────────────────────────────
function formatTime(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        return d.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return ts;
    }
}

// ─── TV Static canvas ───────────────────────────────────────────────────────────
function StaticCanvas() {
    const canvasRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let rafId;
        function draw() {
            const w = canvas.width;
            const h = canvas.height;
            const imageData = ctx.createImageData(w, h);
            const data = imageData.data;
            for (let i = 0; i < data.length; i += 4) {
                const v = (Math.random() * 255) | 0;
                data[i] = v;
                data[i + 1] = v;
                data[i + 2] = v;
                data[i + 3] = 255;
            }
            ctx.putImageData(imageData, 0, 0);
            // Scanline overlay for CRT feel
            ctx.fillStyle = 'rgba(0,0,0,0.18)';
            for (let y = 0; y < h; y += 3) {
                ctx.fillRect(0, y, w, 1);
            }
            // Vertical roll ghost
            const ghost = (Date.now() / 18) % h;
            const grad = ctx.createLinearGradient(0, ghost, 0, ghost + 40);
            grad.addColorStop(0, 'rgba(255,255,255,0)');
            grad.addColorStop(0.5, 'rgba(255,255,255,0.07)');
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, ghost, w, 40);
            // NO SIGNAL text
            ctx.font = 'bold 25px monospace';
            ctx.fillStyle = 'rgba(255,255,255,0.75)';
            ctx.textAlign = 'center';
            ctx.fillText('NO SIGNAL', w / 2, h / 2 + 9);
            // ctx.font = '11px monospace';
            // ctx.fillStyle = 'rgba(200,200,200,0.5)';
            // ctx.fillText('NO FEED AVAILABLE', w / 2, h / 2 + 10);
            rafId = requestAnimationFrame(draw);
        }
        draw();
        return () => cancelAnimationFrame(rafId);
    }, []);
    return (
        <canvas
            ref={canvasRef}
            width={480}
            height={270}
            style={{ width: '100%', height: '100%', minHeight: 200, display: 'block', borderRadius: 10 }}
        />
    );
}

// ─── Event type display helpers ──────────────────────────────────────────────
const EVT_LABEL = {
    Entry: { label: 'Entry', color: '#06d6a0' },
    Entry_Denied: { label: 'Entry Denied', color: '#ef476f' },
    Exit: { label: 'Exit', color: '#f77f00' },
    Exit_VehicleDetected: { label: 'Exit Detected', color: '#c9a84c' },
    AdminLogin: { label: 'Admin Login', color: '#4cc9f0' },
    AdminGateOverride: { label: 'Gate Override', color: '#4cc9f0' },
    Lockdown: { label: 'Lockdown', color: '#ef476f' },
    BadgeAdded: { label: 'Badge Added', color: '#4cc9f0' },
    BadgeRemoved: { label: 'Badge Removed', color: '#c9a84c' },
    PowerFailure: { label: 'Power Failure', color: '#ef476f' },
    PowerRestored: { label: 'Power Restored', color: '#06d6a0' },
};

function evtLabel(type) {
    return EVT_LABEL[type]?.label ?? type;
}
function evtColor(type) {
    return EVT_LABEL[type]?.color ?? '#aaa';
}
function evtDetails(evt) {
    if (!evt.details || Object.keys(evt.details).length === 0) return '—';
    return Object.entries(evt.details)
        .map(([k, v]) => `${k}: ${v}`)
        .join(' · ');
}

// ─── Component ─────────────────────────────────────────────────────────────────
export default function Admin() {
    // Auth
    const [token, setToken] = useState(null);
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('admin');
    const [loginError, setLoginError] = useState('');
    const [loggingIn, setLoggingIn] = useState(false);

    // Gate overrides
    const [gates, setGates] = useState({});
    const [gateMsg, setGateMsg] = useState({ 1: '', 2: '' });

    // Lockdown
    const [lockdown, setLockdownState] = useState(false);

    // Badges
    const [badges, setBadges] = useState([]);
    const [newBadgeUid, setNewBadgeUid] = useState('');
    const [badgeMsg, setBadgeMsg] = useState('');

    // CCTV
    const [cameras, setCameras] = useState([]);
    const [selectedCam, setSelectedCam] = useState(null);
    const [camDetail, setCamDetail] = useState(null);
    const [camImgError, setCamImgError] = useState(false);

    // Events
    const [events, setEvents] = useState([]);

    // ── Auth handlers ────────────────────────────────────────
    const handleLogin = useCallback(async () => {
        setLoggingIn(true);
        setLoginError('');
        try {
            const res = await adminLogin(username, password);
            if (res._error || !res.token) {
                setLoginError(res._status === 401 ? 'Invalid credentials' : (res.error || 'Login failed'));
            } else {
                setToken(res.token);
            }
        } catch {
            setLoginError('Connection error');
        } finally {
            setLoggingIn(false);
        }
    }, [username, password]);

    const handleLogout = useCallback(async () => {
        if (token) {
            await adminLogout(token);
        }
        setToken(null);
        setGates({});
        setBadges([]);
        setCameras([]);
        setSelectedCam(null);
        setCamDetail(null);
        setEvents([]);
    }, [token]);

    // ── Fetch helpers ────────────────────────────────────────
    const fetchEvents = useCallback(async () => {
        if (!token) return;
        const res = await getEvents(token);
        if (!res._error && res.events) setEvents(res.events);
    }, [token]);

    const fetchGates = useCallback(async () => {
        const res = await getAllGateStatus();
        if (!res._error) setGates(res);
    }, []);

    const fetchBadges = useCallback(async () => {
        if (!token) return;
        const res = await getBadges(token);
        if (!res._error && res.badges) setBadges(res.badges);
    }, [token]);

    const fetchCameras = useCallback(async () => {
        if (!token) return;
        const res = await getCameras(token);
        if (!res._error && res.cameras) setCameras(res.cameras);
    }, [token]);

    const fetchLockdown = useCallback(async () => {
        const res = await getLockdownStatus();
        if (!res._error) setLockdownState(!!res.lockdown);
    }, []);

    // ── Init on login ────────────────────────────────────────
    useEffect(() => {
        if (!token) return;
        fetchGates();
        fetchBadges();
        fetchCameras();
        fetchEvents();
        fetchLockdown();
    }, [token, fetchGates, fetchBadges, fetchCameras, fetchEvents, fetchLockdown]);

    // ── WebSocket: subscribe to database state events ────────
    useEffect(() => {
        function onGateUpdate(data) {
            if (data.gate_id === undefined) return;
            const gid = String(data.gate_id);
            setGates((prev) => ({
                ...prev,
                [gid]: { ...prev[gid], ...data },
            }));
        }
        function onLockdownUpdate(data) {
            setLockdownState(!!data.active);
        }

        socket.on('gate_update', onGateUpdate);
        socket.on('lockdown_update', onLockdownUpdate);
        return () => {
            socket.off('gate_update', onGateUpdate);
            socket.off('lockdown_update', onLockdownUpdate);
        };
    }, []);

    // ── Gate override handlers ───────────────────────────────
    const handleGateOverride = useCallback(async (gateId, override, state) => {
        const res = await gateOverride(token, gateId, override, state);
        if (res._error) {
            setGateMsg((p) => ({ ...p, [gateId]: res.error || 'Error' }));
        } else {
            const label = !override ? 'Override disabled' : state ? 'Forced OPEN' : 'Forced CLOSED';
            setGateMsg((p) => ({ ...p, [gateId]: label }));
            fetchEvents(); // events don't have a WebSocket push — poll after action
        }
        setTimeout(() => setGateMsg((p) => ({ ...p, [gateId]: '' })), 3000);
    }, [token, fetchEvents]);

    // ── Lockdown handler ─────────────────────────────────────
    const handleLockdown = useCallback(async (enabled) => {
        const res = await setLockdown(token, enabled);
        if (res._error) {
            console.error('Lockdown error:', res.error);
        }
        fetchEvents();
    }, [token, fetchEvents]);

    // ── Badge handlers ───────────────────────────────────────
    const handleAddBadge = useCallback(async () => {
        const uid = newBadgeUid.trim();
        if (!uid) return;
        const res = await addBadge(token, uid);
        if (res._error) {
            setBadgeMsg(res.error || 'Error adding badge');
        } else {
            if (res.badges) setBadges(res.badges);
            setNewBadgeUid('');
            setBadgeMsg('Badge added');
            fetchEvents();
        }
        setTimeout(() => setBadgeMsg(''), 3000);
    }, [token, newBadgeUid, fetchEvents]);

    const handleRemoveBadge = useCallback(async (uid) => {
        const res = await removeBadge(token, uid);
        if (res._error) {
            setBadgeMsg(res.error || 'Error removing badge');
        } else {
            if (res.badges) setBadges(res.badges);
            setBadgeMsg('Badge removed');
            fetchEvents();
        }
        setTimeout(() => setBadgeMsg(''), 3000);
    }, [token, fetchEvents]);

    // ── Camera handlers ──────────────────────────────────────
    const handleSelectCamera = useCallback(async (id) => {
        setSelectedCam(id);
        setCamImgError(false);
        setCamDetail(null);
        const res = await getCamera(token, id);
        if (!res._error) {
            setCamDetail(res);
        }
    }, [token]);

    // ── Login screen ─────────────────────────────────────────
    if (!token) {
        return (
            <div style={S.page}>
                <header style={S.header}>
                    <h1 style={S.headerTitle}>Parking Structure &mdash; Admin</h1>
                    <a href="/" style={S.backLink}>&larr; Back to Dashboard</a>
                </header>
                <div style={S.loginBox}>
                    <h2 style={S.loginTitle}>Admin Login</h2>
                    <div style={S.loginField}>
                        <label style={S.loginLabel}>Username</label>
                        <input
                            style={S.inputWide}
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                            autoFocus
                        />
                    </div>
                    <div style={S.loginField}>
                        <label style={S.loginLabel}>Password</label>
                        <input
                            style={S.inputWide}
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                        />
                    </div>
                    <button
                        style={{ ...S.btn, ...S.btnPrimary, width: '100%', marginTop: 8, padding: '10px 0' }}
                        onClick={handleLogin}
                        disabled={loggingIn}
                    >
                        {loggingIn ? 'Logging in…' : 'Login'}
                    </button>
                    {loginError && <p style={S.errorMsg}>{loginError}</p>}
                </div>
            </div>
        );
    }

    // ── Admin dashboard ──────────────────────────────────────
    const gateEntries = [
        { id: 1, label: 'Entry Gate' },
        { id: 2, label: 'Exit Gate' },
    ];

    return (
        <div style={S.page}>
            {/* ── Header ─────────────────────────────────── */}
            <header style={S.header}>
                <h1 style={S.headerTitle}>Parking Structure &mdash; Admin Panel</h1>
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                    <a href="/" style={S.backLink}>&larr; Back to Dashboard</a>
                    <button style={{ ...S.btn, ...S.btnDanger }} onClick={handleLogout}>
                        Logout
                    </button>
                </div>
            </header>

            <div style={S.main}>
                {/* ── Gate Override Controls ────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>Gate Override Controls</h2>

                    {gateEntries.map(({ id, label }) => {
                        const gate = gates[id] || gates[String(id)] || {};
                        const isOpen = gate.open ?? false;
                        const overrideActive = gate.override ?? false;

                        return (
                            <div key={id} style={S.gateSection}>
                                <h3 style={S.gateSectionTitle}>{label} (ID {id})</h3>
                                <div style={S.gateStatusRow}>
                                    <span style={S.statusChip(isOpen, '#06d6a0')}>
                                        {isOpen ? 'OPEN' : 'CLOSED'}
                                    </span>
                                    <span style={S.statusChip(overrideActive, '#f77f00')}>
                                        {overrideActive ? 'OVERRIDE ACTIVE' : 'No Override'}
                                    </span>
                                </div>
                                <div style={S.btnRow}>
                                    <button
                                        style={{ ...S.btn, ...S.btnSuccess, ...S.btnSmall }}
                                        onClick={() => handleGateOverride(id, true, true)}
                                    >
                                        Force Open
                                    </button>
                                    <button
                                        style={{ ...S.btn, ...S.btnDanger, ...S.btnSmall }}
                                        onClick={() => handleGateOverride(id, true, false)}
                                    >
                                        Force Closed
                                    </button>
                                    <button
                                        style={{ ...S.btn, ...S.btnPrimary, ...S.btnSmall }}
                                        onClick={() => handleGateOverride(id, false, false)}
                                    >
                                        Disable Override
                                    </button>
                                </div>
                                {gateMsg[id] && (
                                    <div
                                        style={{
                                            ...S.msg,
                                            color: gateMsg[id].includes('OPEN') ? '#06d6a0'
                                                : gateMsg[id].includes('CLOSED') ? '#ef476f'
                                                    : '#aaa',
                                        }}
                                    >
                                        {gateMsg[id]}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* ── Lockdown Control ─────────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>Facility Lockdown</h2>
                    <div style={S.gateSection}>
                        <div style={S.gateStatusRow}>
                            <span style={S.statusChip(lockdown, '#ef476f')}>
                                {lockdown ? '🔒 LOCKDOWN ACTIVE' : '🟢 Normal Operation'}
                            </span>
                        </div>
                        <p style={{ fontSize: '.85rem', color: '#888', margin: '8px 0 12px' }}>
                            Lockdown prevents all vehicles from exiting the facility.
                        </p>
                        <div style={S.btnRow}>
                            <button
                                style={{ ...S.btn, ...(lockdown ? S.btnSuccess : S.btnDanger) }}
                                onClick={() => handleLockdown(!lockdown)}
                            >
                                {lockdown ? 'Disable Lockdown' : 'Enable Lockdown'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* ── Badge Management ─────────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>Badge Management</h2>

                    <div style={S.badgeList}>
                        {badges.length === 0 && (
                            <span style={{ color: '#666', fontSize: '.85rem' }}>No badges registered</span>
                        )}
                        {badges.map((uid) => (
                            <span key={uid} style={S.badgePill}>
                                {uid}
                                <button
                                    style={S.badgeRemoveBtn}
                                    onClick={() => handleRemoveBadge(uid)}
                                    title={`Remove ${uid}`}
                                >
                                    &times;
                                </button>
                            </span>
                        ))}
                    </div>

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
                        <input
                            style={S.input}
                            placeholder="New badge UID"
                            value={newBadgeUid}
                            onChange={(e) => setNewBadgeUid(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleAddBadge()}
                        />
                        <button style={{ ...S.btn, ...S.btnSuccess }} onClick={handleAddBadge}>
                            Add Badge
                        </button>
                    </div>

                    {badgeMsg && (
                        <div
                            style={{
                                ...S.msg,
                                color: badgeMsg.includes('added') ? '#06d6a0'
                                    : badgeMsg.includes('removed') ? '#f77f00'
                                        : '#ef476f',
                            }}
                        >
                            {badgeMsg}
                        </div>
                    )}
                </div>

                {/* ── CCTV Viewer ──────────────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>CCTV Viewer</h2>

                    <div style={S.cameraSelector}>
                        {cameras.length === 0 && (
                            <span style={{ color: '#666', fontSize: '.85rem' }}>No cameras available</span>
                        )}
                        {cameras.map((cam) => (
                            <button
                                key={cam.id}
                                style={S.cameraBtn(selectedCam === cam.id)}
                                onClick={() => handleSelectCamera(cam.id)}
                            >
                                {cam.name || `Camera ${cam.id}`}
                                {cam.location ? ` — ${cam.location}` : ''}
                            </button>
                        ))}
                    </div>

                    {camDetail ? (
                        <div>
                            <div style={S.cameraFeed}>
                                {!camImgError && camDetail.feed_url ? (
                                    <img
                                        src={camDetail.feed_url}
                                        alt={camDetail.name}
                                        style={S.cameraImg}
                                        onError={() => setCamImgError(true)}
                                    />
                                ) : (
                                    <StaticCanvas />
                                )}
                                <div style={S.cameraOverlay}>
                                    <div style={S.cameraStatusDot(camDetail.status === 'online')} />
                                    <span style={S.cameraLabel}>
                                        {camDetail.name} &mdash; {camDetail.location}
                                    </span>
                                </div>
                            </div>
                            <div style={{ marginTop: 8, fontSize: '.82rem', color: '#888' }}>
                                Status: <strong style={{ color: camDetail.status === 'online' ? '#06d6a0' : '#ef476f' }}>
                                    {camDetail.status?.toUpperCase() || 'UNKNOWN'}
                                </strong>
                            </div>
                        </div>
                    ) : selectedCam ? (
                        <div style={S.noFeed}>Loading camera…</div>
                    ) : (
                        <div style={S.noFeed}>Select a camera to view its feed</div>
                    )}
                </div>

                {/* ── Event Log ────────────────────────────── */}
                <div style={S.cardFull}>
                    <h2 style={S.cardTitle}>
                        Event Log
                        <button
                            style={{ ...S.btn, ...S.btnPrimary, ...S.btnSmall, marginLeft: 12 }}
                            onClick={fetchEvents}
                        >
                            Refresh
                        </button>
                    </h2>

                    <div style={S.scrollBox}>
                        <table style={S.table}>
                            <thead>
                                <tr>
                                    <th style={S.th}>Time</th>
                                    <th style={S.th}>Type</th>
                                    <th style={S.th}>Gate</th>
                                    <th style={S.th}>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {events.length === 0 && (
                                    <tr>
                                        <td style={{ ...S.td, color: '#666' }} colSpan={4}>
                                            No events recorded
                                        </td>
                                    </tr>
                                )}
                                {events.map((evt, i) => (
                                    <tr key={evt.id ?? i}>
                                        <td style={S.td}>{formatTime(evt.timestamp)}</td>
                                        <td style={S.td}>
                                            <span style={{ color: evtColor(evt.type), fontWeight: 600 }}>
                                                {evtLabel(evt.type)}
                                            </span>
                                        </td>
                                        <td style={S.td}>{evt.gate_id ?? '—'}</td>
                                        <td style={S.td}>{evtDetails(evt)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
