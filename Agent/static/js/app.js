// PenangLens AI Agent - Dual-view UI (Generate + Chat)

// =============================================
// DOM Elements
// =============================================
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const statusText = document.querySelector('.status-text');
const statusDot = document.querySelector('.status-dot');

// State
let threadId = null;
let currentItinerary = null;
let map = null;
let mapMarkers = [];

// =============================================
// View Navigation
// =============================================
function showView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    document.getElementById('view' + viewName.charAt(0).toUpperCase() + viewName.slice(1)).classList.add('active');
    document.getElementById('nav' + viewName.charAt(0).toUpperCase() + viewName.slice(1)).classList.add('active');

    if (viewName === 'chat') {
        messageInput?.focus();
    }
}

// =============================================
// Interest Tags
// =============================================
document.querySelectorAll('.tag-btn').forEach(btn => {
    btn.addEventListener('click', () => btn.classList.toggle('selected'));
});

// Travel Mode
document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

// =============================================
// GENERATE FLOW
// =============================================
async function generateItinerary() {
    const description = document.getElementById('tripDescription').value.trim();
    const interests = Array.from(document.querySelectorAll('.tag-btn.selected'))
        .map(btn => btn.dataset.tag);
    const startTime = document.getElementById('startTime').value;
    const endTime = document.getElementById('endTime').value;
    const startLocation = document.getElementById('startLocation').value;
    const travelMode = document.querySelector('.mode-btn.active')?.dataset.mode || 'walking';

    // Require at least description or interests
    if (!description && interests.length === 0) {
        alert('Please describe your trip or select at least one interest.');
        return;
    }

    // Show loading
    document.getElementById('generateForm').style.display = 'none';
    document.getElementById('loadingPanel').style.display = 'flex';
    document.getElementById('itineraryPanel').style.display = 'none';

    const statusMsgs = [
        'Searching for the best places...',
        'Calculating travel times...',
        'Optimizing your route...',
        'Adding personal recommendations...',
        'Almost there...'
    ];
    let statusIdx = 0;
    const statusInterval = setInterval(() => {
        statusIdx = (statusIdx + 1) % statusMsgs.length;
        document.getElementById('loadingStatus').textContent = statusMsgs[statusIdx];
    }, 3000);

    updateStatus('Generating...', 'processing');

    try {
        const response = await fetch('/api/v1/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description,
                interests,
                start_time: startTime,
                end_time: endTime,
                start_location: startLocation,
                travel_mode: travelMode,
            }),
        });

        clearInterval(statusInterval);

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        threadId = data.thread_id;

        if (data.structured_itinerary && data.structured_itinerary.stops.length > 0) {
            currentItinerary = data.structured_itinerary;
            renderItinerary(currentItinerary, data.response);
        } else {
            // Fallback: show the markdown response in chat
            showView('chat');
            addMessage(data.response, 'assistant');
        }

        updateStatus('Ready', 'ready');

    } catch (error) {
        clearInterval(statusInterval);
        console.error('Generate error:', error);
        document.getElementById('loadingPanel').style.display = 'none';
        document.getElementById('generateForm').style.display = 'block';
        alert('Error generating itinerary: ' + error.message);
        updateStatus('Error', 'error');
    }
}

// =============================================
// RENDER ITINERARY
// =============================================
function renderItinerary(itinerary, rawResponse) {
    document.getElementById('loadingPanel').style.display = 'none';
    document.getElementById('generateForm').style.display = 'none';
    document.getElementById('itineraryPanel').style.display = 'flex';

    // Stats
    const hours = Math.floor(itinerary.total_duration_min / 60);
    const mins = itinerary.total_duration_min % 60;
    const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;

    document.getElementById('itineraryStats').innerHTML = `
        <div class="stat-item">
            <div class="stat-value">⏱️ ${timeStr}</div>
            <div class="stat-label">Duration</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">📍 ${itinerary.stops.length}</div>
            <div class="stat-label">Stops</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">🚶 ${itinerary.total_walking_distance || '—'}</div>
            <div class="stat-label">Distance</div>
        </div>
        ${itinerary.route_url ? `
        <div class="stat-item">
            <a href="${itinerary.route_url}" target="_blank" class="stat-value" style="color:#667eea;text-decoration:none;">🗺️ Map</a>
            <div class="stat-label">Route</div>
        </div>` : ''}
    `;

    // Stops
    const stopsContainer = document.getElementById('itineraryStops');
    stopsContainer.innerHTML = '';

    itinerary.stops.forEach((stop, idx) => {
        // Stop card
        const card = document.createElement('div');
        card.className = 'stop-card';
        card.onclick = () => card.classList.toggle('expanded');

        const shortDesc = stop.short_description || stop.description.substring(0, 60) + '...';

        card.innerHTML = `
            <div class="stop-header">
                <div class="stop-number">${stop.order}</div>
                <div class="stop-info">
                    <div class="stop-name">${stop.name}</div>
                    <div class="stop-short-desc">${shortDesc}</div>
                </div>
                <div class="stop-duration-badge">${stop.visit_duration_min} min</div>
            </div>
            <div class="stop-details">
                <div class="stop-full-desc">${stop.description}</div>
                ${stop.tips ? `<div class="stop-tips">💡 ${stop.tips}</div>` : ''}
                <div class="stop-links">
                    ${stop.google_maps_url ? `<a href="${stop.google_maps_url}" target="_blank" class="stop-link maps">📍 Google Maps</a>` : ''}
                </div>
            </div>
        `;

        stopsContainer.appendChild(card);

        // Travel connector between stops
        if (stop.travel_to_next && idx < itinerary.stops.length - 1) {
            const connector = document.createElement('div');
            connector.className = 'travel-connector';
            connector.innerHTML = `
                <div class="travel-line"></div>
                🚶 ${stop.travel_to_next.duration_text} · ${stop.travel_to_next.distance_text}
            `;
            stopsContainer.appendChild(connector);
        }
    });

    // Render Map with Leaflet
    renderMap(itinerary.stops);
}

// =============================================
// LEAFLET MAP
// =============================================
function renderMap(stops) {
    const mapContainer = document.getElementById('itineraryMap');

    // Clear existing map
    if (map) {
        map.remove();
        map = null;
    }

    // Filter stops with valid coordinates
    const validStops = stops.filter(s => s.lat && s.lng);
    if (validStops.length === 0) {
        mapContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;">🗺️ No coordinates available for map</div>';
        return;
    }

    // Create map
    map = L.map('itineraryMap', { zoomControl: false });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);

    L.control.zoom({ position: 'topright' }).addTo(map);

    // Add markers
    const bounds = [];
    mapMarkers = [];

    validStops.forEach((stop, idx) => {
        const marker = L.marker([stop.lat, stop.lng]).addTo(map);
        marker.bindPopup(`<strong>${stop.order}. ${stop.name}</strong><br>${stop.visit_duration_min} min`);
        bounds.push([stop.lat, stop.lng]);
        mapMarkers.push(marker);
    });

    // Draw route line
    if (bounds.length > 1) {
        L.polyline(bounds, {
            color: '#667eea',
            weight: 3,
            opacity: 0.7,
            dashArray: '8, 8'
        }).addTo(map);
    }

    // Fit bounds
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }
}

// =============================================
// REFINEMENT / CHAT
// =============================================
let isRefining = false;

function showRefineChat() {
    isRefining = true;
    // Show inline refinement input inside itinerary panel
    const actions = document.querySelector('.itinerary-actions');
    actions.innerHTML = `
        <div style="width:100%;">
            <div class="quick-actions" style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;">
                <button class="quick-btn" onclick="sendRefine('Add a food stop')">Add food 🍜</button>
                <button class="quick-btn" onclick="sendRefine('Add a cafe stop')">Add cafe ☕</button>
                <button class="quick-btn" onclick="sendRefine('Remove the last stop')">Remove last</button>
                <button class="quick-btn" onclick="sendRefine('Make it shorter')">Shorter</button>
            </div>
            <div class="input-wrapper" style="display:flex;gap:8px;">
                <input type="text" id="refineInput" class="form-input" 
                    placeholder="e.g. Remove the cafe, add a museum instead..." 
                    onkeydown="if(event.key==='Enter')sendRefine()" 
                    style="flex:1;padding:12px 16px;">
                <button class="send-button" onclick="sendRefine()"
                    style="width:44px;height:44px;flex-shrink:0;">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <path d="M2 10L18 2L10 18L8 11L2 10Z" fill="currentColor"/>
                    </svg>
                </button>
            </div>
            <div id="refineStatus" style="font-size:12px;color:#94a3b8;margin-top:6px;text-align:center;"></div>
        </div>
    `;
    document.getElementById('refineInput').focus();
}

async function sendRefine(quickText) {
    const input = document.getElementById('refineInput');
    const text = quickText || (input ? input.value.trim() : '');
    if (!text) return;

    if (input) input.value = '';
    const statusEl = document.getElementById('refineStatus');
    if (statusEl) statusEl.textContent = '✨ Updating your itinerary...';
    updateStatus('Refining...', 'processing');

    try {
        // Use sync chat endpoint with same thread_id for context
        const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: threadId }),
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const data = await response.json();
        threadId = data.thread_id;

        // Now re-extract structured itinerary from the response
        if (statusEl) statusEl.textContent = '📍 Extracting updated stops...';

        const extractRes = await fetch('/api/v1/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                response_text: data.response,
                travel_mode: currentItinerary?.travel_mode || 'walking',
            }),
        });

        if (extractRes.ok) {
            const extracted = await extractRes.json();
            if (extracted && extracted.stops && extracted.stops.length > 0) {
                currentItinerary = extracted;
                renderItinerary(currentItinerary, data.response);
                // Re-add refinement input
                showRefineChat();
                if (statusEl) statusEl.textContent = '✅ Itinerary updated!';
                setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 2000);
            } else {
                if (statusEl) statusEl.textContent = '⚠️ Could not extract stops. Try a more specific request.';
            }
        } else {
            if (statusEl) statusEl.textContent = '⚠️ Extraction failed, but response received.';
        }

        updateStatus('Ready', 'ready');

    } catch (error) {
        console.error('Refine error:', error);
        if (statusEl) statusEl.textContent = '❌ Error: ' + error.message;
        updateStatus('Error', 'error');
    }
}

function sendQuick(text) {
    messageInput.value = text;
    chatForm.dispatchEvent(new Event('submit'));
}

function startNewTrip() {
    threadId = null;
    currentItinerary = null;
    document.getElementById('itineraryPanel').style.display = 'none';
    document.getElementById('loadingPanel').style.display = 'none';
    document.getElementById('generateForm').style.display = 'block';

    // Reset form
    document.getElementById('tripDescription').value = '';
    document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('selected'));
}

// Auto-resize textarea
messageInput?.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Handle form submission
chatForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    messageInput.value = '';
    messageInput.style.height = 'auto';
    setInputState(false);

    await streamResponse(message);

    setInputState(true);
    messageInput.focus();
});

// Handle Enter key
messageInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// =============================================
// SSE STREAMING
// =============================================
async function streamResponse(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" /></svg>';

    const content = document.createElement('div');
    content.className = 'message-content';

    const toolStatus = document.createElement('div');
    toolStatus.className = 'tool-status';
    toolStatus.style.display = 'none';

    const messageText = document.createElement('div');
    messageText.className = 'message-text streaming';

    content.appendChild(toolStatus);
    content.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    let fullText = '';
    updateStatus('Thinking...', 'processing');

    try {
        const response = await fetch('/api/v1/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, thread_id: threadId }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
            messageText.innerHTML = formatMessage(`❌ Error: ${err.detail || response.statusText}`);
            messageText.classList.remove('streaming');
            updateStatus('Error', 'error');
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            let currentEvent = '';
            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEvent = line.slice(6).trim();
                } else if (line.startsWith('data:')) {
                    const dataStr = line.slice(5).trim();
                    if (!dataStr) continue;
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.thread_id) threadId = data.thread_id;

                        switch (data.type || currentEvent) {
                            case 'token':
                                fullText += data.content || '';
                                messageText.innerHTML = formatMessage(fullText);
                                scrollToBottom();
                                break;
                            case 'tool_start':
                                updateStatus(`Using ${data.tool_name || 'tool'}...`, 'processing');
                                toolStatus.style.display = 'block';
                                toolStatus.innerHTML = `🔧 <em>${data.content || 'Working...'}</em>`;
                                break;
                            case 'tool_end':
                                toolStatus.style.display = 'none';
                                updateStatus('Generating...', 'processing');
                                break;
                            case 'done':
                                messageText.classList.remove('streaming');
                                toolStatus.style.display = 'none';
                                updateStatus('Ready', 'ready');
                                break;
                            case 'error':
                                fullText += `\n\n❌ ${data.content || 'Error'}`;
                                messageText.innerHTML = formatMessage(fullText);
                                messageText.classList.remove('streaming');
                                updateStatus('Error', 'error');
                                break;
                        }
                    } catch (e) { /* skip unparseable */ }
                }
            }
        }

        messageText.classList.remove('streaming');
        if (!fullText.trim()) {
            messageText.innerHTML = formatMessage("Processing your request...");
        }
        updateStatus('Ready', 'ready');

    } catch (error) {
        messageText.innerHTML = formatMessage(`❌ Connection error: ${error.message}`);
        messageText.classList.remove('streaming');
        updateStatus('Error', 'error');
    }
}

// =============================================
// UI HELPERS
// =============================================
function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = type === 'user' ? 'U' : '';
    if (type !== 'user') {
        avatar.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" /></svg>';
    }

    const content = document.createElement('div');
    content.className = 'message-content';
    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    messageText.innerHTML = formatMessage(text);

    content.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function formatMessage(text) {
    return text
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/(?<![">])(https?:\/\/[^\s<)]+)/g, '<a href="$1" target="_blank">$1</a>')
        .replace(/^---$/gm, '<hr>')
        .replace(/^[•\-] (.+)$/gm, '<li>$1</li>')
        .replace(/^\* (.+)$/gm, '<li>$1</li>')
        .replace(/\n/g, '<br>');
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setInputState(enabled) {
    if (messageInput) messageInput.disabled = !enabled;
    if (sendButton) sendButton.disabled = !enabled;
}

function updateStatus(text, state) {
    statusText.textContent = text;
    statusDot.style.background = state === 'ready' ? '#4ade80' : state === 'processing' ? '#fbbf24' : '#ef4444';
}

// Health check
async function checkHealth() {
    try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        if (!data.gemini_configured) {
            updateStatus('No API Key', 'error');
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}

checkHealth();
