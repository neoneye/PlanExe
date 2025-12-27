"""
Mach-AI API client.

PROMPT> python -m machai
"""
import logging
from pathlib import Path
import requests
import traceback
from enum import Enum

logger = logging.getLogger(__name__)

# IDEA: move secrets to env vars.
URL_PLANEXE_IFRAME_GENERATOR_CONFIRMATION_PRODUCTION = 'https://example.com/iframe_generator_confirmation'
URL_PLANEXE_IFRAME_GENERATOR_CONFIRMATION_DEVELOPMENT = 'https://example.com/iframe_generator_confirmation'

class ConfirmationStatus(str, Enum):
    # The report has been generated successfully.
    ok = 'ok'
    # Something went wrong while generating the report.
    error = 'error'

class MachAI:
    def __init__(self, url: str, url_mode: str):
        self.url = url
        self.url_mode = url_mode

    @classmethod
    def create(cls, use_machai_developer_endpoint: bool) -> 'MachAI':
        if use_machai_developer_endpoint:
            return cls(url=URL_PLANEXE_IFRAME_GENERATOR_CONFIRMATION_DEVELOPMENT, url_mode='developer')
        else:
            return cls(url=URL_PLANEXE_IFRAME_GENERATOR_CONFIRMATION_PRODUCTION, url_mode='production')

    def inner_post_confirmation(self, session_id: str, status: ConfirmationStatus, message: str, plan_name: str, output: str) -> bool:
        """Make a POST request to confirm that the report has been generated or failed."""
        logger.debug(f"MachAI.post_confirmation. session_id {session_id!r}. status {status.value!r}. message {message!r}. plan_name {plan_name!r}. url_mode {self.url_mode!r}.")
        
        # Prepare the data to send
        data = {
            'session_id': session_id,
            'status': status.value,
            'message': message,
            'plan_name': plan_name,
            'output': output
        }
        
        try:
            # Make the POST request
            response = requests.post(self.url, json=data, timeout=30)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            logger.debug(f"MachAI.post_confirmation, success. Response status: {response.status_code}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"MachAI.post_confirmation, failed. {session_id!r}: {e}")
            logger.error(f"Backtrace:\n{traceback.format_exc()}")
            return False

    def post_confirmation_ok_with_file(self, session_id: str, path: Path, plan_name: str) -> bool:
        """Read the file and make a POST request to confirm that the report has been generated."""
        
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        file_size_in_bytes = path.stat().st_size
        message = f'Report size is {file_size_in_bytes} bytes.'

        return self.inner_post_confirmation(
            session_id=session_id, 
            status=ConfirmationStatus.ok, 
            message=message, 
            plan_name=plan_name,
            output=content
        )

    def post_confirmation_error(self, session_id: str, message: str) -> bool:
        """Make a POST request to confirm that the report has failed to be generated."""
        return self.inner_post_confirmation(
            session_id=session_id, 
            status=ConfirmationStatus.error, 
            message=message, 
            plan_name='',
            output=''
        )
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    session_ids = [
        '95a9ab35-e302-42a7-a5d9-78c573146796',
        '672d5db5-50dd-44cc-992e-125411f3d300',
        'ca8b7d27-4989-4c69-b903-2ebe05ecec37',
        '9075bd24-a435-400a-aa85-6ffb3a33ff41',
    ]
    modes = [False, True]
    for mode in modes:
        machai = MachAI.create(use_machai_developer_endpoint=mode)
        machai.inner_post_confirmation(session_id=session_ids[0], status=ConfirmationStatus.ok, message='The report has been generated successfully.', plan_name='Demo Plan 1', output='This is a long report.')
        machai.inner_post_confirmation(session_id=session_ids[1], status=ConfirmationStatus.error, message='User navigated away from the page.', plan_name='Demo Plan 2', output='')
    
        # read file from path
        if False:
            path = Path('/absolute/path/to/an/example/plan/20250524_universal_manufacturing/028-report.html')
            machai.post_confirmation_ok_with_file(session_id=session_ids[2], path=path, plan_name='Demo Universal Manufacturing')
