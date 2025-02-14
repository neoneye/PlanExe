"""
Multi-user experiment. User data is isolated from other users.
Store one parameter in State.
When the page is open in multiple tabs, then each tab is isolated from the other tabs.
However when the user reloads the page, the API key is lost.
"""
import gradio as gr

def store_api_key(api_key, state):
    # Save the API key in session-specific state.
    state = api_key
    return state, f"API key stored for this session: {api_key}"

def perform_action(state):
    # Use the stored API key for some action.
    if state:
        # For demonstration, we simply return a message using the API key.
        return f"Action performed using API key: {state}"
    else:
        return "No API key provided. Please store your API key first."

with gr.Blocks() as demo:
    gr.Markdown("# Per-Session API Key Demo")
    
    # Create a session state to store the API key.
    state = gr.State(None)
    
    with gr.Row():
        api_key_input = gr.Textbox(label="Enter your API Key", placeholder="your-api-key")
        store_button = gr.Button("Store API Key")
    
    action_button = gr.Button("Perform Action")
    output_text = gr.Textbox(label="Output")
    
    # When the store button is clicked, update the session state.
    store_button.click(store_api_key, inputs=[api_key_input, state], outputs=[state, output_text])
    
    # When the action button is clicked, use the session state (API key) to perform an action.
    action_button.click(perform_action, inputs=state, outputs=output_text)

if __name__ == "__main__":
    demo.launch()
