const API_BASE = '';

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

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
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
            body: JSON.stringify({ message })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get response');
        }
        
        const data = await response.json();
        
        // Remove loading
        removeLoadingMessage(loadingId);
        
        // Add assistant message
        addMessage('assistant', data.response);
        
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
function addMessage(role, content) {
    const container = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">${formatContent(content)}</div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Format message content (CORRECTED - uses outputs/ directory)
function formatContent(content) {
    // Convert markdown code blocks to HTML
    content = content.replace(/```sql\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    content = content.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
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

// Clear chat history
async function clearHistory() {
    if (!confirm('Are you sure you want to clear the chat history?')) {
        return;
    }
    
    try {
        await fetch(`${API_BASE}/api/history`, {
            method: 'DELETE'
        });
        
        // Clear UI
        const container = document.getElementById('chatContainer');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">👋</div>
                <h2>Welcome to MASIOSARE!</h2>
                <p>Ask me anything about the database. I can:</p>
                <ul>
                    <li>Execute SQL queries from natural language</li>
                    <li>Show results in beautiful tables</li>
                    <li>Create visualizations and charts</li>
                </ul>
                <div class="example-queries">
                    <p><strong>Try asking:</strong></p>
                    <button class="example-btn" onclick="sendExample('How many products are in each category?')">
                        How many products are in each category?
                    </button>
                    <button class="example-btn" onclick="sendExample('Show top 5 customers by total spending and create a bar chart')">
                        Show top 5 customers by total spending and create a bar chart
                    </button>
                    <button class="example-btn" onclick="sendExample('Create a pie chart of order statuses')">
                        Create a pie chart of order statuses
                    </button>
                </div>
            </div>
        `;
    } catch (error) {
        alert('Failed to clear history');
        console.error('Error:', error);
    }
}

// Close modal when clicking outside
document.getElementById('vizModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Load chat history on page load
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        const history = await response.json();
        
        if (history.length > 0) {
            const welcome = document.querySelector('.welcome-message');
            if (welcome) {
                welcome.remove();
            }
            
            history.forEach(msg => {
                addMessage(msg.role, msg.content);
            });
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

// Auto-focus input on load
window.addEventListener('load', function() {
    document.getElementById('messageInput').focus();
    loadHistory();
});

console.log('Text-to-SQL Agent Chat Interface loaded successfully! 🚀');