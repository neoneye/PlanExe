def print_gradio_info():
    """What version of Gradio is this. Runs the "gradio environment" command."""
    import subprocess
    print(subprocess.check_output(["gradio", "environment"]).decode())
