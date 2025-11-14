"""Firebase service for user management and conversation history.

This module provides Firebase integration for:
1. User profile management (ID, name, age) - no authentication required
2. Conversation history tracking per user ID

Note: This is an outline. You'll need to:
- Install firebase-admin: pip install firebase-admin
- Provide Firebase credentials via config or environment variables
- Initialize Firebase Admin SDK with your project credentials
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from config import get_settings


class FirebaseService:
    """Service for managing users and conversation history in Firebase."""

    def __init__(self):
        """Initialize Firebase service.

        When ready to use Firebase:
        1. Install: pip install firebase-admin
        2. Download Firebase service account key JSON
        3. Set FIREBASE_CREDENTIALS_PATH in .env
        4. Set USE_FIREBASE=true in .env
        """
        self.settings = get_settings()
        self.db = None

        if self.settings.use_firebase:
            self._initialize_firebase()
        else:
            print("[Firebase] Firebase is disabled. Set USE_FIREBASE=true to enable.")

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK.

        Uncomment and configure when ready to use Firebase:
        """
        try:
            # import firebase_admin
            # from firebase_admin import credentials, firestore

            # # Initialize Firebase Admin SDK
            # if not firebase_admin._apps:
            #     cred = credentials.Certificate(self.settings.firebase_credentials_path)
            #     firebase_admin.initialize_app(cred, {
            #         'projectId': self.settings.firebase_project_id,
            #         'databaseURL': self.settings.firebase_database_url
            #     })

            # # Get Firestore client
            # self.db = firestore.client()
            # print("[Firebase] Firebase initialized successfully")

            print("[Firebase] Firebase initialization is commented out. Uncomment code to enable.")
        except Exception as e:
            print(f"[Firebase] Failed to initialize Firebase: {e}")
            self.db = None

    # -------------------------------------------------------------------------
    # User Management
    # -------------------------------------------------------------------------

    def create_user(self, user_id: str, name: str, age: int) -> Dict[str, Any]:
        """Create a new user profile.

        Args:
            user_id: Unique user identifier (no authentication required)
            name: User's name
            age: User's age

        Returns:
            User profile dictionary

        Firebase structure:
        users/{user_id}:
            - user_id: string
            - name: string
            - age: number
            - created_at: timestamp
            - updated_at: timestamp
        """
        if not self.db:
            # Fallback for when Firebase is not configured
            return {
                "user_id": user_id,
                "name": name,
                "age": age,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "firebase_enabled": False
            }

        # When Firebase is enabled, uncomment:
        # user_data = {
        #     "user_id": user_id,
        #     "name": name,
        #     "age": age,
        #     "created_at": firestore.SERVER_TIMESTAMP,
        #     "updated_at": firestore.SERVER_TIMESTAMP
        # }
        # self.db.collection('users').document(user_id).set(user_data)
        # return {**user_data, "firebase_enabled": True}

        return {
            "user_id": user_id,
            "name": name,
            "age": age,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "firebase_enabled": False
        }

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID.

        Args:
            user_id: User identifier

        Returns:
            User profile dictionary or None if not found
        """
        if not self.db:
            # Fallback when Firebase is not configured
            return None

        # When Firebase is enabled, uncomment:
        # user_ref = self.db.collection('users').document(user_id)
        # user_doc = user_ref.get()
        # if user_doc.exists:
        #     return user_doc.to_dict()
        # return None

        return None

    def update_user(self, user_id: str, name: Optional[str] = None, age: Optional[int] = None) -> bool:
        """Update user profile.

        Args:
            user_id: User identifier
            name: New name (optional)
            age: New age (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            return False

        # When Firebase is enabled, uncomment:
        # update_data = {"updated_at": firestore.SERVER_TIMESTAMP}
        # if name is not None:
        #     update_data["name"] = name
        # if age is not None:
        #     update_data["age"] = age
        #
        # self.db.collection('users').document(user_id).update(update_data)
        # return True

        return False

    # -------------------------------------------------------------------------
    # Conversation History
    # -------------------------------------------------------------------------

    def save_conversation(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a conversation turn to Firebase.

        Args:
            user_id: User identifier
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
            metadata: Optional metadata (sources, tokens, etc.)

        Returns:
            Conversation ID

        Firebase structure:
        conversations/{user_id}/messages/{conversation_id}:
            - user_id: string
            - session_id: string
            - user_message: string
            - assistant_message: string
            - metadata: object
            - timestamp: timestamp
        """
        if not self.db:
            # Generate a conversation ID for fallback
            conv_id = f"{user_id}_{session_id}_{datetime.utcnow().timestamp()}"
            print(f"[Firebase] Would save conversation: {conv_id} (Firebase disabled)")
            return conv_id

        # When Firebase is enabled, uncomment:
        # conversation_data = {
        #     "user_id": user_id,
        #     "session_id": session_id,
        #     "user_message": user_message,
        #     "assistant_message": assistant_message,
        #     "metadata": metadata or {},
        #     "timestamp": firestore.SERVER_TIMESTAMP
        # }
        #
        # # Save to subcollection under user
        # conv_ref = self.db.collection('conversations').document(user_id).collection('messages').add(conversation_data)
        # return conv_ref[1].id

        conv_id = f"{user_id}_{session_id}_{datetime.utcnow().timestamp()}"
        return conv_id

    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to retrieve
            session_id: Filter by session (optional)

        Returns:
            List of conversation dictionaries, ordered by timestamp (newest first)
        """
        if not self.db:
            return []

        # When Firebase is enabled, uncomment:
        # query = self.db.collection('conversations').document(user_id).collection('messages')
        #
        # if session_id:
        #     query = query.where('session_id', '==', session_id)
        #
        # query = query.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
        # docs = query.stream()
        #
        # conversations = []
        # for doc in docs:
        #     conv_data = doc.to_dict()
        #     conv_data['id'] = doc.id
        #     conversations.append(conv_data)
        #
        # return conversations

        return []

    def delete_user_conversations(self, user_id: str, session_id: Optional[str] = None) -> int:
        """Delete conversation history for a user.

        Args:
            user_id: User identifier
            session_id: Delete only this session (optional)

        Returns:
            Number of conversations deleted
        """
        if not self.db:
            return 0

        # When Firebase is enabled, uncomment:
        # query = self.db.collection('conversations').document(user_id).collection('messages')
        #
        # if session_id:
        #     query = query.where('session_id', '==', session_id)
        #
        # docs = query.stream()
        # deleted_count = 0
        #
        # for doc in docs:
        #     doc.reference.delete()
        #     deleted_count += 1
        #
        # return deleted_count

        return 0

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Check if Firebase is enabled and configured."""
        return self.db is not None

    def get_status(self) -> Dict[str, Any]:
        """Get Firebase service status."""
        return {
            "enabled": self.settings.use_firebase,
            "configured": self.db is not None,
            "project_id": self.settings.firebase_project_id,
            "database_url": self.settings.firebase_database_url
        }


# Singleton instance
_firebase_service: Optional[FirebaseService] = None


def get_firebase_service() -> FirebaseService:
    """Get or create Firebase service instance."""
    global _firebase_service
    if _firebase_service is None:
        _firebase_service = FirebaseService()
    return _firebase_service
