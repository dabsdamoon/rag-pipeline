import React, { useState } from 'react';
import StreamingChat from './components/StreamingChat';
import CharacterCreator from './components/CharacterCreator';
import RoleplayChat from './components/RoleplayChat';
import { Character } from './types/character';
import './styles/theme.css';
import './App.css';

type TabType = 'rag' | 'creator' | 'roleplay';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('roleplay');
  const [createdCharacter, setCreatedCharacter] = useState<Character | null>(null);

  const API_BASE_URL = process.env.REACT_APP_LOCAL_API_URL || `${window.location.protocol}//${window.location.hostname}:8001`;

  const handleCharacterCreated = (character: Character) => {
    setCreatedCharacter(character);
    // Automatically switch to roleplay tab after creating a character
    setActiveTab('roleplay');
  };

  const handleSwitchToCreator = () => {
    setActiveTab('creator');
  };

  return (
    <div className="App">
      <div className="app-header">
        <h1>🎭 AI Roleplay & RAG Assistant</h1>
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'creator' ? 'active' : ''}`}
            onClick={() => setActiveTab('creator')}
          >
            ✨ Create Character
          </button>
          <button
            className={`tab-button ${activeTab === 'roleplay' ? 'active' : ''}`}
            onClick={() => setActiveTab('roleplay')}
          >
            🎭 Roleplay Chat
          </button>
          <button
            className={`tab-button ${activeTab === 'rag' ? 'active' : ''}`}
            onClick={() => setActiveTab('rag')}
          >
            📚 RAG Assistant
          </button>
        </div>
      </div>

      <div className="app-content">
        {activeTab === 'creator' && (
          <CharacterCreator
            apiBaseUrl={API_BASE_URL}
            onCharacterCreated={handleCharacterCreated}
          />
        )}

        {activeTab === 'roleplay' && (
          <RoleplayChat
            apiBaseUrl={API_BASE_URL}
            selectedCharacter={createdCharacter}
            onCharacterSelect={handleSwitchToCreator}
          />
        )}

        {activeTab === 'rag' && (
          <StreamingChat />
        )}
      </div>
    </div>
  );
}

export default App;
