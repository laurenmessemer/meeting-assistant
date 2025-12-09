"""UI router for serving the web interface."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the main UI page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meeting Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', system-ui, sans-serif;
            background: #f5f5f7;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 24px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border-radius: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08), 0 1px 0 rgba(255, 255, 255, 0.5) inset;
            width: 100%;
            max-width: 840px;
            height: 92vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 0.5px solid rgba(0, 0, 0, 0.08);
        }
        
        .header {
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            padding: 20px 28px;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.06);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .header h1 {
            font-size: 20px;
            font-weight: 590;
            color: #1d1d1f;
            letter-spacing: -0.3px;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px 28px;
            background: transparent;
            scroll-behavior: smooth;
        }
        
        .chat-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .chat-container::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .chat-container::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
        }
        
        .chat-container::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 0, 0, 0.3);
        }
        
        .message {
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
            animation: fadeInUp 0.3s ease-out;
            opacity: 0;
            animation-fill-mode: forwards;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            align-items: flex-end;
        }
        
        .message.assistant {
            align-items: flex-start;
        }
        
        .message-bubble {
            max-width: 75%;
            padding: 10px 16px;
            border-radius: 20px;
            word-wrap: break-word;
            line-height: 1.5;
            font-size: 15px;
            letter-spacing: -0.1px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .message.user .message-bubble {
            background: #e8e8ed;
            color: #1d1d1f;
            border-bottom-right-radius: 4px;
        }
        
        .message.assistant .message-bubble {
            background: #ffffff;
            color: #1d1d1f;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06), 0 2px 8px rgba(0, 0, 0, 0.04);
            border-bottom-left-radius: 4px;
        }
        
        .message.assistant {
            align-items: stretch;
        }
        
        .message.assistant .assistant-card {
            width: 100%;
            max-width: 100%;
        }
        
        .input-container {
            padding: 16px 20px 20px;
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border-top: 0.5px solid rgba(0, 0, 0, 0.06);
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        #messageInput {
            flex: 1;
            padding: 10px 18px;
            border: 0.5px solid rgba(0, 0, 0, 0.1);
            border-radius: 20px;
            font-size: 15px;
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', system-ui, sans-serif;
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            outline: none;
            transition: all 0.2s ease;
            color: #1d1d1f;
            letter-spacing: -0.1px;
        }
        
        #messageInput:focus {
            border-color: rgba(0, 0, 0, 0.2);
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.04);
        }
        
        #messageInput::placeholder {
            color: #86868b;
        }
        
        #sendButton {
            padding: 10px 24px;
            background: #1d1d1f;
            color: #ffffff;
            border: none;
            border-radius: 20px;
            font-size: 15px;
            font-weight: 590;
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', system-ui, sans-serif;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: -0.1px;
            min-width: 64px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        #sendButton:hover {
            background: #2d2d2f;
            transform: scale(1.02);
        }
        
        #sendButton:active {
            transform: scale(0.98);
        }
        
        #sendButton:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: #ffffff;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .meeting-options {
            margin-top: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .meeting-option {
            padding: 12px 16px;
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .meeting-option:hover {
            background: rgba(255, 255, 255, 0.8);
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        }
        
        .meeting-option:active {
            transform: translateY(0);
        }
        
        .meeting-option-title {
            font-weight: 590;
            margin-bottom: 4px;
            color: #1d1d1f;
            font-size: 15px;
            letter-spacing: -0.1px;
        }
        
        .meeting-option-date {
            font-size: 13px;
            color: #86868b;
            letter-spacing: -0.05px;
        }
        
        /* Structured Summary Styling */
        .summary-container {
            max-width: 100%;
        }
        
        .summary-header {
            font-size: 22px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
            letter-spacing: -0.4px;
        }
        
        .summary-section {
            margin-bottom: 24px;
            animation: fadeIn 0.4s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .summary-section-title {
            font-size: 16px;
            font-weight: 590;
            color: #1d1d1f;
            margin-bottom: 10px;
            padding: 8px 0;
            letter-spacing: -0.2px;
        }
        
        .summary-section-content {
            padding: 0;
            line-height: 1.6;
            color: #424245;
            font-size: 15px;
            letter-spacing: -0.1px;
        }
        
        .summary-section-content ul,
        .summary-section-content ol {
            margin: 12px 0;
            padding-left: 24px;
        }
        
        .summary-section-content li {
            margin: 6px 0;
        }
        
        .summary-section-content h3 {
            font-size: 15px;
            font-weight: 590;
            color: #1d1d1f;
            margin: 16px 0 8px 0;
            letter-spacing: -0.2px;
        }
        
        .summary-section-content h4 {
            font-size: 14px;
            font-weight: 590;
            color: #424245;
            margin: 12px 0 6px 0;
            letter-spacing: -0.15px;
        }
        
        .summary-section-content p {
            margin: 10px 0;
        }
        
        .action-items-group {
            margin: 16px 0;
            padding: 14px 16px;
            background: rgba(0, 0, 0, 0.02);
            border-radius: 12px;
            border: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .action-items-group h4 {
            color: #1d1d1f;
            margin-bottom: 10px;
            font-weight: 590;
            letter-spacing: -0.2px;
        }
        
        .action-item {
            padding: 8px 0;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .action-item:last-child {
            border-bottom: none;
        }
        
        .participants-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        
        .participant-tag {
            padding: 4px 12px;
            background: rgba(0, 0, 0, 0.05);
            color: #424245;
            border-radius: 12px;
            font-size: 13px;
            letter-spacing: -0.05px;
            border: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .date-info {
            color: #86868b;
            font-size: 13px;
            margin: 6px 0;
            letter-spacing: -0.05px;
        }
        
        /* macOS-style Assistant Card */
        .assistant-card {
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 2px 16px rgba(0, 0, 0, 0.08), 0 1px 0 rgba(255, 255, 255, 0.8) inset;
            border: 0.5px solid rgba(0, 0, 0, 0.08);
            padding: 24px 28px;
            margin: 0;
            max-width: 100%;
            overflow: hidden;
            transition: box-shadow 0.2s ease;
        }
        
        .assistant-card:hover {
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12), 0 1px 0 rgba(255, 255, 255, 0.8) inset;
        }
        
        .assistant-card-header {
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
            margin: 0 0 20px 0;
            padding-bottom: 16px;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
            letter-spacing: -0.5px;
        }
        
        .assistant-card-section {
            margin-bottom: 24px;
            padding-bottom: 20px;
        }
        
        .assistant-card-section:last-child {
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .assistant-card-divider {
            height: 0.5px;
            background: rgba(0, 0, 0, 0.08);
            margin: 24px 0;
            border: none;
        }
        
        .assistant-card h2 {
            font-size: 20px;
            font-weight: 600;
            color: #1d1d1f;
            margin: 0 0 16px 0;
            letter-spacing: -0.4px;
        }
        
        .assistant-card h3 {
            font-size: 17px;
            font-weight: 590;
            color: #1d1d1f;
            margin: 20px 0 12px 0;
            letter-spacing: -0.3px;
        }
        
        .assistant-card h4 {
            font-size: 15px;
            font-weight: 590;
            color: #424245;
            margin: 16px 0 8px 0;
            letter-spacing: -0.2px;
        }
        
        .assistant-card p {
            margin: 12px 0;
            line-height: 1.6;
            color: #424245;
            font-size: 15px;
            letter-spacing: -0.1px;
        }
        
        .assistant-card ul,
        .assistant-card ol {
            margin: 12px 0;
            padding-left: 24px;
        }
        
        .assistant-card li {
            margin: 8px 0;
            line-height: 1.6;
            color: #424245;
        }
        
        /* Follow-up Email Styling */
        .followup-email {
            background: #ffffff;
        }
        
        .followup-subject {
            font-size: 20px;
            font-weight: 600;
            color: #1d1d1f;
            margin: 0 0 20px 0;
            padding-bottom: 16px;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
            letter-spacing: -0.4px;
        }
        
        .followup-body {
            line-height: 1.7;
            color: #424245;
            font-size: 15px;
        }
        
        .followup-body p {
            margin: 14px 0;
        }
        
        .followup-signature {
            margin-top: 24px;
            padding-top: 20px;
            border-top: 0.5px solid rgba(0, 0, 0, 0.08);
            color: #86868b;
            font-size: 14px;
        }
        
        /* Enhanced Action Items in Cards */
        .assistant-card .action-items-group {
            margin: 20px 0;
            padding: 18px 20px;
            background: rgba(0, 0, 0, 0.02);
            border-radius: 12px;
            border: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .assistant-card .action-item {
            padding: 10px 0;
            border-bottom: 0.5px solid rgba(0, 0, 0, 0.06);
        }
        
        .assistant-card .action-item:last-child {
            border-bottom: none;
        }
        
        /* Decisions Styling */
        .decisions-list {
            margin: 16px 0;
            padding: 16px 20px;
            background: rgba(0, 122, 255, 0.03);
            border-radius: 12px;
            border: 0.5px solid rgba(0, 122, 255, 0.1);
        }
        
        .decision-item {
            padding: 10px 0;
            border-bottom: 0.5px solid rgba(0, 122, 255, 0.08);
        }
        
        .decision-item:last-child {
            border-bottom: none;
        }
        
        .decision-description {
            font-weight: 590;
            color: #1d1d1f;
            margin-bottom: 4px;
        }
        
        .decision-context {
            font-size: 14px;
            color: #86868b;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Meeting Assistant</h1>
        </div>
        <div class="chat-container" id="chatContainer">
            <div class="message assistant" style="animation-delay: 0.1s;">
                <div class="message-bubble">
                    Hello! I'm your Meeting Assistant. I can help you prepare for meetings, summarize past meetings, and generate follow-up emails. How can I help you today?
                </div>
            </div>
        </div>
        <div class="input-container">
            <input type="text" id="messageInput" placeholder="Type your message here...">
            <button id="sendButton">Send</button>
        </div>
    </div>
    
    <script>
        const chatContainer = document.getElementById('chatContainer');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        
        function formatStructuredSummary(text) {
            // Check if this looks like a structured summary (has markdown headers)
            if (!text.includes('#') && !text.includes('##')) {
                return text; // Not structured, return as-is
            }
            
            // Create card container
            const card = document.createElement('div');
            card.className = 'assistant-card';
            
            // Create container for structured summary
            const container = document.createElement('div');
            container.className = 'summary-container';
            
            // Normalize line breaks - handle both escaped and actual newlines
            const newlinePattern = new RegExp('\\\\n', 'g');
            const normalizedText = text.replace(newlinePattern, '\\n');
            const lines = normalizedText.split('\\n');
            
            let currentSection = null;
            let currentContent = [];
            let foundHeader = false;
            let inActionItemsGroup = false;
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                const trimmed = line.trim();
                
                // Check for main header (# Meeting Header)
                if (trimmed.startsWith('# ') && !trimmed.startsWith('##') && !foundHeader) {
                    const headerText = trimmed.substring(2).trim();
                    const header = document.createElement('h2');
                    header.className = 'assistant-card-header';
                    header.textContent = headerText;
                    container.appendChild(header);
                    foundHeader = true;
                }
                // Check for section headers (## Section Name)
                else if (trimmed.startsWith('## ')) {
                    // Save previous section if exists
                    if (currentSection) {
                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'summary-section-content';
                        contentDiv.innerHTML = formatContent(currentContent.join('\\n'));
                        currentSection.appendChild(contentDiv);
                    }
                    
                    // Add divider before new section (except first)
                    if (currentSection && container.children.length > 0) {
                        const divider = document.createElement('hr');
                        divider.className = 'assistant-card-divider';
                        container.appendChild(divider);
                    }
                    
                    // Create new section
                    currentSection = document.createElement('div');
                    currentSection.className = 'assistant-card-section';
                    
                    const sectionTitle = document.createElement('h3');
                    const titleText = trimmed.substring(3).replace(':', '').trim();
                    sectionTitle.textContent = titleText;
                    currentSection.appendChild(sectionTitle);
                    
                    currentContent = [];
                    container.appendChild(currentSection);
                    inActionItemsGroup = false;
                }
                // Regular content line
                else if (trimmed) {
                    currentContent.push(line);
                }
            }
            
            // Add last section's content
            if (currentSection && currentContent.length > 0) {
                const contentDiv = document.createElement('div');
                contentDiv.className = 'summary-section-content';
                contentDiv.innerHTML = formatContent(currentContent.join('\\n'));
                currentSection.appendChild(contentDiv);
            }
            
            card.appendChild(container);
            return card;
        }
        
        function formatFollowupEmail(data) {
            // Check if this is a follow-up email response
            if (typeof data === 'string') {
                // Try to parse if it's JSON string
                try {
                    data = JSON.parse(data);
                } catch (e) {
                    // Not JSON, might be plain text response
                    if (data.includes('Subject:') || data.includes('Follow-up:')) {
                        return formatFollowupText(data);
                    }
                    return null;
                }
            }
            
            if (!data || (!data.subject && !data.body)) {
                return null;
            }
            
            const card = document.createElement('div');
            card.className = 'assistant-card followup-email';
            
            // Subject
            if (data.subject) {
                const subject = document.createElement('h2');
                subject.className = 'followup-subject';
                subject.textContent = data.subject;
                card.appendChild(subject);
            }
            
            // Body
            if (data.body) {
                const bodyDiv = document.createElement('div');
                bodyDiv.className = 'followup-body';
                
                // Split body into paragraphs
                const paragraphs = data.body.split('\\n\\n').filter(p => p.trim());
                paragraphs.forEach(para => {
                    const trimmed = para.trim();
                    if (!trimmed) return;
                    
                    // Check if it's a list or formatted section
                    if (trimmed.startsWith('**') || trimmed.startsWith('*') || trimmed.match(/^\d+\./)) {
                        const p = document.createElement('p');
                        p.innerHTML = formatContent(trimmed);
                        bodyDiv.appendChild(p);
                    } else {
                        const p = document.createElement('p');
                        p.textContent = trimmed;
                        bodyDiv.appendChild(p);
                    }
                });
                
                card.appendChild(bodyDiv);
            }
            
            // Signature (if client_name or client_email present)
            if (data.client_name || data.client_email) {
                const signature = document.createElement('div');
                signature.className = 'followup-signature';
                if (data.client_name) {
                    signature.textContent = data.client_name;
                }
                if (data.client_email) {
                    signature.textContent += (data.client_name ? ' <' : '') + data.client_email + (data.client_name ? '>' : '');
                }
                card.appendChild(signature);
            }
            
            return card;
        }
        
        function formatFollowupText(text) {
            // Handle plain text follow-up responses
            const card = document.createElement('div');
            card.className = 'assistant-card followup-email';
            
            const lines = text.split('\\n');
            let subjectFound = false;
            let bodyStarted = false;
            const bodyLines = [];
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line.startsWith('Subject:') && !subjectFound) {
                    const subject = document.createElement('h2');
                    subject.className = 'followup-subject';
                    subject.textContent = line.replace('Subject:', '').trim();
                    card.appendChild(subject);
                    subjectFound = true;
                } else if (line && (subjectFound || bodyStarted)) {
                    bodyLines.push(line);
                    bodyStarted = true;
                }
            }
            
            if (bodyLines.length > 0) {
                const bodyDiv = document.createElement('div');
                bodyDiv.className = 'followup-body';
                bodyDiv.innerHTML = formatContent(bodyLines.join('\\n'));
                card.appendChild(bodyDiv);
            }
            
            return card;
        }
        
        function formatContent(content) {
            if (!content) return '';
            
            // Split into lines for processing
            const lines = content.split('\\n');
            let html = '';
            let inList = false;
            let inActionGroup = false;
            let inDecisionsList = false;
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                const trimmed = line.trim();
                
                if (!trimmed) {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    html += '<br>';
                    continue;
                }
                
                // Check for decisions section
                if (trimmed.includes('Decisions Made:') || trimmed.includes('Key Decisions:')) {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    if (!inDecisionsList) {
                        html += '<div class="decisions-list">';
                        inDecisionsList = true;
                    }
                    continue;
                }
                
                // Check for action items group header
                if (trimmed.includes('### Action Items for') || trimmed.includes('Action Items & Next Steps:')) {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    if (inDecisionsList) {
                        html += '</div>';
                        inDecisionsList = false;
                    }
                    const actionItemsPattern = new RegExp('### Action Items for (Client|User):');
                    const match = trimmed.match(actionItemsPattern);
                    if (match) {
                        html += '<div class="action-items-group"><h4>Action Items for ' + match[1] + '</h4>';
                        inActionGroup = true;
                    } else if (trimmed.includes('Action Items & Next Steps:')) {
                        html += '<div class="action-items-group"><h4>Action Items & Next Steps</h4>';
                        inActionGroup = true;
                    }
                }
                // Check for decision item (Decision: description (Context: context))
                else if (trimmed.startsWith('- Decision:') || trimmed.startsWith('* Decision:')) {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    if (!inDecisionsList) {
                        html += '<div class="decisions-list">';
                        inDecisionsList = true;
                    }
                    const decisionMatch = trimmed.match(/- Decision: (.+?)(?:\s+\(Context: (.+?)\))?$/);
                    if (decisionMatch) {
                        html += '<div class="decision-item">';
                        html += '<div class="decision-description">' + escapeHtml(decisionMatch[1]) + '</div>';
                        if (decisionMatch[2]) {
                            html += '<div class="decision-context">' + escapeHtml(decisionMatch[2]) + '</div>';
                        }
                        html += '</div>';
                    }
                }
                // Check for list item
                else if (new RegExp('^[-*] (.+)$').test(trimmed)) {
                    if (!inList) {
                        html += '<ul>';
                        inList = true;
                    }
                    const itemText = trimmed.substring(2).trim();
                    const itemClass = inActionGroup ? 'action-item' : '';
                    html += '<li class="' + itemClass + '">' + escapeHtml(itemText) + '</li>';
                }
                // Check for "None" in action items
                else if (trimmed === 'None' && inActionGroup) {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    html += '<p style="color: #86868b; font-style: italic;">None</p></div>';
                    inActionGroup = false;
                }
                // Regular paragraph
                else {
                    if (inList) {
                        html += '</ul>';
                        inList = false;
                    }
                    if (inActionGroup && !trimmed.includes('###')) {
                        // Close action group if we hit non-action content
                        html += '</div>';
                        inActionGroup = false;
                    }
                    if (inDecisionsList && !trimmed.includes('Decision:')) {
                        html += '</div>';
                        inDecisionsList = false;
                    }
                    // Convert markdown formatting
                    let formatted = escapeHtml(trimmed);
                    // Use RegExp constructor to avoid backslash issues in Python strings
                    const boldPattern = new RegExp('\\\\*\\\\*(.*?)\\\\*\\\\*', 'g');
                    const italicPattern = new RegExp('\\\\*(.*?)\\\\*', 'g');
                    formatted = formatted.replace(boldPattern, '<strong>$1</strong>');
                    formatted = formatted.replace(italicPattern, '<em>$1</em>');
                    html += '<p>' + formatted + '</p>';
                }
            }
            
            if (inList) {
                html += '</ul>';
            }
            if (inActionGroup) {
                html += '</div>';
            }
            if (inDecisionsList) {
                html += '</div>';
            }
            
            return html;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function addMessage(text, isUser = false, meetingOptions = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            
            // Add animation delay for smooth sequential appearance
            const messageCount = chatContainer.children.length;
            messageDiv.style.animationDelay = `${messageCount * 0.05}s`;
            
            if (isUser) {
                // User messages: keep simple bubble style
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.textContent = text;
                messageDiv.appendChild(bubble);
            } else {
                // Assistant messages: use card styling
                let cardContent = null;
                
                // Check if this is a follow-up email (has subject/body structure)
                if (text.includes('Subject:') || text.includes('Follow-up:') || 
                    (typeof text === 'object' && text.subject)) {
                    cardContent = formatFollowupEmail(text);
                }
                
                // Check if this is a structured summary
                if (!cardContent && (text.includes('# Meeting Header') || text.includes('## Overview'))) {
                    cardContent = formatStructuredSummary(text);
                }
                
                // If we have card content, use it; otherwise use simple bubble
                if (cardContent instanceof HTMLElement) {
                    // Remove bubble styling, use card directly
                    messageDiv.style.alignItems = 'stretch';
                    messageDiv.appendChild(cardContent);
                } else {
                    // Fallback to bubble for simple text
                    const bubble = document.createElement('div');
                    bubble.className = 'message-bubble';
                    bubble.textContent = text;
                    messageDiv.appendChild(bubble);
                }
            }
            
            if (meetingOptions && meetingOptions.length > 0) {
                const optionsDiv = document.createElement('div');
                optionsDiv.className = 'meeting-options';
                
                // Show all meeting options (not just 3)
                meetingOptions.forEach((option, index) => {
                    const optionDiv = document.createElement('div');
                    optionDiv.className = 'meeting-option';
                    optionDiv.style.animationDelay = `${(messageCount + index) * 0.05}s`;
                    optionDiv.innerHTML = `
                        <div class="meeting-option-title">${escapeHtml(option.title)}</div>
                        <div class="meeting-option-date">${escapeHtml(option.date)}</div>
                    `;
                    optionDiv.onclick = () => selectMeeting(option, index + 1);
                    optionsDiv.appendChild(optionDiv);
                });
                
                messageDiv.appendChild(optionsDiv);
            }
            
            chatContainer.appendChild(messageDiv);
            
            // Smooth scroll with slight delay for animation
            setTimeout(() => {
                chatContainer.scrollTo({
                    top: chatContainer.scrollHeight,
                    behavior: 'smooth'
                });
            }, 100);
        }
        
        async function selectMeeting(option, number) {
            // When user selects a meeting, send the selection with calendar_event_id
            const message = `Summarize meeting ${number}: ${option.title}`;
            messageInput.value = message;
            
            // Send the selection with calendar_event_id
            // Ensure we only pass null or a valid calendar event ID (string/number)
            const calendarEventId = option.calendar_event_id ? String(option.calendar_event_id) : null;
            const meetingId = option.meeting_id ? (typeof option.meeting_id === 'number' ? option.meeting_id : parseInt(option.meeting_id)) : null;
            await sendMessage(calendarEventId, meetingId);
        }
        
        async function sendMessage(selectedCalendarEventId = null, selectedMeetingId = null) {
            const message = messageInput.value.trim();
            if (!message) return;
            
            addMessage(message, true);
            messageInput.value = '';
            
            sendButton.disabled = true;
            sendButton.innerHTML = '<div class="loading"></div>';
            
            try {
                // Ensure selectedCalendarEventId is either null or a valid string/number
                // Reject any browser event objects (they have isTrusted property)
                let validCalendarEventId = null;
                if (selectedCalendarEventId !== null && selectedCalendarEventId !== undefined) {
                    // Check if it's a browser event object
                    if (typeof selectedCalendarEventId === 'object' && selectedCalendarEventId.isTrusted !== undefined) {
                        // This is a browser event object, ignore it
                        validCalendarEventId = null;
                    } else {
                        // Convert to string if it's a number, otherwise use as-is if string
                        validCalendarEventId = typeof selectedCalendarEventId === 'number' 
                            ? String(selectedCalendarEventId) 
                            : (typeof selectedCalendarEventId === 'string' ? selectedCalendarEventId : null);
                    }
                }
                
                // Ensure selectedMeetingId is either null or a valid number
                let validMeetingId = null;
                if (selectedMeetingId !== null && selectedMeetingId !== undefined) {
                    if (typeof selectedMeetingId === 'object' && selectedMeetingId.isTrusted !== undefined) {
                        validMeetingId = null;
                    } else {
                        validMeetingId = typeof selectedMeetingId === 'number' 
                            ? selectedMeetingId 
                            : (typeof selectedMeetingId === 'string' ? parseInt(selectedMeetingId) : null);
                    }
                }
                
                const requestBody = {
                    message: message,
                    user_id: 1,  // TEMPORARY until real auth is added
                    selected_meeting_id: validMeetingId,
                    selected_calendar_event_id: validCalendarEventId
                };
                
                // TEMPORARY DEBUG: Log request body
                console.log('[FRONTEND DEBUG] POST request body:', JSON.stringify(requestBody, null, 2));
                console.log('[FRONTEND DEBUG] user_id in requestBody:', requestBody.user_id);
                
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody)
                });
                
                const data = await response.json();
                
                // Check if response contains follow-up email structure
                let responseContent = data.response;
                if (data.extra_data && data.extra_data.debug && 
                    data.extra_data.debug.tool_output && 
                    data.extra_data.debug.tool_output.result) {
                    const toolResult = data.extra_data.debug.tool_output.result;
                    if (toolResult.subject || toolResult.body) {
                        responseContent = toolResult;
                    }
                }
                
                if (data.meeting_options && data.meeting_options.length > 0) {
                    addMessage(responseContent, false, data.meeting_options);
                } else {
                    addMessage(responseContent, false);
                }
            } catch (error) {
                addMessage('I encountered an error: ' + error.message + '. Please try again or provide more context.', false);
            } finally {
                sendButton.disabled = false;
                sendButton.innerHTML = 'Send';
            }
        }
        
        sendButton.addEventListener('click', () => sendMessage());
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

