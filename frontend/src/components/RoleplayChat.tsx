import React, { useState, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import { Character } from '../types/character';
import './RoleplayChat.css';

interface Message {
  id: string;
  content: string;
  type: 'user' | 'character';
  isStreaming?: boolean;
  characterName?: string;
}

interface RoleplayChatProps {
  apiBaseUrl: string;
  selectedCharacter?: Character | null;
  onCharacterSelect?: () => void;
}

const RoleplayChat: React.FC<RoleplayChatProps> = ({
  apiBaseUrl,
  selectedCharacter: externalCharacter,
  onCharacterSelect
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string>(`roleplay_${Date.now()}`);

  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(externalCharacter || null);
  const [isLoadingCharacters, setIsLoadingCharacters] = useState(false);

  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini');
  const [temperature, setTemperature] = useState(0.8);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Update selected character when external character changes
  useEffect(() => {
    if (externalCharacter) {
      setSelectedCharacter(externalCharacter);
      // Start new conversation when character changes
      setSessionId(`roleplay_${Date.now()}`);
      setMessages([{
        id: '1',
        content: `Hello! I'm ${externalCharacter.name}. It's nice to meet you! How can I help you today?`,
        type: 'character',
        characterName: externalCharacter.name
      }]);
    }
  }, [externalCharacter]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!externalCharacter) {
      fetchCharacters();
    }
  }, [apiBaseUrl, externalCharacter]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchCharacters = async () => {
    setIsLoadingCharacters(true);
    try {
      const response = await fetch(`${apiBaseUrl}/character/list/all?limit=100`);
      if (response.ok) {
        const data = await response.json();
        // Filter out characters without character_id (shouldn't happen, but be safe)
        const validCharacters = data.characters.filter((c: Character) => c.character_id);
        setCharacters(validCharacters);

        // Auto-select first character if available
        if (validCharacters.length > 0 && !selectedCharacter) {
          handleCharacterSelection(validCharacters[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch characters:', error);
    } finally {
      setIsLoadingCharacters(false);
    }
  };

  const handleCharacterSelection = (character: Character) => {
    setSelectedCharacter(character);
    // Start new conversation when character changes
    setSessionId(`roleplay_${Date.now()}`);
    setMessages([{
      id: '1',
      content: `Hello! I'm ${character.name}. It's nice to meet you! How can I help you today?`,
      type: 'character',
      characterName: character.name
    }]);
  };

  const generateId = () => Math.random().toString(36).substr(2, 9);

  const addMessage = (content: string, type: 'user' | 'character', isStreaming = false, characterName?: string): string => {
    const id = generateId();
    const newMessage: Message = { id, content, type, isStreaming, characterName };
    setMessages(prev => [...prev, newMessage]);
    return id;
  };

  const appendToMessage = (id: string, newContent: string) => {
    flushSync(() => {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === id
            ? { ...msg, content: msg.content + newContent }
            : msg
        )
      );
    });
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isStreaming || !selectedCharacter || !selectedCharacter.character_id) return;

    const userMessage = inputValue.trim();
    setInputValue('');

    addMessage(userMessage, 'user');
    const characterMessageId = addMessage('', 'character', true, selectedCharacter.name);

    setIsStreaming(true);
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${apiBaseUrl}/roleplay/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: selectedCharacter.character_id,
          message: userMessage,
          session_id: sessionId,
          model: selectedModel,
          temperature: temperature,
          max_tokens: null
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;

        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data.trim()) {
                appendToMessage(characterMessageId, data);
              }
            }
          }
        }
      }

    } catch (error: any) {
      console.error('Roleplay streaming error:', error);
      if (error.name === 'AbortError') {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === characterMessageId
              ? { ...msg, content: 'Request cancelled', isStreaming: false }
              : msg
          )
        );
      } else {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === characterMessageId
              ? { ...msg, content: `Error: ${error.message}`, isStreaming: false }
              : msg
          )
        );
      }
    } finally {
      setIsStreaming(false);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === characterMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault();
      sendMessage();
    }
  };

  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const clearConversation = () => {
    if (selectedCharacter) {
      setSessionId(`roleplay_${Date.now()}`);
      setMessages([{
        id: '1',
        content: `Hello! I'm ${selectedCharacter.name}. It's nice to meet you! How can I help you today?`,
        type: 'character',
        characterName: selectedCharacter.name
      }]);
    }
  };

  if (!externalCharacter && isLoadingCharacters) {
    return (
      <div className="roleplay-chat">
        <div className="loading-state">Loading characters...</div>
      </div>
    );
  }

  if (!externalCharacter && characters.length === 0) {
    return (
      <div className="roleplay-chat">
        <div className="empty-state">
          <h3>🎭 No Characters Available</h3>
          <p>Create a character first to start roleplaying!</p>
          {onCharacterSelect && (
            <button onClick={onCharacterSelect} className="create-char-button">
              ✨ Create Character
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="roleplay-chat">
      <div className="roleplay-container">
        {/* Character List Sidebar */}
        {!externalCharacter && characters.length > 0 && (
          <div className="character-sidebar">
            <div className="sidebar-header">
              <h3>💬 Characters</h3>
              {onCharacterSelect && (
                <button onClick={onCharacterSelect} className="add-character-btn" title="Create new character">
                  ➕
                </button>
              )}
            </div>

            <div className="character-list">
              {characters.map((char) => (
                <div
                  key={char.character_id}
                  className={`character-card ${selectedCharacter?.character_id === char.character_id ? 'active' : ''}`}
                  onClick={() => !isStreaming && handleCharacterSelection(char)}
                >
                  <div className="character-avatar">
                    {char.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="character-details">
                    <div className="character-name">{char.name}</div>
                    <div className="character-occupation">{char.occupation}</div>
                    <div className="character-tags">
                      <span className="tag">{char.tags.tone}</span>
                      <span className="tag">{char.tags.characteristics}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main Chat Area */}
        <div className="chat-main">
          {/* Character Info Header */}
          {selectedCharacter && (
            <div className="character-header">
              <div className="character-info">
                <div className="char-avatar-large">
                  {selectedCharacter.name.charAt(0).toUpperCase()}
                </div>
                <div className="char-info-text">
                  <h2>{selectedCharacter.name}</h2>
                  <div className="character-meta">
                    <span>👔 {selectedCharacter.occupation}</span>
                    <span>•</span>
                    <span>🎂 {selectedCharacter.age} years old</span>
                    <span>•</span>
                    <span>🎵 {selectedCharacter.tags.tone}</span>
                  </div>
                </div>
              </div>

              <div className="header-controls">
                <button onClick={clearConversation} className="clear-button" disabled={isStreaming}>
                  🔄 New Chat
                </button>
              </div>
            </div>
          )}

          {/* Settings Panel */}
          <div className="settings-panel">
            <div className="setting-group">
              <label>🤖 Model:</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isStreaming}
              >
                <option value="gpt-4o-mini">GPT-4o Mini</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
              </select>
            </div>

            <div className="setting-group">
              <label>🎨 Creativity: {temperature.toFixed(1)}</label>
              <input
                type="range"
                min={0}
                max={1.5}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                disabled={isStreaming}
                className="temperature-slider"
              />
            </div>
          </div>

          {/* Messages Container */}
          <div className="messages-container">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.type}-message`}>
                {message.type === 'character' && (
                  <div className="message-header">
                    <div className="msg-avatar">
                      {message.characterName?.charAt(0).toUpperCase() || 'C'}
                    </div>
                    <div className="message-author">
                      {message.characterName || 'Character'}
                    </div>
                  </div>
                )}
                <div className={`message-content ${message.isStreaming ? 'streaming' : ''}`}>
                  {message.content}
                  {message.isStreaming && (
                    <span className="typing-indicator">
                      <span className="loading-dots">
                        <span></span>
                      </span>
                    </span>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Container */}
          <div className="input-container">
            <textarea
              className="input-textarea"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                selectedCharacter
                  ? `💬 Talk to ${selectedCharacter.name}...`
                  : 'Select a character to start chatting...'
              }
              disabled={isStreaming || !selectedCharacter}
              rows={2}
            />
            <div className="input-actions">
              <button
                onClick={sendMessage}
                disabled={!inputValue.trim() || isStreaming || !selectedCharacter}
                className="send-button"
              >
                {isStreaming ? (
                  <>
                    <span className="loading-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </span>
                    Sending...
                  </>
                ) : (
                  '✨ Send'
                )}
              </button>

              {isStreaming && (
                <button onClick={cancelRequest} className="cancel-button">
                  ⏹️ Stop
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RoleplayChat;
