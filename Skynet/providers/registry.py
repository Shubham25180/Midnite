from .base import LLMProvider


def get_provider(role: str, cfg: dict) -> LLMProvider:
    """
    role: "llm1" or "llm2"
    cfg:  the full settings dict from config.load()

    Returns the correct LLMProvider for that role.
    Raises if the role is disabled or backend is unknown.
    """
    section = cfg.get(role)
    if not section:
        raise KeyError(f"No config section for role '{role}'")
    if not section.get("enabled"):
        raise RuntimeError(f"'{role}' is disabled in settings.yaml")

    backend = section.get("backend")
    model   = section.get("model", "")

    if backend == "ollama":
        from .ollama import OllamaProvider, _DEFAULT_CTX
        return OllamaProvider(
            model=model,
            num_ctx=section.get("num_ctx", _DEFAULT_CTX),
        )

    if backend == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(model=model)

    if backend == "llamacpp":
        from .llamacpp import LlamaCppProvider
        return LlamaCppProvider(
            model_path=section.get("model_path") or None,
            repo_id=section.get("repo_id") or None,
            filename=section.get("filename") or None,
            n_gpu_layers=section.get("n_gpu_layers", -1),
            n_ctx=section.get("n_ctx", 8192),
        )

    raise ValueError(f"Unknown backend '{backend}' for role '{role}'")
