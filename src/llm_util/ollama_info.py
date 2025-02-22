"""
PROMPT> python -m src.llm_util.ollama_info
"""
from dataclasses import dataclass

@dataclass
class OllamaInfo:
    """
    Details about the Ollama service, including a list of available model names,
    a flag indicating whether the service is running, and an optional error message.
    """
    model_names: list[str]
    is_running: bool
    error_message: str = None

    @classmethod
    def obtain_info(cls) -> 'OllamaInfo':
        """Retrieves information about the Ollama service."""
        try:
            # Only import ollama if it's available
            from ollama import ListResponse, list
            list_response: ListResponse = list()
        except ImportError as e:
            error_message = f"OllamaInfo. The 'ollama' library was not found: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)
        except ConnectionError as e:
            error_message = f"OllamaInfo. Error connecting to Ollama: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)
        except Exception as e:
            error_message = f"OllamaInfo. An unexpected error occurred: {e}"
            return OllamaInfo(model_names=[], is_running=False, error_message=error_message)

        model_names = [model.model for model in list_response.models]
        return OllamaInfo(model_names=model_names, is_running=True, error_message=None)
    
    def is_model_available(self, find_model: str) -> bool:
        """Checks if a specific model is available in the list of model names."""
        return find_model in self.model_names

if __name__ == '__main__':
    find_model = 'qwen2.5-coder:latest'
    ollama_info = OllamaInfo.obtain_info()
    print(f"Error message: {ollama_info.error_message}")
    print(f'Is Ollama running: {ollama_info.is_running}')
    found = ollama_info.is_model_available(find_model)
    print(f'Has model {find_model}: {found}')
