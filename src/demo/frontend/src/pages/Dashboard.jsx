import { useState, useEffect, useCallback, useRef } from 'react';
import {
    socket,
    getStatus,
    getOccupancy,
    vehicleDetected,
    vehicleEntered,
    rfidScan,
    spotUpdate,
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
    adminLink: {
        color: '#4cc9f0',
        textDecoration: 'none',
        fontWeight: 500,
        fontSize: '.95rem',
    },
    statusBar: {
        display: 'flex',
        gap: 24,
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px 32px',
        background: '#0f3460',
        flexWrap: 'wrap',
    },
    statusChip: {
        padding: '4px 14px',
        borderRadius: 20,
        fontSize: '.85rem',
        fontWeight: 600,
        letterSpacing: '.3px',
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
    cardTitle: { margin: '0 0 16px', fontSize: '1.15rem', fontWeight: 600, color: '#4cc9f0' },
    gateSection: {
        marginBottom: 20,
        padding: 16,
        background: '#1a1a2e',
        borderRadius: 10,
        border: '1px solid #0f346066',
    },
    gateSectionTitle: { margin: '0 0 12px', fontSize: '.95rem', fontWeight: 600 },
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
    // Sensor-active state: lit amber to indicate the sensor is currently HIGH
    btnSensorOn: { background: '#f77f00', boxShadow: '0 0 8px #f77f0066' },
    btnRow: { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 10 },
    input: {
        padding: '8px 12px',
        borderRadius: 8,
        border: '1px solid #0f3460',
        background: '#0d1b3e',
        color: '#e0e0e0',
        fontSize: '.85rem',
        width: 120,
    },
    gateArm: {
        position: 'relative',
        width: 100,
        height: 60,
        margin: '8px 0',
    },
    gatePost: {
        position: 'absolute',
        bottom: 0,
        left: 10,
        width: 10,
        height: 50,
        background: '#555',
        borderRadius: 3,
    },
    gateBar: (open) => ({
        position: 'absolute',
        bottom: 40,
        left: 15,
        width: 70,
        height: 6,
        background: open ? '#06d6a0' : '#ef476f',
        borderRadius: 3,
        transformOrigin: '0% 50%',
        transform: open ? 'rotate(-80deg)' : 'rotate(0deg)',
        transition: 'transform .5s ease, background .3s',
    }),
    rfidIndicator: (state) => ({
        width: 22,
        height: 22,
        borderRadius: '50%',
        display: 'inline-block',
        marginLeft: 10,
        verticalAlign: 'middle',
        transition: 'background .3s',
        background:
            state === 'valid' ? '#06d6a0' : state === 'invalid' ? '#ef476f' : '#555',
        boxShadow:
            state === 'valid'
                ? '0 0 10px #06d6a0'
                : state === 'invalid'
                    ? '0 0 10px #ef476f'
                    : 'none',
    }),
    floorTabs: { display: 'flex', gap: 6, marginBottom: 14 },
    floorTab: (active) => ({
        padding: '6px 18px',
        borderRadius: '8px 8px 0 0',
        border: 'none',
        cursor: 'pointer',
        fontWeight: 600,
        fontSize: '.85rem',
        color: active ? '#fff' : '#aaa',
        background: active ? '#0f3460' : 'transparent',
    }),
    spotGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 44px)',
        gap: 6,
    },
    spot: (occupied) => ({
        width: 44,
        height: 44,
        borderRadius: 8,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        fontSize: '.65rem',
        fontWeight: 600,
        userSelect: 'none',
        transition: 'background .2s, box-shadow .2s',
        background: occupied ? '#3d1f2f' : '#133b2e',
        color: occupied ? '#ef476f' : '#06d6a0',
        border: occupied ? '1px solid #ef476f55' : '1px solid #06d6a055',
        boxShadow: occupied ? 'none' : '0 0 6px #06d6a033',
    }),
    led: (on) => ({
        width: 6,
        height: 6,
        borderRadius: '50%',
        marginTop: 2,
        background: on ? '#06d6a0' : '#333',
        boxShadow: on ? '0 0 4px #06d6a0' : 'none',
    }),
    floorSummary: { margin: '10px 0 0', fontSize: '.85rem', fontWeight: 500 },
    msg: {
        marginTop: 6,
        fontSize: '.8rem',
        fontWeight: 500,
        minHeight: '1.2em',
    },
};

// ─── Component ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
    // Global state — updated exclusively via WebSocket events from the database
    const [occupancy, setOccupancy] = useState({ num_cars_inside: 0, capacity: 75, percentage: 0 });
    const [power, setPower] = useState({ source: 'grid', outage_mode: false });
    const [lockdown, setLockdown] = useState(false);

    // Gates — full state mirrored from WebSocket gate_update events
    const [gates, setGates] = useState({
        1: { open: false, approach_sensor: false, clearance_sensor: false, override: false, override_state: false },
        2: { open: false, approach_sensor: false, clearance_sensor: false, override: false, override_state: false },
    });

    // Floors — array of floor objects, updated via WebSocket floor_update events
    const [floors, setFloors] = useState([]);

    // UI-only state
    const [selectedFloor, setSelectedFloor] = useState(1);
    const [rfidState, setRfidState] = useState('neutral'); // 'neutral' | 'valid' | 'invalid'
    const [badgeInput, setBadgeInput] = useState('');
    const [gateMsg, setGateMsg] = useState({ 1: '', 2: '' });
    const [loading, setLoading] = useState(true);

    // Ref to track previous gate state for deriving messages from state transitions
    const prevGatesRef = useRef(null);

    // ── Helpers ──────────────────────────────────────────────
    const flashRfid = useCallback((state) => {
        setRfidState(state);
        setTimeout(() => setRfidState('neutral'), 2000);
    }, []);

    const setGateMessage = useCallback((gateId, msg) => {
        setGateMsg((p) => ({ ...p, [gateId]: msg }));
        setTimeout(() => setGateMsg((p) => ({ ...p, [gateId]: '' })), 3000);
    }, []);

    // ── Init: fetch initial snapshot via REST ────────────────
    useEffect(() => {
        (async () => {
            try {
                const status = await getStatus();
                if (!status._error) {
                    setOccupancy(status.occupancy);
                    setPower(status.power);
                    setLockdown(status.lockdown);
                    if (status.gates) {
                        const hydrate = (g) => ({
                            open: !!g?.open,
                            approach_sensor: !!g?.approach_sensor,
                            clearance_sensor: !!g?.clearance_sensor,
                            override: !!g?.override,
                            override_state: !!g?.override_state,
                        });
                        const initial = {
                            1: hydrate(status.gates['1']),
                            2: hydrate(status.gates['2']),
                        };
                        setGates(initial);
                        prevGatesRef.current = initial;
                    }
                }
                const occ = await getOccupancy();
                if (!occ._error) {
                    setOccupancy(occ.global);
                    setFloors(occ.floors);
                }
            } catch (e) {
                console.error('Init error', e);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    // ── WebSocket: subscribe to all database state events ────
    useEffect(() => {
        function onGateUpdate(data) {
            if (data.gate_id === undefined) return;
            const gid = data.gate_id;
            const next = {
                open: !!data.open,
                approach_sensor: !!data.approach_sensor,
                clearance_sensor: !!data.clearance_sensor,
                override: !!data.override,
                override_state: !!data.override_state,
            };
            setGates((prev) => {
                const updated = { ...prev, [gid]: { ...prev[gid], ...next } };
                // Derive status messages from state transitions
                const old = prevGatesRef.current?.[gid];
                if (old) {
                    if (!old.open && next.open) {
                        setGateMessage(gid, gid === 1 ? 'Gate opened — awaiting vehicle' : 'Gate opened — vehicle may proceed');
                    } else if (old.open && !next.open) {
                        setGateMessage(gid, gid === 1 ? 'Vehicle entered — gate closing' : 'Vehicle exited — gate closing');
                    }
                    if (!old.approach_sensor && next.approach_sensor && !next.open && gid === 1) {
                        setGateMessage(gid, 'Awaiting RFID badge scan…');
                    }
                }
                prevGatesRef.current = updated;
                return updated;
            });
        }

        function onOccupancyUpdate(data) {
            setOccupancy(data);
        }

        function onFloorUpdate(data) {
            if (data.floor_id === undefined) return;
            setFloors((prev) => {
                const idx = prev.findIndex((f) => f.floor_id === data.floor_id);
                if (idx === -1) return [...prev, data];
                const next = [...prev];
                next[idx] = { ...next[idx], ...data };
                return next;
            });
        }

        function onPowerUpdate(data) {
            setPower(data);
        }

        function onLockdownUpdate(data) {
            setLockdown(!!data.active);
        }

        socket.on('gate_update', onGateUpdate);
        socket.on('occupancy_update', onOccupancyUpdate);
        socket.on('floor_update', onFloorUpdate);
        socket.on('power_update', onPowerUpdate);
        socket.on('lockdown_update', onLockdownUpdate);

        return () => {
            socket.off('gate_update', onGateUpdate);
            socket.off('occupancy_update', onOccupancyUpdate);
            socket.off('floor_update', onFloorUpdate);
            socket.off('power_update', onPowerUpdate);
            socket.off('lockdown_update', onLockdownUpdate);
        };
    }, [setGateMessage]);

    // ── Gate handlers (sensor simulation — fire-and-forget) ──
    const handleVehicleDetected = useCallback(async (gateId) => {
        const nextActive = !(gates[gateId]?.approach_sensor ?? false);
        const res = await vehicleDetected(gateId, nextActive);
        if (res._error) {
            setGateMessage(gateId, res.error || 'Error');
        }
        // State update arrives via WebSocket — no response processing needed
    }, [gates, setGateMessage]);

    const handleRfidScan = useCallback(async () => {
        const uid = badgeInput.trim();
        if (!uid) return;
        const res = await rfidScan(1, uid);
        // RFID is a user action — response carries valid/invalid
        if (!res._error && res.valid) {
            flashRfid('valid');
            setGateMessage(1, `Badge ${uid} — ACCESS GRANTED`);
        } else {
            flashRfid('invalid');
            const errMsg = res.error || (res.valid === false ? 'INVALID BADGE' : 'Error');
            setGateMessage(1, errMsg);
        }
    }, [badgeInput, flashRfid, setGateMessage]);

    const handleVehicleEntered = useCallback(async (gateId) => {
        const nextActive = !(gates[gateId]?.clearance_sensor ?? false);
        const res = await vehicleEntered(gateId, nextActive);
        if (res._error) {
            setGateMessage(gateId, res.error || 'Error');
        }
        // State update arrives via WebSocket — no response processing needed
    }, [gates, setGateMessage]);

    // ── Spot handler (sensor simulation — fire-and-forget) ───
    const handleSpotClick = useCallback(async (spotId, currentlyOccupied) => {
        const res = await spotUpdate(spotId, !currentlyOccupied);
        if (res._error) {
            console.error('Spot update error:', res.error);
        }
        // Floor state update arrives via WebSocket
    }, []);

    // ── Derived ──────────────────────────────────────────────
    const currentFloor = floors.find((f) => f.floor_id === selectedFloor);

    // ── Render ───────────────────────────────────────────────
    if (loading) {
        return (
            <div style={{ ...S.page, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ fontSize: '1.2rem', opacity: 0.7 }}>Loading…</p>
            </div>
        );
    }

    return (
        <div style={S.page}>
            {/* ── Header ─────────────────────────────────── */}
            <header style={S.header}>
                <h1 style={S.headerTitle}>Parking Structure &mdash; Demo Dashboard</h1>
                <a href="/admin" style={S.adminLink}>Admin Panel &rarr;</a>
            </header>

            {/* ── Info text ─────────────────────────────── */}
            <div style={{ padding: '8px 32px', fontSize: '.9rem', color: '#aaa' }}>
                This demonstration page simulates sensor inputs and sends to the system for state updates.
            </div>

            {/* ── Status bar ─────────────────────────────– */}
            <div style={S.statusBar}>
                <span>
                    Cars Inside:&nbsp;
                    <strong>{occupancy.num_cars_inside}</strong> / {occupancy.capacity}
                    &nbsp;({occupancy.percentage}%)
                </span>
                <span
                    style={{
                        ...S.statusChip,
                        background: power.source === 'grid' ? '#06d6a033' : '#ef476f33',
                        color: power.source === 'grid' ? '#06d6a0' : '#ef476f',
                    }}
                >
                    Power: {power.source.toUpperCase()}
                    {power.outage_mode ? ' ⚡ OUTAGE' : ''}
                </span>
                <span
                    style={{
                        ...S.statusChip,
                        background: lockdown ? '#ef476f33' : '#06d6a033',
                        color: lockdown ? '#ef476f' : '#06d6a0',
                    }}
                >
                    {lockdown ? '🔒 LOCKDOWN' : '🟢 Normal'}
                </span>
            </div>

            {/* ── Main ───────────────────────────────────── */}
            <div style={S.main}>
                {/* ── Gate Control Panel ─────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>
                        Gate Control Panel
                        <span style={S.rfidIndicator(rfidState)} title={`RFID: ${rfidState}`} />
                    </h2>

                    {/* Entry Gate */}
                    <div style={S.gateSection}>
                        <h3 style={S.gateSectionTitle}>Entry Gate (ID 1)</h3>
                        <div style={S.gateArm}>
                            <div style={S.gatePost} />
                            <div style={S.gateBar(gates[1].open)} />
                        </div>
                        <div style={S.btnRow}>
                            <button
                                style={{ ...S.btn, ...(gates[1].approach_sensor ? S.btnSensorOn : S.btnPrimary) }}
                                onClick={() => handleVehicleDetected(1)}
                                title="Approach lane sensor — toggle ON/OFF"
                            >
                                {gates[1].approach_sensor ? '● Approach: ON' : 'Approach Sensor'}
                            </button>
                            <input
                                style={S.input}
                                placeholder="Badge UID"
                                value={badgeInput}
                                onChange={(e) => setBadgeInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleRfidScan()}
                            />
                            <button
                                style={{ ...S.btn, ...S.btnSuccess }}
                                onClick={handleRfidScan}
                            >
                                Scan Badge
                            </button>
                        </div>
                        <div style={S.btnRow}>
                            <button
                                style={{ ...S.btn, ...(gates[1].clearance_sensor ? S.btnSensorOn : S.btnPrimary) }}
                                onClick={() => handleVehicleEntered(1)}
                                title="Ultrasonic clearance sensor — ON while vehicle in path, OFF when cleared"
                            >
                                {gates[1].clearance_sensor ? '● Ultrasonic: ON' : 'Ultrasonic (Entry)'}
                            </button>
                        </div>
                        <div
                            style={{
                                ...S.msg,
                                color: gateMsg[1]?.includes('GRANTED') || gateMsg[1]?.includes('entered')
                                    ? '#06d6a0'
                                    : gateMsg[1]?.includes('⛔') || gateMsg[1]?.includes('INVALID') || gateMsg[1]?.includes('capacity')
                                        ? '#ef476f'
                                        : '#aaa',
                            }}
                        >
                            {gateMsg[1]}
                        </div>
                    </div>

                    {/* Exit Gate */}
                    <div style={S.gateSection}>
                        <h3 style={S.gateSectionTitle}>Exit Gate (ID 2)</h3>
                        <div style={S.gateArm}>
                            <div style={S.gatePost} />
                            <div style={S.gateBar(gates[2].open)} />
                        </div>
                        <div style={S.btnRow}>
                            <button
                                style={{ ...S.btn, ...(gates[2].approach_sensor ? S.btnSensorOn : S.btnPrimary) }}
                                onClick={() => handleVehicleDetected(2)}
                                title="Approach lane sensor — toggle ON/OFF"
                            >
                                {gates[2].approach_sensor ? '● Approach: ON' : 'Approach Sensor'}
                            </button>
                            <button
                                style={{ ...S.btn, ...(gates[2].clearance_sensor ? S.btnSensorOn : S.btnPrimary) }}
                                onClick={() => handleVehicleEntered(2)}
                                title="Ultrasonic clearance sensor — ON while vehicle in path, OFF when cleared"
                            >
                                {gates[2].clearance_sensor ? '● Ultrasonic: ON' : 'Ultrasonic (Exit)'}
                            </button>
                        </div>
                        <div
                            style={{
                                ...S.msg,
                                color: gateMsg[2]?.includes('opened') || gateMsg[2]?.includes('exited')
                                    ? '#06d6a0'
                                    : gateMsg[2]?.includes('LOCKDOWN') || gateMsg[2]?.includes('Error')
                                        ? '#ef476f'
                                        : '#aaa',
                            }}
                        >
                            {gateMsg[2]}
                        </div>
                    </div>
                </div>

                {/* ── Parking Floor Map ─────────────────── */}
                <div style={S.card}>
                    <h2 style={S.cardTitle}>Parking Floor Map</h2>

                    {/* Floor tabs */}
                    <div style={S.floorTabs}>
                        {[1, 2, 3].map((fid) => (
                            <button
                                key={fid}
                                style={S.floorTab(selectedFloor === fid)}
                                onClick={() => setSelectedFloor(fid)}
                            >
                                Floor {fid}
                            </button>
                        ))}
                    </div>

                    {/* Spot grid */}
                    {currentFloor ? (
                        <>
                            <div style={S.spotGrid}>
                                {Object.entries(currentFloor.spots)
                                    .sort(([a], [b]) => a.localeCompare(b))
                                    .map(([spotId, occupied]) => (
                                        <div
                                            key={spotId}
                                            style={S.spot(occupied)}
                                            title={`${spotId} — ${occupied ? 'Occupied' : 'Available'}`}
                                            onClick={() => handleSpotClick(spotId, occupied)}
                                        >
                                            <span>{spotId.split('-')[1]}</span>
                                            <div style={S.led(!occupied)} />
                                        </div>
                                    ))}
                            </div>
                            <p style={S.floorSummary}>
                                Floor {currentFloor.floor_id}:&nbsp;
                                <strong>{currentFloor.occupied}</strong> / {currentFloor.total} occupied
                                &nbsp;&mdash;&nbsp;
                                <span
                                    style={{
                                        color: currentFloor.available === 0 ? '#ef476f' : '#06d6a0',
                                        fontWeight: 700,
                                    }}
                                >
                                    {currentFloor.available === 0 ? 'FULL' : 'AVAILABLE'}
                                </span>
                            </p>
                        </>
                    ) : (
                        <p style={{ opacity: 0.5 }}>No floor data</p>
                    )}
                </div>
            </div>
        </div>
    );
}
