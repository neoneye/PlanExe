"""
PROMPT> python -m worker_plan_internal.llm_util.ollama_info
"""
from dataclasses import dataclass
from typing import Optional

DEFAULT_OLLAMA_PORT = "11434"
FALLBACK_DOCKER_HOST = f"http://host.docker.internal:{DEFAULT_OLLAMA_PORT}"

@dataclass
class OllamaInfo:
    """
    Details about the Ollama service, including a list of available model names,
    a flag indicating whether the service is running, and an optional error message.
    """
    model_names: list[str]
    is_running: bool
    error_message: Optional[str] = None

    @staticmethod
    def _normalize_host(base_url: Optional[str]) -> Optional[str]:
        """Ensure the host has a scheme. None means use the client's default host/env."""
        if not base_url:
            return None
        if base_url.startswith(("http://", "https://")):
            return base_url
        return f"http://{base_url}"

    @classmethod
    def _candidate_hosts(cls, base_url: Optional[str]) -> list[Optional[str]]:
        """
        Return the list of hosts to try. If the user supplied a host, only try that.
        Otherwise, try the default client host first, then fall back to host.docker.internal
        to support containers talking to the host's Ollama daemon.
        """
        normalized = cls._normalize_host(base_url)
        if normalized:
            return [normalized]
        return [None, FALLBACK_DOCKER_HOST]

    @classmethod
    def obtain_info(cls, base_url: Optional[str] = None) -> 'OllamaInfo':
        """Retrieves information about the Ollama service."""
        try:
            # Only import ollama if it's available
            from ollama import Client
        except ImportError as e:
            error_message = f"OllamaInfo base_url={base_url}. The 'ollama' library was not found: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)

        errors = []
        for host in cls._candidate_hosts(base_url):
            try:
                client = Client(timeout=5) if host is None else Client(host=host, timeout=5)
                list_response = client.list()
                model_names = [model.model for model in list_response.models]
                return OllamaInfo(model_names=model_names, is_running=True, error_message=None)
            except ConnectionError as e:
                errors.append(f"host={host or 'default'} connection error: {e}")
            except Exception as e:
                errors.append(f"host={host or 'default'} unexpected error: {e}")

        error_message = "; ".join(errors) if errors else None
        return OllamaInfo(model_names=[], is_running=False, error_message=error_message)
    
    def is_model_available(self, find_model: str) -> bool:
        """
        Checks if a specific model is available.
        
        Args:
            find_model: Name of the model to check. Can be either a local Ollama model
                       or a HuggingFace GGUF model (prefixed with 'hf.co/').

        Returns:
            bool: True if the model is available or is a valid GGUF model path.
        """
        if not find_model:
            return False
            
        # Support direct use of GGUF models from HuggingFace
        if find_model.startswith("hf.co/"):
            return True
            
        return find_model in self.model_names

if __name__ == '__main__':
    find_model = 'qwen2.5-coder:latest'
    base_url = None
    # base_url = "localhost:11434"
    # base_url = "example.com:11434"

    print(f"find_model: {find_model}")
    print(f"base_url: {base_url}")
    ollama_info = OllamaInfo.obtain_info(base_url=base_url)
    print(f"Error message: {ollama_info.error_message}")
    print(f'Is Ollama running: {ollama_info.is_running}')
    found = ollama_info.is_model_available(find_model)
    print(f'Has model {find_model}: {found}')
