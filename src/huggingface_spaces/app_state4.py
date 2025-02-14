"""
Multi-user experiment. User data is isolated from other users.
Store multiple parameters in BrowserState.
When the page is open in multiple tabs, the API key is shared across all tabs.
When the user reloads the page, the API key is remembered.
When the server is restarted, the API key is remembered.
"""
import gradio as gr
import json

def store_settings(api_key, setting1, setting2, browser_state):
    # Load existing settings if any
    try:
        settings = json.loads(browser_state) if browser_state else {}
    except json.JSONDecodeError:
        settings = {}
    
    # Update settings with new values
    settings.update({
        "api_key": api_key,
        "setting1": setting1,
        "setting2": setting2
    })
    
    # Convert back to JSON string to store
    stored_value = json.dumps(settings)
    return stored_value, f"Settings stored: {settings}"

def perform_action(browser_state):
    if browser_state:
        try:
            settings = json.loads(browser_state)
            return f"Action performed using settings: {settings}"
        except json.JSONDecodeError:
            return "Stored settings are corrupted."
    else:
        return "No settings stored. Please enter and store them first."

with gr.Blocks() as demo:
    gr.Markdown("## Settings Persistence using BrowserState")
    
    # Create a BrowserState component.
    # The initial value is an empty string, and the key "Test" is used to store/retrieve the value.
    browser_state = gr.BrowserState("", storage_key="Test", secret="Test")
    
    with gr.Row():
        api_key_input = gr.Textbox(label="Enter your API Key", elem_id="api_key_input")
        setting1_input = gr.Textbox(label="Setting 1", elem_id="setting1_input")
        setting2_input = gr.Textbox(label="Setting 2", elem_id="setting2_input")
        store_button = gr.Button("Store Settings")
    
    action_button = gr.Button("Perform Action")
    output_text = gr.Textbox(label="Output")
    
    # Save settings on button click.
    store_button.click(
        store_settings, 
        inputs=[api_key_input, setting1_input, setting2_input, browser_state], 
        outputs=[browser_state, output_text]
    )
    
    # Use the stored settings on action button click.
    action_button.click(
        perform_action, 
        inputs=browser_state, 
        outputs=output_text
    )

if __name__ == "__main__":
    demo.launch()
