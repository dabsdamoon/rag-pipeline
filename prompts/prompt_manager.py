"""Prompt management utilities driven by YAML-based personalization layers."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .guidelines import DICT_LANGUAGE_GUIDELINES

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency handled at runtime
    yaml = None

_PROMPT_DIRECTIVE_PATTERN = re.compile(r"\{\{\s*([^{}]+)\s*\}\}")


@dataclass
class LayerConfig:
    """Configuration for a single prompt layer."""

    layer_id: str
    template: str
    required: bool

    def __post_init__(self) -> None:
        if not self.layer_id:
            raise ValueError("Layer id must be provided")


@dataclass
class LayerOutput:
    """Rendered output metadata for a layer."""

    layer_id: str
    variant: Optional[str]
    prompt: str
    template: str
    required: bool
    rendered: str = ""


@dataclass
class PromptRenderResult:
    """Final composed prompt along with per-layer metadata."""

    prompt: str
    layers: List[LayerOutput]


class PromptManager:
    """Prompt builder that composes layered prompts from YAML configuration."""

    def __init__(
        self,
        prompts_package: str = "prompts",
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        if yaml is None:
            raise ModuleNotFoundError(
                "PyYAML is required to use PromptManager. Install it with `pip install PyYAML`."
            )
        self.prompts_package = prompts_package
        self.base_path = Path(importlib.import_module(prompts_package).__file__).resolve().parent
        self.config_path = Path(config_path) if config_path else self.base_path / "prompt_personalization.yml"

        self.layers: List[LayerConfig] = []
        self.guards: Dict[str, Any] = {}
        self._layer_sources: Dict[str, Dict[str, Any]] = {}

        self._load_configuration()
        self._load_layer_sources()

    # ---------------------------------------------------------------------
    # Configuration loading
    # ---------------------------------------------------------------------
    def _load_configuration(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Prompt personalization config not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as config_file:
            config_data = yaml.safe_load(config_file) or {}

        self.layers = [
            LayerConfig(
                layer_id=layer_entry.get("id"),
                template=layer_entry.get("template", ""),
                required=self._coerce_bool(layer_entry.get("required", False)),
            )
            for layer_entry in config_data.get("layers", [])
        ]

        self.guards = config_data.get("guards", {})

    def _load_layer_sources(self) -> None:
        for layer in self.layers:
            module_name = f"{self.prompts_package}.{layer.layer_id}"
            module = importlib.import_module(module_name)
            dictionary = self._extract_prompt_dictionary(module, layer.layer_id)
            self._layer_sources[layer.layer_id] = dictionary

    @staticmethod
    def _extract_prompt_dictionary(module: Any, layer_id: str) -> Dict[str, Any]:
        """Retrieve the dictionary containing prompt variants from a module."""

        candidates: List[Tuple[str, Dict[str, Any]]] = []
        for attribute, value in vars(module).items():
            if attribute.startswith("__"):
                continue
            if isinstance(value, dict):
                candidates.append((attribute, value))

        if not candidates:
            raise ValueError(f"Module '{module.__name__}' does not expose a prompt dictionary")

        # Prefer dictionaries whose name references the layer id for clarity.
        for attribute, value in candidates:
            if layer_id.lower() in attribute.lower():
                return value

        # Fall back to the first discovered dictionary.
        return candidates[0][1]

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def available_layers(self) -> List[str]:
        return [layer.layer_id for layer in self.layers]

    def available_variants(self, layer_id: str) -> Iterable[str]:
        source = self._layer_sources.get(layer_id)
        if source is None:
            raise KeyError(f"Layer '{layer_id}' not loaded")
        return source.keys()

    # ------------------------------------------------------------------
    def generate_prompt(
        self,
        selections: Dict[str, Any],
        global_context: Optional[Dict[str, Any]] = None,
        include_meta: bool = False,
    ) -> Union[str, PromptRenderResult]:
        """Compose the final prompt from the configured layers.

        Args:
            selections: Mapping of layer ids to selection descriptors. A descriptor
                can be either a string variant key or a dictionary with keys such
                as `id`/`type` and `variables`.
            global_context: Additional context made available during template
                rendering (e.g., `{"language": "English"}`).
            include_meta: When True, return a :class:`PromptRenderResult` containing
                per-layer metadata alongside the final prompt string.
        """

        layer_outputs: List[LayerOutput] = []
        context_root: Dict[str, Any] = dict(global_context or {})

        for layer in self.layers:
            selection = selections.get(layer.layer_id)

            if selection is None:
                if layer.required:
                    raise ValueError(f"Missing selection for required layer '{layer.layer_id}'")
                # Optional layers are omitted entirely.
                continue

            prompt_text, variant_key = self._resolve_layer_prompt(layer.layer_id, selection)

            layer_context = {
                "prompt": prompt_text,
                "variant": variant_key,
            }
            context_root[layer.layer_id] = layer_context

            layer_outputs.append(
                LayerOutput(
                    layer_id=layer.layer_id,
                    variant=variant_key,
                    prompt=prompt_text,
                    template=layer.template,
                    required=layer.required,
                )
            )

        rendered_sections: List[str] = []
        for layer_output in layer_outputs:
            template = self._get_layer_template(layer_output.layer_id)
            rendered = self._render_template(template, context_root)
            if rendered.strip():
                rendered_sections.append(rendered.strip())
            layer_output.rendered = rendered

        final_prompt = "\n\n".join(rendered_sections).strip()

        if include_meta:
            return PromptRenderResult(prompt=final_prompt, layers=layer_outputs)
        
        return final_prompt

    def build_user_prompt(
        self,
        query: str,
        language: str = "English",
        context_docs: Optional[List[Dict[str, Any]]] = None,
        domain: Optional[str] = None,
        source_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> str:
        """Convenience wrapper used by the RAG pipeline for prompt composition."""

        selections = self._default_selections(
            query=query,
            language=language,
            context_docs=context_docs,
            domain=domain,
            source_metadata=source_metadata,
            layer_config=layer_config,
        )

        result = self.generate_prompt(selections, global_context={"language": language}, include_meta=False)

        return result

    # ------------------------------------------------------------------
    def _build_context_block(self, context_docs: List[Dict[str, Any]]) -> str:
        if not context_docs:
            return ""
        sections = []
        for idx, doc in enumerate(context_docs, start=1):
            content = doc.get("content", "").strip()
            if not content:
                continue
            sections.append(f"Source {idx}: {content}")
        return "\n\n".join(sections)

    @staticmethod
    def _current_datetime() -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()

    def _default_selections(
        self,
        *,
        query: str,
        language: str,
        context_docs: Optional[List[Dict[str, Any]]],
        domain: Optional[str],
        source_metadata: Optional[Dict[str, Dict[str, Any]]],
        layer_config: Optional[Dict[str, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        context_docs = context_docs or []
        source_metadata = source_metadata or {}
        domain = (domain or "books").strip().lower() or "books"
        preferences = layer_config or {}

        context_text = self._build_context_block(context_docs)
        company_name = None
        if domain == "insurance" and context_docs:
            primary_doc = context_docs[0]
            source_id = primary_doc.get("source_id")
            if source_id:
                metadata = source_metadata.get(source_id, {})
                company_name = metadata.get("display_name", source_id)

        context_info = {
            "query": query,
            "language": language,
            "domain": domain,
            "context_text": context_text,
            "company_name": company_name or "Insurance Provider",
        }

        selections: Dict[str, Any] = {}
        for layer in self.layers:
            preference = preferences.get(layer.layer_id, {})
            base_selection = self._construct_base_selection(
                layer_id=layer.layer_id,
                context=context_info,
                preference=preference,
            )

            include_override = preference.get("include")
            if include_override is not None:
                include_layer = bool(include_override)
            elif layer.required:
                include_layer = True
            else:
                include_layer = base_selection is not None

            if not include_layer:
                continue

            if base_selection is None:
                base_selection = {
                    "id": preference.get("id", "default"),
                    "variables": preference.get("variables", {}),
                }

            selections[layer.layer_id] = self._merge_selection(base_selection, preference)

        return selections

    def _construct_base_selection(
        self,
        *,
        layer_id: str,
        context: Dict[str, Any],
        preference: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if layer_id == "system":
            identity = preference.get("id") or "generic"
            return {"id": identity, "variables": {"currentDateTime": self._current_datetime()}}

        if layer_id == "domain":
            domain_variant = preference.get("id") or context.get("domain") or "books"
            return {
                "id": domain_variant,
                "variables": {
                    "language": context.get("language"),
                    "context": context.get("context_text"),
                    "company_name": context.get("company_name"),
                },
            }

        if layer_id == "query":
            return {
                "id": preference.get("id", "default"),
                "variables": {"question": context.get("query")},
            }

        if layer_id == "user":
            if not preference:
                return None
            return {
                "id": preference.get("id", "default"),
                "variables": preference.get("variables", {}),
            }

        if layer_id == "history":
            if not preference:
                return None
            return {
                "id": preference.get("id", "default"),
                "variables": preference.get("variables", {}),
            }

        # Unknown layer: include only if preference supplies data
        variables = preference.get("variables")
        if not variables and not preference.get("include"):
            return None
        return {
            "id": preference.get("id", "default"),
            "variables": variables or {},
        }

    def _resolve_layer_prompt(self, layer_id: str, selection: Any) -> Tuple[str, Optional[str]]:
        source = self._layer_sources.get(layer_id)
        if source is None:
            raise KeyError(f"Layer '{layer_id}' not loaded")

        if isinstance(selection, str):
            variant_key = selection
            variables: Dict[str, Any] = {}
        elif isinstance(selection, dict):
            if "prompt" in selection and not selection.get("id"):
                prompt_value = selection["prompt"]
                return str(prompt_value), selection.get("id")
            variant_key = selection.get("id") or selection.get("type") or selection.get("variant")
            if variant_key is None:
                raise ValueError(
                    f"Selection for layer '{layer_id}' must specify an 'id'/'type' when using a dictionary"
                )
            variables = selection.get("variables", {}) or {}
        else:
            raise TypeError(f"Unsupported selection type for layer '{layer_id}': {type(selection)!r}")

        if variant_key not in source:
            raise KeyError(f"Variant '{variant_key}' not defined for layer '{layer_id}'")

        variant = source[variant_key]
        if callable(variant):
            prompt_text = variant(**variables)
        elif isinstance(variant, str):
            prompt_text = variant.format(**variables) if variables else variant
        else:
            prompt_text = str(variant)

        return prompt_text, variant_key

    def _get_layer_template(self, layer_id: str) -> str:
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer.template
        raise KeyError(f"Template not found for layer '{layer_id}'")

    @staticmethod
    def _render_template(template: str, context: Dict[str, Any]) -> str:
        def lookup(path: str) -> str:
            parts = [segment.strip() for segment in path.split(".") if segment.strip()]
            value: Any = context
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return ""
            return "" if value is None else str(value)

        return _PROMPT_DIRECTIVE_PATTERN.sub(lambda match: lookup(match.group(1)), template)

    @staticmethod
    def _merge_selection(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        if "id" in override:
            merged["id"] = override["id"]
        if "variant" in override:
            merged["variant"] = override["variant"]
        if "prompt" in override:
            merged["prompt"] = override["prompt"]
        if "variables" in override:
            variables = dict(merged.get("variables", {}))
            variables.update(override.get("variables", {}))
            merged["variables"] = variables
        return merged

    # ------------------------------------------------------------------
    def build_prompt_messages(
        self,
        query: str,
        language: str = "English",
        context_docs: Optional[List[Dict[str, Any]]] = None,
        domain: Optional[str] = None,
        source_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[str, str, PromptRenderResult]:
        result = self.generate_prompt(
            selections=self._default_selections(
                query=query,
                language=language,
                context_docs=context_docs,
                domain=domain,
                source_metadata=source_metadata,
                layer_config=layer_config,
            ),
            global_context={"language": language},
            include_meta=True,
        )

        if not isinstance(result, PromptRenderResult):
            raise RuntimeError("Expected PromptRenderResult when include_meta=True")

        system_prompt = ""
        user_sections: List[str] = []
        for layer in result.layers:
            if not layer.rendered.strip():
                continue
            if layer.layer_id == "system":
                system_prompt = layer.rendered.strip()
            else:
                user_sections.append(layer.rendered.strip())

        if language.lower() in DICT_LANGUAGE_GUIDELINES:
            language_guideline_string = DICT_LANGUAGE_GUIDELINES[language.lower()]
            system_prompt += f"\n\n{language_guideline_string}"

        user_prompt = "\n\n".join(user_sections).strip()
        if not user_prompt:
            user_prompt = result.prompt

        return system_prompt, user_prompt, result


if __name__ == "__main__":
    manager = PromptManager()

    sample_prompt = manager.generate_prompt(
        selections={
            "system": {"id": "houmy", "variables": {"currentDateTime": manager._current_datetime()}},
            "domain": {
                "id": "books",
                "variables": {
                    "language": "English",
                    "context": "Sample context paragraph...",
                },
            },
            "user": {
                "id": "general",
                "variables": {"profile": "Expecting parent researching prenatal care."},
            },
            "query": {"id": "general", "variables": {"question": "What exercises are safe during the third trimester?"}},
        },
        global_context={"language": "English"},
    )
    print("Generated prompt:\n")
    print(sample_prompt)
