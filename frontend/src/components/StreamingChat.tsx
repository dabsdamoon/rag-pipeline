import React, { useState, useRef, useEffect, useCallback } from 'react';
import { flushSync } from 'react-dom';
import '../styles/theme.css';
import './StreamingChat.css';

interface Message {
  id: string;
  content: string;
  type: 'user' | 'bot';
  isStreaming?: boolean;
  sources?: SourceReference[];
  domain?: string;
  strategy?: string;
}

interface SourceReference {
  source_id: string;
  page_number: number;
  relevance_score: number;
  excerpt: string;
  display_name: string;
  purchase_link: string;
}

type ApiTargetKey = 'local' | 'cloud';

interface ApiTargetOption {
  key: ApiTargetKey;
  label: string;
  url: string;
}

const DEFAULT_LOCAL_API_URL = process.env.REACT_APP_LOCAL_API_URL || `${window.location.protocol}//${window.location.hostname}:8001`;
const DEFAULT_CLOUDRUN_API_URL = process.env.REACT_APP_CLOUDRUN_API_URL || process.env.REACT_APP_API_URL || '';

const API_TARGET_OPTIONS: ApiTargetOption[] = [
  {
    key: 'cloud',
    label: 'Cloud Run API',
    url: DEFAULT_CLOUDRUN_API_URL,
  },
  {
    key: 'local',
    label: 'Local API',
    url: DEFAULT_LOCAL_API_URL,
  },
];

const API_TOKEN = process.env.REACT_APP_API_TOKEN;

const LANGUAGE_OPTIONS = [
  { code: 'English', name: 'English', flag: '🇺🇸', emoji: '🌍' },
  { code: 'Korean', name: '한국어', flag: '🇰🇷', emoji: '🌏' },
  { code: 'Japanese', name: '日本語', flag: '🇯🇵', emoji: '🌏' },
  { code: 'Chinese', name: '中文', flag: '🇨🇳', emoji: '🌏' },
  { code: 'Spanish', name: 'Español', flag: '🇪🇸', emoji: '🌍' },
  { code: 'French', name: 'Français', flag: '🇫🇷', emoji: '🌍' },
  { code: 'German', name: 'Deutsch', flag: '🇩🇪', emoji: '🌍' },
  { code: 'Portuguese', name: 'Português', flag: '🇵🇹', emoji: '🌍' },
];

interface Source {
  id: string;
  display_name: string;
  name: string;
  source_type: string;
}

const DEFAULT_MIN_RELEVANCE = Number(process.env.REACT_APP_MIN_RELEVANCE ?? '0.05');

const USER_VARIANTS = [
  { value: 'default', label: 'Default' },
  { value: 'ob', label: 'Obstetrics' },
];

const StreamingChat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('Korean');
  const [selectedDomain, setSelectedDomain] = useState<'books' | 'insurance'>('books');
  const envDefaultTarget = (process.env.REACT_APP_DEFAULT_API_TARGET || '').toLowerCase() as ApiTargetKey;
  const resolveTarget = (target: ApiTargetKey | undefined): ApiTargetKey => {
    const found = API_TARGET_OPTIONS.find(option => option.key === target && option.url);
    if (found) {
      return found.key;
    }
    if (DEFAULT_CLOUDRUN_API_URL) {
      return 'cloud';
    }
    return 'local';
  };
  const initialTarget = resolveTarget(envDefaultTarget);
  const getApiUrl = (target: ApiTargetKey): string => {
    const option = API_TARGET_OPTIONS.find(item => item.key === target);
    return option && option.url ? option.url : DEFAULT_LOCAL_API_URL;
  };
  const [selectedApiTarget, setSelectedApiTarget] = useState<ApiTargetKey>(initialTarget);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(() => getApiUrl(initialTarget));
  const [allSources, setAllSources] = useState<Source[]>([]);
  const [availableSources, setAvailableSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [showReferences, setShowReferences] = useState(false);
  const [minRelevanceScore, setMinRelevanceScore] = useState<number>(DEFAULT_MIN_RELEVANCE);
  const [userLayerEnabled, setUserLayerEnabled] = useState<boolean>(false);
  const [userVariant, setUserVariant] = useState<string>('default');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [obUserVariables, setObUserVariables] = useState({
    username: '',
    age: '',
    address: '',
    is_pregnant: '',
    estimated_delivery_date: '',
    number_of_children: '',
    insurance_provider: '',
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    setApiBaseUrl(getApiUrl(selectedApiTarget));
  }, [selectedApiTarget]);

  useEffect(() => {
    setAllSources([]);
    setAvailableSources([]);
    setSelectedSourceIds([]);
  }, [apiBaseUrl]);

  const fetchAvailableSources = useCallback(async () => {
    if (!apiBaseUrl) {
      console.warn('API base URL is not configured. Skipping sources fetch.');
      return;
    }

    try {
      const headers: Record<string, string> = {};
      if (selectedApiTarget === 'cloud' && API_TOKEN) {
        headers['Authorization'] = `Bearer ${API_TOKEN}`;
      }
      const response = await fetch(`${apiBaseUrl}/sources`, {
        headers,
      });
      if (response.ok) {
        const data = await response.json();
        const sources: Source[] = data.sources.map((source: any) => ({
          id: source.source_id,
          display_name: source.display_name,
          name: source.name,
          source_type: source.source_type
        }));
        setAllSources(sources);
      } else {
        console.warn('Failed to fetch sources:', response.statusText);
      }
    } catch (error) {
      console.error('Failed to fetch sources:', error);
    }
  }, [apiBaseUrl, selectedApiTarget]);

  const filterSourcesByDomain = useCallback(() => {
    const targetType = selectedDomain === 'books' ? 'book' : 'insurance';
    const filtered = allSources.filter(source => source.source_type === targetType);
    setAvailableSources(filtered);
    
    // Reset selected source IDs when domain changes
    setSelectedSourceIds([]);
  }, [selectedDomain, allSources]);

  useEffect(() => {
    fetchAvailableSources();
  }, [fetchAvailableSources]);

  // Filter sources by domain when domain changes
  useEffect(() => {
    filterSourcesByDomain();
  }, [filterSourcesByDomain]);

  // Initialize welcome message on component mount
  useEffect(() => {
    if (!isInitialized) {
      const initialMessage = {
        id: '1',
        content: getWelcomeMessage(selectedLanguage),
        type: 'bot' as const
      };
      setMessages([initialMessage]);
      setIsInitialized(true);
    }
  }, [isInitialized, selectedLanguage]);

  const generateId = () => Math.random().toString(36).substr(2, 9);

  const getWelcomeMessage = (language: string): string => {
    const welcomeMessages: { [key: string]: string } = {
      'English': "Hello! I'm your Houmy assistant, running right next you in the journey of building a good maternity care flow.",
      'Korean': "안녕하세요! 저는 Houmy 어시스턴트입니다. 좋은 산모 돌봄 과정을 만드는 여정에서 함께하겠습니다.",
      'Japanese': "こんにちは！私はあなたのHoumyアシスタントです。良い妊産婦ケアフローを構築する旅路で、あなたのすぐ隣で一緒に歩んでいきます。",
      'Chinese': "你好！我是您的Houmy助手，在建立良好孕产妇护理流程的旅程中与您并肩同行。",
      'Spanish': "¡Hola! Soy tu asistente Houmy, corriendo junto a ti en el viaje de construir un buen flujo de atención de maternidad.",
      'French': "Bonjour ! Je suis votre assistant Houmy, qui vous accompagne dans le voyage de construction d'un bon flux de soins de maternité.",
      'German': "Hallo! Ich bin Ihr Houmy-Assistent und begleite Sie auf dem Weg zum Aufbau eines guten Betreuungsablaufs für die Mutterschaft.",
      'Portuguese': "Olá! Eu sou seu assistente Houmy, correndo ao seu lado na jornada de construir um bom fluxo de cuidados de maternidade."
    };
    return welcomeMessages[language] || welcomeMessages['English'];
  };

  const handleLanguageChange = (language: string) => {
    setSelectedLanguage(language);
    console.log('🌍 Language changed to:', language);
    
    addMessage(getWelcomeMessage(language), 'bot');
  };

  const handleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds(prev => {
      if (prev.includes(sourceId)) {
        const updated = prev.filter(id => id !== sourceId);
        console.log('📚 Removed source:', sourceId, 'Selected sources:', updated);
        return updated;
      } else {
        const updated = [...prev, sourceId];
        console.log('📚 Added source:', sourceId, 'Selected sources:', updated);
        return updated;
      }
    });
  };

  const toggleAllSources = () => {
    if (selectedSourceIds.length === availableSources.length) {
      setSelectedSourceIds([]);
      console.log('📚 Deselected all sources');
    } else {
      const allSourceIds = availableSources.map(source => source.id);
      setSelectedSourceIds(allSourceIds);
      console.log('📚 Selected all sources:', allSourceIds);
    }
  };

  const addMessage = (content: string, type: 'user' | 'bot', isStreaming = false): string => {
    const id = generateId();
    const newMessage: Message = { id, content, type, isStreaming };
    
    console.log('➕ Adding message:', { id, content: content.substring(0, 50), type, isStreaming });
    setMessages(prev => [...prev, newMessage]);
    return id;
  };

  const updateMessage = (id: string, content: string, sources?: SourceReference[]) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === id 
          ? { ...msg, content, sources, isStreaming: false }
          : msg
      )
    );
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
    if (!inputValue.trim() || isStreaming) return;

    if (!apiBaseUrl) {
      setStatus('API URL이 설정되지 않았습니다.');
      setTimeout(() => setStatus(''), 3000);
      return;
    }

    const userMessage = inputValue.trim();
    setInputValue('');
    
    addMessage(userMessage, 'user');
    
    const botMessageId = addMessage('', 'bot', true);
    
    setIsStreaming(true);
    setStatus('생각 중...');

    abortControllerRef.current = new AbortController();

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (selectedApiTarget === 'cloud' && API_TOKEN) {
        headers['Authorization'] = `Bearer ${API_TOKEN}`;
      }

      const response = await fetch(`${apiBaseUrl}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMessage,
          language: selectedLanguage,
          domain: selectedDomain,
          session_id: `session_${Date.now()}`,
          user_id: 'demopage',
          source_ids: selectedSourceIds.length > 0 ? selectedSourceIds : undefined,
          max_tokens: null,
          min_relevance_score: minRelevanceScore,
          layer_config: buildLayerConfig(),
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      console.log('🔗 Response received, starting to stream...');
      console.log('🌍 Using language:', selectedLanguage);
      
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let done = false;

      // Server-Sent Events (SSE) streaming
      let buffer = '';
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          console.log('📦 Raw chunk received:', chunk);
          
          // Add chunk to buffer
          buffer += chunk;
          
          // Process complete SSE messages
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6); // Remove 'data: ' prefix
              if (data.trim()) {
                appendToMessage(botMessageId, data);
              }
            }
          }
        }
      }
      
      console.log('✅ Stream completed');
      
    } catch (error: any) {
      console.error('❌ Streaming error:', error);
      if (error.name === 'AbortError') {
        updateMessage(botMessageId, '요청이 취소되었습니다');
        setStatus('취소됨');
      } else {
        updateMessage(botMessageId, '죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다.');
        setStatus('오류 발생');
      }
    } finally {
      setIsStreaming(false);
      setMessages(prev => 
        prev.map(msg => 
          msg.id === botMessageId 
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
      setTimeout(() => setStatus(''), 3000);
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

  const formatRelevanceScore = (score: number) => {
    return `${(score * 100).toFixed(0)}%`;
  };

  const buildLayerConfig = (): Record<string, unknown> => {
    const config: Record<string, unknown> = {};

    if (userLayerEnabled) {
      if (userVariant === 'ob') {
        const trimmedObVars = Object.fromEntries(
          Object.entries(obUserVariables).map(([key, value]) => [key, value.trim()]),
        );
        config.user = {
          include: true,
          id: 'ob',
          variables: trimmedObVars,
        };
      } else {
        config.user = {
          include: true,
          id: 'default',
          variables: {},
        };
      }
    } else {
      config.user = { include: false };
    }

    return config;
  };

  return (
    <div className="chat-app">
      <div className="chat-container">
        {/* Sidebar Toggle Button */}
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          title={sidebarOpen ? "Close settings" : "Open settings"}
        >
          {sidebarOpen ? "✕" : "☰"}
        </button>

        {/* Sidebar */}
        <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="sidebar-content">
            <div className="sidebar-header">
              <h2>🏠 Houmy RAG Assistant</h2>
              <div className="sidebar-subtitle">
                AI-powered document assistant with multilingual support
              </div>
            </div>

            {/* Controls Section */}
            <div className="controls-section">
              {/* API Target Selection */}
              <div className="control-group">
                <label>
                  ☁️ API Target
                </label>
                <select
                  value={selectedApiTarget}
                  onChange={(e) => setSelectedApiTarget(e.target.value as ApiTargetKey)}
                  disabled={isStreaming}
                >
                  {API_TARGET_OPTIONS.map((option) => (
                    <option key={option.key} value={option.key} disabled={!option.url}>
                      {option.label}
                      {!option.url ? ' (not configured)' : ''}
                    </option>
                  ))}
                </select>
                <div className="api-target-hint">
                  {apiBaseUrl ? apiBaseUrl : 'API URL is not configured'}
                </div>
              </div>

              {/* Domain Selection */}
              <div className="control-group">
                <label>
                  🎯 도메인 / Domain
                </label>
                <select
                  value={selectedDomain}
                  onChange={(e) => setSelectedDomain(e.target.value as 'books' | 'insurance')}
                  disabled={isStreaming}
                >
                  <option value="books">📚 Sources (RAG)</option>
                  <option value="insurance">🏥 Insurance Claims</option>
                </select>
              </div>

              {/* Minimum Relevance Score */}
              <div className="control-group">
                <label>
                  🎯 최소 관련도 / Min Relevance ({minRelevanceScore.toFixed(2)})
                </label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={minRelevanceScore}
                  disabled={isStreaming}
                  onChange={(event) => {
                    const nextValue = parseFloat(event.target.value);
                    if (!Number.isNaN(nextValue)) {
                      setMinRelevanceScore(Math.min(Math.max(nextValue, 0), 1));
                    }
                  }}
                />
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={minRelevanceScore}
                  disabled={isStreaming}
                  onChange={(event) => {
                    const nextValue = parseFloat(event.target.value);
                    if (!Number.isNaN(nextValue)) {
                      setMinRelevanceScore(Math.min(Math.max(nextValue, 0), 1));
                    }
                  }}
                />
              </div>

              {/* Language Selection */}
              <div className="control-group">
                <label>
                  🌍 언어 / Language
                </label>
                <select
                  value={selectedLanguage}
                  onChange={(e) => handleLanguageChange(e.target.value)}
                  disabled={isStreaming}
                >
                  {LANGUAGE_OPTIONS.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.flag} {lang.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* User Layer Configuration */}
              <div className="control-group">
                <label>
                  👤 사용자 레이어 / User Layer
                </label>
                <div className="toggle-row">
                  <input
                    type="checkbox"
                    checked={userLayerEnabled}
                    onChange={(event) => setUserLayerEnabled(event.target.checked)}
                    disabled={isStreaming}
                  />
                  <span>{userLayerEnabled ? 'Enabled' : 'Disabled'}</span>
                </div>
                {userLayerEnabled && (
                  <div className="layer-config">
                    <label>Variant</label>
                    <select
                      value={userVariant}
                      onChange={(event) => setUserVariant(event.target.value)}
                      disabled={isStreaming}
                    >
                      {USER_VARIANTS.map((variant) => (
                        <option key={variant.value} value={variant.value}>
                          {variant.label}
                        </option>
                      ))}
                    </select>
                    {userVariant === 'ob' && (
                      <div className="ob-grid">
                        <div className="input-group">
                          <label className="input-label">Username</label>
                          <input
                            type="text"
                            value={obUserVariables.username}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, username: event.target.value }))}
                            disabled={isStreaming}
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Age</label>
                          <input
                            type="text"
                            value={obUserVariables.age}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, age: event.target.value }))}
                            disabled={isStreaming}
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Address</label>
                          <input
                            type="text"
                            value={obUserVariables.address}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, address: event.target.value }))}
                            disabled={isStreaming}
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Is Pregnant</label>
                          <input
                            type="text"
                            value={obUserVariables.is_pregnant}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, is_pregnant: event.target.value }))}
                            disabled={isStreaming}
                            placeholder="yes / no"
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Estimated Delivery Date</label>
                          <input
                            type="text"
                            value={obUserVariables.estimated_delivery_date}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, estimated_delivery_date: event.target.value }))}
                            disabled={isStreaming}
                            placeholder="YYYY-MM-DD"
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Number of Children</label>
                          <input
                            type="text"
                            value={obUserVariables.number_of_children}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, number_of_children: event.target.value }))}
                            disabled={isStreaming}
                          />
                        </div>
                        <div className="input-group">
                          <label className="input-label">Insurance Provider</label>
                          <input
                            type="text"
                            value={obUserVariables.insurance_provider}
                            onChange={(event) => setObUserVariables(prev => ({ ...prev, insurance_provider: event.target.value }))}
                            disabled={isStreaming}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Source Selection - Show for both domains when sources are available */}
              {availableSources.length > 0 && (
                <div className="control-group">
                <label>
                  {selectedDomain === 'books' ? '📚' : '🏥'} 소스 선택 / Source Selection
                  {selectedSourceIds.length === 0 && (
                    <span className="selection-warning">
                      ⚠️ 소스를 선택해주세요 / Please select sources
                    </span>
                  )}
                </label>
                <div className="source-selection">
                  <div className="source-selection-header">
                    <span className="text-sm text-secondary">
                      {selectedSourceIds.length}/{availableSources.length} selected
                    </span>
                    <button 
                      className="toggle-all-btn"
                      onClick={toggleAllSources}
                      disabled={isStreaming}
                      title={selectedSourceIds.length === availableSources.length ? "모두 해제" : "모두 선택"}
                    >
                      {selectedSourceIds.length === availableSources.length ? "➖" : "➕"}
                    </button>
                  </div>
                  <div className="source-checkboxes">
                    {availableSources.map((source) => (
                      <label key={source.id} className="source-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedSourceIds.includes(source.id)}
                          onChange={() => handleSourceSelection(source.id)}
                          disabled={isStreaming}
                        />
                        <span className="source-name">{source.display_name}</span>
                      </label>
                    ))}
                    {availableSources.length === 0 && (
                      <span className="no-sources">사용 가능한 소스가 없습니다</span>
                    )}
                  </div>
                </div>
                </div>
              )}
            </div>

            {/* Status Section */}
            <div className="status-section">
              <div className="status-item">
                ☁️ {selectedApiTarget === 'cloud' ? 'Cloud Run API' : 'Local API'}
              </div>
              <div className="status-item">
                💬 {messages.length - 1} messages
              </div>
              <div className="status-item">
                {LANGUAGE_OPTIONS.find(lang => lang.code === selectedLanguage)?.emoji} {selectedLanguage}
              </div>
              <div className="status-item">
                {selectedDomain === 'books' ? '📚' : '🏥'} {selectedDomain}
              </div>
              <div className="status-item">
                🎯 {minRelevanceScore.toFixed(2)} min score
              </div>
              {availableSources.length > 0 && (
                <div className="status-item">
                  {selectedDomain === 'books' ? '📚' : '🏥'} {selectedSourceIds.length}/{availableSources.length} sources
                </div>
              )}
              {isStreaming && (
                <button onClick={cancelRequest} className="cancel-btn">
                  ⏹️ 취소
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className={`main-chat-area ${sidebarOpen ? 'sidebar-open' : ''}`}>
          {/* Messages Container */}
          <main className="messages-container">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.type}-message`}>
              {message.type === 'bot' && message.domain && (
                <div className="domain-indicator">
                  <span className="domain-badge">
                    {message.domain === 'books' ? '📚' : message.domain === 'insurance' ? '🏥' : '🤖'} 
                    {message.domain}
                  </span>
                  {message.strategy && (
                    <span className="strategy-name">{message.strategy}</span>
                  )}
                </div>
              )}
              <div className={`message-content ${message.isStreaming ? 'streaming' : ''}`}>
                {message.content}
                {message.isStreaming && (
                  <>
                    <span className="typing-indicator">
                      <span className="loading-dots">
                        <span></span>
                      </span>
                    </span>
                  </>
                )}
              </div>
              
              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <div 
                    className="sources-title clickable" 
                    onClick={() => setShowReferences(!showReferences)}
                    title={showReferences ? "참고 문헌 숨기기" : "참고 문헌 보기"}
                  >
                    📚 참고 문헌 / References 
                    <span className="toggle-icon">
                      {showReferences ? "🔽" : "▶️"}
                    </span>
                    <span className="reference-count">
                      ({message.sources.length})
                    </span>
                  </div>
                  {showReferences && (
                    <div className="sources-list">
                      {message.sources.map((source, idx) => (
                        <div key={idx} className="source-item">
                          <strong>{source.display_name}</strong> (
                          <a 
                            href={source.purchase_link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="source-link"
                          >
                            구매 링크
                          </a>
                          ) • 페이지 {source.page_number} • 
                          관련도 {formatRelevanceScore(source.relevance_score)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
            <div ref={messagesEndRef} />
          </main>

          {/* Input Section */}
          <div className="input-container">
          <textarea
            className="input-textarea"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={selectedLanguage === 'Korean' ? 
              "소스에 대해 무엇이든 물어보세요..." : 
              "Ask me anything about your documents..."
            }
            disabled={isStreaming}
            rows={1}
          />
          <button 
            onClick={sendMessage} 
            disabled={!inputValue.trim() || isStreaming}
            className="send-button"
          >
            {isStreaming ? (
              <>
                <span className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
                전송 중...
              </>
            ) : (
              <>
                ✨ 전송
              </>
            )}
          </button>
          </div>

          {/* Status Message */}
          {status && (
            <div className="status-message">
              {status}
              {isStreaming && (
                <span className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StreamingChat;
