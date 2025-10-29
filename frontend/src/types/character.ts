// Shared character types for the application

export interface CharacterTags {
  relationship: string;
  tone: string;
  characteristics: string;
}

export interface Character {
  character_id?: string;  // Optional when creating, present after saving
  name: string;
  occupation: string;
  age: number;
  gender: string;
  tags: CharacterTags;
  speaking_style?: string;
  appearance?: string;
  success?: boolean;
  errors?: string[];
}

export interface AvailableTags {
  relationship: string[];
  tone: string[];
  characteristics: string[];
}
