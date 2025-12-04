"""
PROMPT> python -m planexe.llm_util.ollama_info
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class OllamaInfo:
    """
    Details about the Ollama service, including a list of available model names,
    a flag indicating whether the service is running, and an optional error message.
    """
    model_names: list[str]
    is_running: bool
    error_message: Optional[str] = None

    @classmethod
    def obtain_info(cls, base_url: Optional[str] = None) -> 'OllamaInfo':
        """Retrieves information about the Ollama service."""
        try:
            # Only import ollama if it's available
            from ollama import ListResponse, Client
            client = Client(host=base_url, timeout=5)
            list_response: ListResponse = client.list()
        except ImportError as e:
            error_message = f"OllamaInfo base_url={base_url}. The 'ollama' library was not found: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)
        except ConnectionError as e:
            error_message = f"OllamaInfo base_url={base_url}. Error connecting to Ollama: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)
        except Exception as e:
            error_message = f"OllamaInfo base_url={base_url}. An unexpected error occurred: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)

        model_names = [model.model for model in list_response.models]
        return OllamaInfo(model_names=model_names, is_running=True, error_message=None)
    
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
