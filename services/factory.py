"""
Service Factory - Centralized service initialization

This module provides a factory pattern for initializing all application services
with consistent error handling and logging.
"""
import os
from typing import Dict, Any, Tuple, Type
from modules.rag_pipeline import RAGPipeline
from modules.character_creation_pipeline import CharacterCreationPipeline
from prompts.prompt_manager import PromptManager
from services import get_firebase_service
from services.character_storage import CharacterStorageService
from services.roleplay_manager import RoleplayManager


class ServiceFactory:
    """
    Factory for initializing and managing application services.

    This factory centralizes service initialization logic, reducing code duplication
    and providing consistent error handling across all service instantiations.
    """

    # Service configuration: (name, class, kwargs)
    SERVICE_CONFIGS = [
        ("RAG Pipeline", RAGPipeline, lambda: {"test_with_chromadb": os.getenv("TEST_WITH_CHROMADB", "false").lower() == "true"}),
        ("Prompt Manager", PromptManager, lambda: {}),
        ("Firebase Service", None, lambda: {}),  # Special case - uses get_firebase_service()
        ("Character Creation Pipeline", CharacterCreationPipeline, lambda: {}),
        ("Character Storage Service", CharacterStorageService, lambda: {}),
        ("Roleplay Manager", RoleplayManager, lambda: {}),
    ]

    @staticmethod
    def _init_service(name: str, service_class: Type, kwargs_fn) -> Any:
        """
        Initialize a single service with error handling.

        Args:
            name: Human-readable service name for logging
            service_class: Class to instantiate
            kwargs_fn: Function that returns kwargs dict for initialization

        Returns:
            Initialized service instance

        Raises:
            Exception: If service initialization fails
        """
        print(f"🔧 Initializing {name}...")
        try:
            # Special case for Firebase service
            if name == "Firebase Service":
                service = get_firebase_service()
            else:
                kwargs = kwargs_fn()
                service = service_class(**kwargs)

            print(f"✅ {name} initialized successfully")
            return service
        except Exception as e:
            print(f"❌ Failed to initialize {name}: {e}")
            import traceback
            traceback.print_exc()
            raise

    @classmethod
    def initialize_services(cls) -> Dict[str, Any]:
        """
        Initialize all application services.

        Returns:
            Dictionary mapping service keys to initialized instances:
            {
                "rag_pipeline": RAGPipeline instance,
                "prompt_manager": PromptManager instance,
                "firebase_service": Firebase service instance,
                "character_pipeline": CharacterCreationPipeline instance,
                "character_storage": CharacterStorageService instance,
                "roleplay_manager": RoleplayManager instance,
            }

        Raises:
            Exception: If any service initialization fails
        """
        services = {}

        for name, service_class, kwargs_fn in cls.SERVICE_CONFIGS:
            # Convert display name to key (e.g., "RAG Pipeline" -> "rag_pipeline")
            key = name.lower().replace(" ", "_")
            services[key] = cls._init_service(name, service_class, kwargs_fn)

        return services

    @classmethod
    def get_service_info(cls) -> Dict[str, str]:
        """
        Get information about all configured services.

        Returns:
            Dictionary mapping service names to their class names
        """
        return {
            name: service_class.__name__ if service_class else "get_firebase_service()"
            for name, service_class, _ in cls.SERVICE_CONFIGS
        }
