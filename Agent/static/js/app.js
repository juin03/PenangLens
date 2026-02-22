// PenangLens AI Agent - Chat Interface

const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const statusText = document.querySelector('.status-text');
const statusDot = document.querySelector('.status-dot');

// Auto-resize textarea
messageInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Handle form submission
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Disable input while processing
    setInputState(false);
    updateStatus('Thinking...', 'processing');

    // Show loading indicator
    const loadingId = addLoadingMessage();

    try {
        // Send message to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        // Remove loading indicator
        removeLoadingMessage(loadingId);

        if (response.ok) {
            const data = await response.json();

            if (data.success) {
                // Add assistant response
                addMessage(data.response, 'assistant');
                updateStatus('Ready', 'ready');
            } else {
                // Show error from response
                addMessage(`Error: ${data.error || 'Unknown error'}`, 'error');
                updateStatus('Error', 'error');
            }
        } else {
            // Handle HTTP errors
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            addMessage(`Server error: ${errorData.detail || response.statusText}`, 'error');
            updateStatus('Error', 'error');
        }

    } catch (error) {
        removeLoadingMessage(loadingId);
        addMessage(`Connection error: ${error.message}`, 'error');
        updateStatus('Error', 'error');
    } finally {
        setInputState(true);
        messageInput.focus();
    }
});

// Handle Enter key (send) and Shift+Enter (new line)
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// Add message to chat
function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';

    if (type === 'user') {
        avatar.textContent = 'U';
    } else {
        avatar.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" />
            </svg>
        `;
    }

    const content = document.createElement('div');
    content.className = 'message-content';

    const messageText = document.createElement('div');
    messageText.className = 'message-text';

    if (type === 'error') {
        messageDiv.classList.add('error-message');
    }

    // Format the message text (preserve line breaks and basic formatting)
    messageText.innerHTML = formatMessage(text);

    content.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

// Add loading message
function addLoadingMessage() {
    const loadingDiv = document.createElement('div');
    const loadingId = 'loading-' + Date.now();
    loadingDiv.id = loadingId;
    loadingDiv.className = 'message loading-message';

    loadingDiv.innerHTML = `
        <div class="message-avatar">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" />
            </svg>
        </div>
        <div class="message-content">
            <div class="loading-dots">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;

    chatMessages.appendChild(loadingDiv);
    scrollToBottom();

    return loadingId;
}

// Remove loading message
function removeLoadingMessage(loadingId) {
    const loadingDiv = document.getElementById(loadingId);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// Format message text
function formatMessage(text) {
    // Convert markdown-style formatting to HTML
    let formatted = text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')  // Bold
        .replace(/\n/g, '<br>')  // Line breaks
        .replace(/^- (.+)$/gm, '<li>$1</li>');  // List items

    // Wrap consecutive list items in <ul>
    formatted = formatted.replace(/(<li>.*<\/li>(?:<br>)?)+/g, (match) => {
        return '<ul>' + match.replace(/<br>/g, '') + '</ul>';
    });

    // Wrap in paragraphs
    if (!formatted.includes('<ul>') && !formatted.includes('<br>')) {
        formatted = '<p>' + formatted + '</p>';
    }

    return formatted;
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Set input state (enabled/disabled)
function setInputState(enabled) {
    messageInput.disabled = !enabled;
    sendButton.disabled = !enabled;
}

// Update status indicator
function updateStatus(text, state) {
    statusText.textContent = text;

    // Update status dot color
    if (state === 'ready') {
        statusDot.style.background = '#4ade80';
    } else if (state === 'processing') {
        statusDot.style.background = '#fbbf24';
    } else if (state === 'error') {
        statusDot.style.background = '#ef4444';
    }
}

// Check API health on load
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        if (!data.gemini_configured) {
            addMessage('⚠️ Warning: Google Gemini API key not configured. Please set it in your .env file.', 'error');
            updateStatus('Not Configured', 'error');
        }
    } catch (error) {
        console.error('Health check failed:', error);
    }
}

// Initialize
checkHealth();
messageInput.focus();
