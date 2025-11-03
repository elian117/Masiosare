const API_BASE = '';

// Session management
let currentSessionId = localStorage.getItem('currentSessionId') || null;

// Auto-resize textarea
document.getElementById('messageInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Initialize or create new session
async function initializeSession() {
    if (!currentSessionId) {
        try {
            const response = await fetch(`${API_BASE}/api/sessions/new`, {
                method: 'POST'
            });
            const data = await response.json();
            currentSessionId = data.session_id;
            localStorage.setItem('currentSessionId', currentSessionId);
            console.log('New session created:', currentSessionId);
        } catch (error) {
            console.error('Failed to create session:', error);
        }
    }
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Ensure we have a session
    await initializeSession();
    
    // Clear input
    input.value = '';
    input.style.height = 'auto';
    
    // Remove welcome message if exists
    const welcome = document.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }
    
    // Add user message
    addMessage('user', message);
    
    // Show loading
    const loadingId = addLoadingMessage();
    
    // Disable send button
    setSendButtonState(true);
    
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                message,
                session_id: currentSessionId 
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get response');
        }
        
        const data = await response.json();
        
        // Update session ID if it changed
        if (data.session_id && data.session_id !== currentSessionId) {
            currentSessionId = data.session_id;
            localStorage.setItem('currentSessionId', currentSessionId);
        }
        
        // Remove loading
        removeLoadingMessage(loadingId);
        
        // Add assistant message with data table and fuzzy matches if available
        addMessage('assistant', data.response, data.dataframe, data.columns, data.query, data.fuzzy_matches);
        
    } catch (error) {
        removeLoadingMessage(loadingId);
        addMessage('assistant', '❌ Sorry, I encountered an error. Please try again.');
        console.error('Error:', error);
    } finally {
        setSendButtonState(false);
    }
}

// Send example query
function sendExample(text) {
    document.getElementById('messageInput').value = text;
    sendMessage();
}

// Add message to chat
function addMessage(role, content, dataframe = null, columns = null, query = null) {
    const container = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    
    let messageContent = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${formatContent(content)}
    `;
    
    // If there's a dataframe, add it as a table
    if (dataframe && dataframe.length > 0 && columns) {
        messageContent += `
            <div class="data-table-container">
                <div class="table-info">📊 <strong>${dataframe.length} rows</strong> returned</div>
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr>
                                ${columns.map(col => `<th>${col}</th>`).join('')}
                            </tr>
                        </thead>
                        <tbody>
                            ${dataframe.map(row => `
                                <tr>
                                    ${columns.map(col => `<td>${row[col] !== null ? row[col] : '<span style="color: #94a3b8;">null</span>'}</td>`).join('')}
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    messageContent += `</div>`;
    messageDiv.innerHTML = messageContent;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Format message content
function formatContent(content) {
    
    // Convert markdown code blocks to HTML
    content = content.replace(/```sql\n([\s\S]*?)```/g, '');
    content = content.replace(/```([\s\S]*?)```/g, '');
    
    // Convert markdown tables to HTML
    if (content.includes('|')) {
        const lines = content.split('\n');
        let tableHtml = '';
        let inTable = false;
        let newContent = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            if (line.startsWith('|') && line.endsWith('|')) {
                if (!inTable) {
                    tableHtml = '<table>';
                    inTable = true;
                }
                
                const cells = line.split('|').filter(cell => cell.trim());
                const isHeader = i < lines.length - 1 && lines[i + 1].includes('---');
                
                if (!lines[i + 1]?.includes('---') && i > 0 && lines[i - 1].includes('---')) {
                    tableHtml += '<tr>';
                    cells.forEach(cell => {
                        tableHtml += `<td>${cell.trim()}</td>`;
                    });
                    tableHtml += '</tr>';
                } else if (isHeader) {
                    tableHtml += '<tr>';
                    cells.forEach(cell => {
                        tableHtml += `<th>${cell.trim()}</th>`;
                    });
                    tableHtml += '</tr>';
                } else if (!line.includes('---')) {
                    tableHtml += '<tr>';
                    cells.forEach(cell => {
                        tableHtml += `<td>${cell.trim()}</td>`;
                    });
                    tableHtml += '</tr>';
                }
                
            } else {
                if (inTable) {
                    tableHtml += '</table>';
                    newContent.push(tableHtml);
                    tableHtml = '';
                    inTable = false;
                }
                newContent.push(line);
            }
        }
        
        if (inTable) {
            tableHtml += '</table>';
            newContent.push(tableHtml);
        }
        
        content = newContent.join('\n');
    }
    
    // Convert line breaks
    content = content.replace(/\n/g, '<br>');
    
    // Convert bold
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert inline code with backticks
    content = content.replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: monospace;">$1</code>');
    
    // Convert checkmarks
    content = content.replace(/✓/g, '<span style="color: #10b981;">✓</span>');
    
    // Convert error marks
    content = content.replace(/❌/g, '<span style="color: #ef4444;">❌</span>');
    
    return content;
}

// Add loading message
function addLoadingMessage() {
    const container = document.getElementById('chatContainer');
    const loadingDiv = document.createElement('div');
    const loadingId = 'loading-' + Date.now();
    loadingDiv.id = loadingId;
    loadingDiv.className = 'message assistant';
    
    loadingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="loading">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;
    
    container.appendChild(loadingDiv);
    container.scrollTop = container.scrollHeight;
    
    return loadingId;
}

// Remove loading message
function removeLoadingMessage(loadingId) {
    const loading = document.getElementById(loadingId);
    if (loading) {
        loading.remove();
    }
}

// Set send button state
function setSendButtonState(disabled) {
    const button = document.getElementById('sendButton');
    const icon = document.getElementById('sendIcon');
    const text = document.getElementById('sendText');
    
    button.disabled = disabled;
    
    if (disabled) {
        icon.textContent = '⏳';
        text.textContent = 'Thinking...';
    } else {
        icon.textContent = '📤';
        text.textContent = 'Send';
    }
}

// Clear chat history for current session
async function clearHistory() {
    if (!confirm('Are you sure you want to clear the chat history for this session?')) {
        return;
    }
    
    try {
        const url = currentSessionId 
            ? `${API_BASE}/api/history?session_id=${currentSessionId}`
            : `${API_BASE}/api/history`;
            
        await fetch(url, {
            method: 'DELETE'
        });
        
        // Clear UI
        const container = document.getElementById('chatContainer');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">👋</div>
                <h2>Welcome to MASIOSARE!</h2>
                <p>Ask me anything about the database. I'll remember our conversation!</p>
                <div class="session-info">
                    <p>💡 <strong>Memory Enabled:</strong> I can reference previous queries and maintain context across the conversation.</p>
                </div>
                <div class="example-queries">
                    <p><strong>Try asking:</strong></p>
                    <button class="example-btn" onclick="sendExample('How many products are in each category?')">
                        How many products are in each category?
                    </button>
                    <button class="example-btn" onclick="sendExample('Show me the details of the top category')">
                        Show me the details of the top category
                    </button>
                    <button class="example-btn" onclick="sendExample('How many were there in the previous query?')">
                        How many were there in the previous query?
                    </button>
                </div>
            </div>
        `;
    } catch (error) {
        alert('Failed to clear history');
        console.error('Error:', error);
    }
}

// Start new conversation session
async function startNewSession() {
    if (!confirm('Start a new conversation? Current session will be saved.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/sessions/new`, {
            method: 'POST'
        });
        const data = await response.json();
        currentSessionId = data.session_id;
        localStorage.setItem('currentSessionId', currentSessionId);
        
        // Clear UI
        const container = document.getElementById('chatContainer');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🆕</div>
                <h2>New Conversation Started!</h2>
                <p>Session ID: ${currentSessionId.substring(0, 8)}...</p>
                <div class="example-queries">
                    <p><strong>Try asking:</strong></p>
                    <button class="example-btn" onclick="sendExample('How many products are in each category?')">
                        How many products are in each category?
                    </button>
                </div>
            </div>
        `;
        
        console.log('New session started:', currentSessionId);
    } catch (error) {
        alert('Failed to start new session');
        console.error('Error:', error);
    }
}

// Load chat history on page load
async function loadHistory() {
    await initializeSession();
    
    try {
        const url = currentSessionId 
            ? `${API_BASE}/api/history?session_id=${currentSessionId}`
            : `${API_BASE}/api/history`;
            
        const response = await fetch(url);
        const history = await response.json();
        
        if (history.length > 0) {
            const welcome = document.querySelector('.welcome-message');
            if (welcome) {
                welcome.remove();
            }
            
            history.forEach(msg => {
                addMessage(msg.role, msg.content, msg.dataframe, msg.columns, msg.query);
            });
            
            console.log('Loaded conversation history with', history.length, 'messages');
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

// Auto-focus input on load
window.addEventListener('load', function() {
    document.getElementById('messageInput').focus();
    loadHistory();
    
    // Display session info
    if (currentSessionId) {
        console.log('Current session:', currentSessionId);
    }
});

console.log('Text-to-SQL Agent Chat Interface with Memory loaded successfully! 🚀');