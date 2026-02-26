// PenangLens AI Agent - Chat Interface with SSE Streaming

const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const statusText = document.querySelector(".status-text");
const statusDot = document.querySelector(".status-dot");

// Session management
let threadId = null;

// Auto-resize textarea
messageInput.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

// Handle form submission
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const message = messageInput.value.trim();
  if (!message) return;

  // Add user message to chat
  addMessage(message, "user");

  // Clear input
  messageInput.value = "";
  messageInput.style.height = "auto";

  // Disable input while processing
  setInputState(false);

  // Stream the response
  await streamResponse(message);

  setInputState(true);
  messageInput.focus();
});

// Handle Enter key (send) and Shift+Enter (new line)
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

// Stream response from SSE endpoint
async function streamResponse(message) {
  // Create the assistant message container (empty, will be filled by streaming)
  const messageDiv = document.createElement("div");
  messageDiv.className = "message assistant-message";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" />
        </svg>
    `;

  const content = document.createElement("div");
  content.className = "message-content";

  const messageText = document.createElement("div");
  messageText.className = "message-text streaming";

  // Tool status indicator
  const toolStatus = document.createElement("div");
  toolStatus.className = "tool-status";
  toolStatus.style.display = "none";

  content.appendChild(toolStatus);
  content.appendChild(messageText);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);
  chatMessages.appendChild(messageDiv);
  scrollToBottom();

  let fullText = "";
  let activeTools = 0;

  updateStatus("Connecting...", "processing");

  try {
    const response = await fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        thread_id: threadId,
      }),
    });

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }));
      messageText.innerHTML = formatMessage(
        `❌ Error: ${errorData.detail || response.statusText}`,
      );
      messageText.classList.remove("streaming");
      updateStatus("Error", "error");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    updateStatus("Thinking...", "processing");

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep incomplete line in buffer

      let currentEvent = "";

      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const dataStr = line.slice(5).trim();
          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);
            const eventType = data.type || currentEvent;

            // Save thread_id from first event
            if (data.thread_id && !threadId) {
              threadId = data.thread_id;
            }

            switch (eventType) {
              case "token":
                fullText += data.content || "";
                messageText.innerHTML = formatMessage(fullText);
                scrollToBottom();
                break;

              case "tool_start":
                activeTools++;
                updateStatus(
                  `Using ${data.tool_name || "tool"}...`,
                  "processing",
                );
                toolStatus.style.display = "block";
                toolStatus.innerHTML = `🔧 <em>${data.content || "Searching..."}</em>`;
                scrollToBottom();
                break;

              case "tool_end":
                activeTools = Math.max(0, activeTools - 1);
                if (activeTools === 0) {
                  updateStatus("Generating response...", "processing");
                  toolStatus.style.display = "none";
                }
                break;

              case "done":
                messageText.classList.remove("streaming");
                toolStatus.style.display = "none";
                updateStatus("Ready", "ready");

                // Save thread_id
                if (data.thread_id) {
                  threadId = data.thread_id;
                }
                break;

              case "error":
                fullText += `\n\n❌ ${data.content || "An error occurred"}`;
                messageText.innerHTML = formatMessage(fullText);
                messageText.classList.remove("streaming");
                updateStatus("Error", "error");
                break;
            }
          } catch (e) {
            // Skip unparseable data lines
            console.debug("Skipping unparseable SSE data:", dataStr);
          }
        }
      }
    }

    // Ensure we finish cleanly
    if (messageText.classList.contains("streaming")) {
      messageText.classList.remove("streaming");
      updateStatus("Ready", "ready");
    }

    // If no text was streamed, show a fallback
    if (!fullText.trim()) {
      messageText.innerHTML = formatMessage(
        "I'm processing your request. The response may still be generating...",
      );
    }
  } catch (error) {
    console.error("Stream error:", error);
    messageText.innerHTML = formatMessage(
      `❌ Connection error: ${error.message}`,
    );
    messageText.classList.remove("streaming");
    updateStatus("Error", "error");
  }
}

// Add message to chat
function addMessage(text, type) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${type}-message`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";

  if (type === "user") {
    avatar.textContent = "U";
  } else {
    avatar.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="url(#avatarGradient)" />
            </svg>
        `;
  }

  const content = document.createElement("div");
  content.className = "message-content";

  const messageText = document.createElement("div");
  messageText.className = "message-text";

  if (type === "error") {
    messageDiv.classList.add("error-message");
  }

  messageText.innerHTML = formatMessage(text);

  content.appendChild(messageText);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);

  chatMessages.appendChild(messageDiv);
  scrollToBottom();

  return messageDiv;
}

// Format message text (markdown-like to HTML)
function formatMessage(text) {
  let formatted = text
    // Headers
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Links [text](url)
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>',
    )
    // Bare URLs (not already inside an <a> tag)
    .replace(
      /(?<![">])(https?:\/\/[^\s<)]+)/g,
      '<a href="$1" target="_blank" rel="noopener">$1</a>',
    )
    // Horizontal rules
    .replace(/^---$/gm, "<hr>")
    // List items (with bullet • or -)
    .replace(/^[•\-] (.+)$/gm, "<li>$1</li>")
    .replace(/^\* (.+)$/gm, "<li>$1</li>")
    // Line breaks
    .replace(/\n/g, "<br>");

  // Wrap consecutive <li> in <ul>
  formatted = formatted.replace(/(<li>.*?<\/li>(<br>)?)+/g, (match) => {
    return "<ul>" + match.replace(/<br>/g, "") + "</ul>";
  });

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

  if (state === "ready") {
    statusDot.style.background = "#4ade80";
  } else if (state === "processing") {
    statusDot.style.background = "#fbbf24";
  } else if (state === "error") {
    statusDot.style.background = "#ef4444";
  }
}

// Check API health on load
async function checkHealth() {
  try {
    const response = await fetch("/api/v1/health");
    const data = await response.json();

    if (!data.gemini_configured) {
      addMessage(
        "⚠️ Warning: Google Gemini API key not configured. Please set it in your .env file.",
        "error",
      );
      updateStatus("Not Configured", "error");
    }
  } catch (error) {
    console.error("Health check failed:", error);
  }
}

// Initialize
checkHealth();
messageInput.focus();
