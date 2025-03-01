"""
Pick a suitable currency for the project plan. If the description already includes the currency, then there is no need for this step.
If the currency is not mentioned, then the expert should suggest suitable locations based on the project requirements.
The project may go across national borders, so picking a currency that is widely accepted is important.

Currency codes
https://en.wikipedia.org/wiki/ISO_4217

PROMPT> python -m src.assume.pick_currency
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class CurrencyItem(BaseModel):
    currency: str = Field(
        description="ISO 4217 alphabetic code."
    )
    consideration: str = Field(
        description="Why use this currency."
    )

class DocumentDetails(BaseModel):
    currency_list: list[CurrencyItem] = Field(
        description="List of currencies that are relevant for this project."
    )
    primary_currency: str = Field(
        description="The main currency for budgeting and reporting (ISO 4217 alphabetic code).",
        default=None
    )
    currency_strategy: str = Field(
        description="A short summary of how to handle currency exchange and risk during the project.",
        default=""
    )

PICK_CURRENCY_SYSTEM_PROMPT = """
You are a world-class planning expert specializing in picking the best-suited currency for large, international projects. Currency decisions significantly impact project costs, reporting, and financial risk.

ere are a few examples of the desired output format:

**Example 1:**
Project: Constructing a solar power plant in Nevada, USA
Currency List:
- USD: For all project-related expenses in the USA.
Primary Currency: USD
Currency Strategy: Use USD for all budgeting and accounting.

**Example 2:**
Project: Building a wind farm in the North Sea (offshore UK and Netherlands)
Currency List:
- EUR: For equipment and services sourced from the Eurozone.
- GBP: For UK-based operations and services.
- DKK: For Danish-based operations and services.
Primary Currency: EUR
Currency Strategy: EUR will be the primary currency.  Maintain accounts in GBP and DKK for local expenses.  Hedge against significant currency fluctuations.

Consider the following factors when selecting currencies:

*   Stability: Choose currencies that are relatively stable to minimize the impact of exchange rate fluctuations on the project budget.
*   Transaction Costs: Minimize the number of currency conversions to reduce transaction fees.
*   Economic Influence: Consider the economic influence of the countries involved and the currencies used by major suppliers and contractors.
*   Reporting Requirements: Think about the reporting needs of stakeholders and investors.
*   Project Duration: Longer projects are more susceptible to currency risk.
*   Accounting and Tax Implications: Be aware of the accounting and tax rules regarding currency conversions.
*   Important Currency Facts: England uses the British Pound (GBP). Denmark uses the Danish Krone (DKK), NOT the Euro.

Given the project description and location information, identify the following:

1.  Primary Currency: Select a single, primary currency for project budgeting, accounting, and overall financial management (ISO 4217 alphabetic code). Explain your reasoning.  Justify why this is the best choice, considering stability, transaction costs, and overall convenience.
2.  Additional Currencies: List ALL other currencies that will likely be needed for local expenses, procurement, or regulatory compliance (ISO 4217 alphabetic code).  Explain *specifically* why each currency is necessary (e.g., "DKK for local expenses in Denmark, such as permits and local labor."). Include DKK and GBP if the project involves Denmark and England respectively, even if you recommend a different primary currency.
3.  Currency Strategy: Provide a detailed summary of a recommended currency management strategy for the project. This should include advice on hedging currency risk (e.g., using forward contracts for large, predictable expenses), managing exchange rates, and handling local currency transactions.

If the currency is not explicitly mentioned in the project description, suggest suitable currencies based on the project's requirements, locations, and the factors listed above.

Be precise with your reasoning, and avoid making inaccurate statements about which countries use which currencies.
"""

@dataclass
class PickCurrency:
    """
    Take a look at the vague plan description and suggest a currency.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'PickCurrency':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = PICK_CURRENCY_SYSTEM_PROMPT.strip()

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = PickCurrency(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.utils.concat_files_into_string import concat_files_into_string

    base_path = os.path.join(os.path.dirname(__file__), 'test_data', 'pick_currency1')

    all_documents_string = concat_files_into_string(base_path)
    print(all_documents_string)

    llm = get_llm("ollama-llama3.1")

    pick_currency = PickCurrency.execute(llm, all_documents_string)
    json_response = pick_currency.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))
