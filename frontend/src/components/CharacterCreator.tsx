import React, { useState, useEffect } from 'react';
import { Character, AvailableTags } from '../types/character';
import './CharacterCreator.css';

interface CharacterCreatorProps {
  apiBaseUrl: string;
  onCharacterCreated?: (character: Character) => void;
}

const CharacterCreator: React.FC<CharacterCreatorProps> = ({ apiBaseUrl, onCharacterCreated }) => {
  const [name, setName] = useState('');
  const [occupation, setOccupation] = useState('');
  const [age, setAge] = useState<number>(25);
  const [gender, setGender] = useState('');
  const [relationship, setRelationship] = useState('');
  const [tone, setTone] = useState('');
  const [characteristics, setCharacteristics] = useState('');
  const [model, setModel] = useState('gpt-4o-mini');
  const [temperature, setTemperature] = useState<number>(0.7);

  const [availableTags, setAvailableTags] = useState<AvailableTags | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdCharacter, setCreatedCharacter] = useState<Character | null>(null);

  useEffect(() => {
    fetchAvailableTags();
  }, [apiBaseUrl]);

  const fetchAvailableTags = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/character/tags`);
      if (response.ok) {
        const data = await response.json();
        setAvailableTags(data);

        // Set default values
        if (data.relationship?.length > 0) setRelationship(data.relationship[0]);
        if (data.tone?.length > 0) setTone(data.tone[0]);
        if (data.characteristics?.length > 0) setCharacteristics(data.characteristics[0]);
      } else {
        setError('Failed to fetch available tags');
      }
    } catch (err) {
      setError('Failed to connect to API');
      console.error('Failed to fetch tags:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateCharacter = async () => {
    if (!name || !occupation || !gender) {
      setError('Please fill in all required fields (name, occupation, gender)');
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      // Step 1: Create character with LLM
      const createResponse = await fetch(`${apiBaseUrl}/character/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          occupation,
          age,
          gender,
          tags: {
            relationship,
            tone,
            characteristics
          },
          model,
          temperature
        })
      });

      if (!createResponse.ok) {
        throw new Error('Failed to create character');
      }

      const characterData = await createResponse.json();

      if (!characterData.success) {
        throw new Error(characterData.errors?.join(', ') || 'Character creation failed');
      }

      // Step 2: Save character to ChromaDB
      const saveResponse = await fetch(`${apiBaseUrl}/character/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character: characterData
        })
      });

      if (!saveResponse.ok) {
        throw new Error('Failed to save character to database');
      }

      const saveData = await saveResponse.json();

      // Add character_id to the character data
      const finalCharacter = {
        ...characterData,
        character_id: saveData.character_id
      };

      setCreatedCharacter(finalCharacter);

      // Notify parent component
      if (onCharacterCreated) {
        onCharacterCreated(finalCharacter);
      }

    } catch (err: any) {
      setError(err.message || 'Failed to create character');
      console.error('Character creation error:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleReset = () => {
    setName('');
    setOccupation('');
    setAge(25);
    setGender('');
    setCreatedCharacter(null);
    setError(null);

    // Reset to default tags
    if (availableTags) {
      if (availableTags.relationship?.length > 0) setRelationship(availableTags.relationship[0]);
      if (availableTags.tone?.length > 0) setTone(availableTags.tone[0]);
      if (availableTags.characteristics?.length > 0) setCharacteristics(availableTags.characteristics[0]);
    }
  };

  if (isLoading) {
    return (
      <div className="character-creator">
        <div className="loading">Loading character creation tools...</div>
      </div>
    );
  }

  return (
    <div className="character-creator">
      <div className="creator-header">
        <h2>🎭 Character Creator</h2>
        <p>Create your AI roleplay character with custom personality</p>
      </div>

      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}

      {createdCharacter ? (
        <div className="character-result">
          <div className="success-message">
            ✅ Character "{createdCharacter.name}" created successfully!
          </div>

          <div className="character-details">
            <h3>📋 Character Profile</h3>
            <div className="detail-grid">
              <div className="detail-item">
                <strong>Name:</strong> {createdCharacter.name}
              </div>
              <div className="detail-item">
                <strong>Occupation:</strong> {createdCharacter.occupation}
              </div>
              <div className="detail-item">
                <strong>Age:</strong> {createdCharacter.age}
              </div>
              <div className="detail-item">
                <strong>Gender:</strong> {createdCharacter.gender}
              </div>
            </div>

            <div className="detail-section">
              <h4>🗣️ Speaking Style</h4>
              <p>{createdCharacter.speaking_style}</p>
            </div>

            <div className="detail-section">
              <h4>👤 Appearance</h4>
              <p>{createdCharacter.appearance}</p>
            </div>

            <div className="detail-section">
              <h4>🏷️ Tags</h4>
              <div className="tags-display">
                <span className="tag">Relationship: {createdCharacter.tags.relationship}</span>
                <span className="tag">Tone: {createdCharacter.tags.tone}</span>
                <span className="tag">Characteristics: {createdCharacter.tags.characteristics}</span>
              </div>
            </div>
          </div>

          <button onClick={handleReset} className="reset-button">
            🔄 Create Another Character
          </button>
        </div>
      ) : (
        <div className="character-form">
          <div className="form-section">
            <h3>Basic Information</h3>

            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter character name"
                disabled={isCreating}
              />
            </div>

            <div className="form-group">
              <label>Occupation *</label>
              <input
                type="text"
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                placeholder="e.g., Software Engineer, Artist, Teacher"
                disabled={isCreating}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Age</label>
                <input
                  type="number"
                  value={age}
                  onChange={(e) => setAge(parseInt(e.target.value))}
                  min={1}
                  max={150}
                  disabled={isCreating}
                />
              </div>

              <div className="form-group">
                <label>Gender *</label>
                <input
                  type="text"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  placeholder="e.g., Male, Female, Non-binary"
                  disabled={isCreating}
                />
              </div>
            </div>
          </div>

          {availableTags && (
            <div className="form-section">
              <h3>Personality Tags</h3>

              <div className="form-group">
                <label>Relationship with User</label>
                <select
                  value={relationship}
                  onChange={(e) => setRelationship(e.target.value)}
                  disabled={isCreating}
                >
                  {availableTags.relationship.map((tag) => (
                    <option key={tag} value={tag}>{tag}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Communication Tone</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={isCreating}
                >
                  {availableTags.tone.map((tag) => (
                    <option key={tag} value={tag}>{tag}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Key Characteristics</label>
                <select
                  value={characteristics}
                  onChange={(e) => setCharacteristics(e.target.value)}
                  disabled={isCreating}
                >
                  {availableTags.characteristics.map((tag) => (
                    <option key={tag} value={tag}>{tag}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="form-section advanced-section">
            <h3>Advanced Settings</h3>

            <div className="form-group">
              <label>AI Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={isCreating}
              >
                <option value="gpt-4o-mini">GPT-4o Mini (Fast & Affordable)</option>
                <option value="gpt-4o">GPT-4o (Balanced)</option>
                <option value="gpt-4-turbo">GPT-4 Turbo (High Quality)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Creativity (Temperature: {temperature})</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                disabled={isCreating}
              />
              <div className="range-labels">
                <span>Conservative</span>
                <span>Creative</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleCreateCharacter}
            disabled={isCreating || !name || !occupation || !gender}
            className="create-button"
          >
            {isCreating ? (
              <>
                <span className="loading-spinner"></span>
                Creating Character...
              </>
            ) : (
              '✨ Create Character'
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default CharacterCreator;
