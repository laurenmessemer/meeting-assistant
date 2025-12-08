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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 800px;
            height: 90vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 600;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        
        .message {
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
        }
        
        .message.user {
            align-items: flex-end;
        }
        
        .message.assistant {
            align-items: flex-start;
        }
        
        .message-bubble {
            max-width: 70%;
            padding: 12px 18px;
            border-radius: 18px;
            word-wrap: break-word;
            line-height: 1.5;
        }
        
        .message.user .message-bubble {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .message.assistant .message-bubble {
            background: white;
            color: #333;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
        }
        
        #messageInput {
            flex: 1;
            padding: 12px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        #messageInput:focus {
            border-color: #667eea;
        }
        
        #sendButton {
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        #sendButton:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        #sendButton:active {
            transform: translateY(0);
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .meeting-options {
            margin-top: 10px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .meeting-option {
            padding: 12px 18px;
            background: #f0f0f0;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .meeting-option:hover {
            background: #e0e0e0;
        }
        
        .meeting-option-title {
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .meeting-option-date {
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Meeting Assistant</h1>
        </div>
        <div class="chat-container" id="chatContainer">
            <div class="message assistant">
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
        
        function addMessage(text, isUser = false, meetingOptions = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.textContent = text;
            
            messageDiv.appendChild(bubble);
            
            if (meetingOptions && meetingOptions.length > 0) {
                const optionsDiv = document.createElement('div');
                optionsDiv.className = 'meeting-options';
                
                // Show all meeting options (not just 3)
                meetingOptions.forEach((option, index) => {
                    const optionDiv = document.createElement('div');
                    optionDiv.className = 'meeting-option';
                    optionDiv.innerHTML = `
                        <div class="meeting-option-title">${option.title}</div>
                        <div class="meeting-option-date">${option.date}</div>
                    `;
                    optionDiv.onclick = () => selectMeeting(option, index + 1);
                    optionsDiv.appendChild(optionDiv);
                });
                
                messageDiv.appendChild(optionsDiv);
            }
            
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        async function selectMeeting(option, number) {
            // When user selects a meeting, send the selection with calendar_event_id
            const message = `Summarize meeting ${number}: ${option.title}`;
            messageInput.value = message;
            
            // Send the selection with calendar_event_id
            await sendMessage(option.calendar_event_id || null, option.meeting_id || null);
        }
        
        async function sendMessage(selectedCalendarEventId = null, selectedMeetingId = null) {
            const message = messageInput.value.trim();
            if (!message) return;
            
            addMessage(message, true);
            messageInput.value = '';
            
            sendButton.disabled = true;
            sendButton.innerHTML = '<div class="loading"></div>';
            
            try {
                const requestBody = {
                    message: message,
                    selected_meeting_id: selectedMeetingId,
                    selected_calendar_event_id: selectedCalendarEventId
                };
                
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody)
                });
                
                const data = await response.json();
                
                if (data.meeting_options && data.meeting_options.length > 0) {
                    addMessage(data.response, false, data.meeting_options);
                } else {
                    addMessage(data.response, false);
                }
            } catch (error) {
                addMessage('I encountered an error: ' + error.message + '. Please try again or provide more context.', false);
            } finally {
                sendButton.disabled = false;
                sendButton.innerHTML = 'Send';
            }
        }
        
        sendButton.addEventListener('click', sendMessage);
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

