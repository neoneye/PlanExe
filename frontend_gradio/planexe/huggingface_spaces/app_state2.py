"""
Multi-user experiment. User data is isolated from other users.
Store one parameter in BrowserState.
When the page is open in multiple tabs, the API key is shared across all tabs.
When the user reloads the page, the API key is remembered.
When the server is restarted, the API key is remembered.
"""
import gradio as gr

def store_api_key(api_key, browser_state):
    # Update browser state with the new API key.
    browser_state = api_key
    return browser_state, f"API key stored: {api_key}"

def perform_action(browser_state):
    if browser_state:
        return f"Action performed using API key: {browser_state}"
    else:
        return "No API key stored. Please enter and store one first."

with gr.Blocks() as demo:
    gr.Markdown("## API Key Persistence using BrowserState")
    
    # Create a BrowserState component.
    # The initial value is an empty string, and the key "api_key" is used to store/retrieve the value.
    browser_state = gr.BrowserState("", storage_key="Test", secret="Test")
    
    with gr.Row():
        api_key_input = gr.Textbox(label="Enter your API Key", elem_id="api_key_input")
        store_button = gr.Button("Store API Key")
    
    action_button = gr.Button("Perform Action")
    output_text = gr.Textbox(label="Output")
    
    # Clicking "Store API Key" saves the key to BrowserState.
    store_button.click(store_api_key, inputs=[api_key_input, browser_state], outputs=[browser_state, output_text])
    # "Perform Action" uses the stored API key.
    action_button.click(perform_action, inputs=browser_state, outputs=output_text)

if __name__ == "__main__":
    demo.launch()
