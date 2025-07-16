"""
This was generated with Gemini 2.5 Pro.

Strategic Variant Analysis (SVA), explore the solution space.

Step 3: Sample & Prioritize Combinations

- This module takes the "vital few" levers identified in the previous step.
- It calculates all possible permutations of these levers and their options to define the total solution space.
- It then draws a random sample of N (e.g., 20) strategic variants from this space.
- These sampled variants represent distinct, plausible strategic pathways for the project, which can then be evaluated.

PROMPT> python -m planexe.strategic_variant_analysis.lever_scenario_synthesizer_legacy1
"""
import json
import logging
import os
import random
import itertools
from dataclasses import dataclass
from typing import List, Dict, Any

from planexe.strategic_variant_analysis.identify_potential_levers import Lever

logger = logging.getLogger(__name__)

# The number of random samples to draw from the permutation space.
NUM_SAMPLES = 20

@dataclass
class StrategicVariant:
    """Represents one unique combination of lever settings."""
    variant_id: int
    settings: Dict[str, str]  # Maps Lever Name to its selected Option
    description: str

@dataclass
class SampledVariantsResult:
    """Holds the results of the sampling process."""
    vital_levers: List[Lever]
    total_possible_variants: int
    sampled_variants: List[StrategicVariant]
    metadata: Dict[str, Any]

    def to_dict(self) -> dict:
        """Converts the result to a dictionary for serialization."""
        return {
            "metadata": {
                "total_possible_variants": self.total_possible_variants,
                "num_levers": len(self.vital_levers),
                "num_samples_drawn": len(self.sampled_variants),
                **self.metadata
            },
            "sampled_variants": [
                {
                    "variant_id": v.variant_id,
                    "description": v.description,
                    "settings": v.settings
                } for v in self.sampled_variants
            ]
        }
    
    def save(self, file_path: str) -> None:
        """Saves the sampled variants to a JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

class SampleStrategicVariants:

    @staticmethod
    def execute(vital_levers_filepath: str) -> SampledVariantsResult:
        """
        Loads vital levers, generates permutations, and samples them.

        Args:
            vital_levers_filepath: Path to the JSON file containing the vital levers.

        Returns:
            A SampledVariantsResult object.
        """
        if not os.path.exists(vital_levers_filepath):
            raise FileNotFoundError(f"Vital levers file not found at: {vital_levers_filepath}")

        with open(vital_levers_filepath, 'r') as f:
            data = json.load(f)
        
        vital_levers = [Lever(**lever_data) for lever_data in data.get('levers', [])]

        if not vital_levers:
            raise ValueError("No levers found in the provided file.")
        
        logger.info(f"Loaded {len(vital_levers)} vital levers.")

        # Get the options for each lever
        lever_names = [lever.name for lever in vital_levers]
        options_per_lever = [lever.options for lever in vital_levers]

        # Generate all possible combinations using itertools.product
        all_combinations = list(itertools.product(*options_per_lever))
        total_variants = len(all_combinations)
        
        logger.info(f"Total possible strategic variants (solution space size): {total_variants}")

        # Take a random sample
        num_to_sample = min(NUM_SAMPLES, total_variants)
        sampled_combinations = random.sample(all_combinations, num_to_sample)
        
        logger.info(f"Drawing a random sample of {num_to_sample} variants.")

        # Create StrategicVariant objects for each sample
        sampled_variants = []
        for i, combo in enumerate(sampled_combinations):
            settings = dict(zip(lever_names, combo))
            
            # Create a human-readable description
            desc_parts = [f"- **{name}**: '{setting}'" for name, setting in settings.items()]
            description = f"Variant {i+1} is defined by the following strategic choices:\n" + "\n".join(desc_parts)
            
            variant = StrategicVariant(
                variant_id=i + 1,
                settings=settings,
                description=description
            )
            sampled_variants.append(variant)

        metadata = {
            "source_file": vital_levers_filepath
        }

        return SampledVariantsResult(
            vital_levers=vital_levers,
            total_possible_variants=total_variants,
            sampled_variants=sampled_variants,
            metadata=metadata
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # This file was created by the previous script (focus_on_vital_few_levers.py)
    input_file = "vital_levers_from_test_data.json"
    output_file = "sampled_strategic_variants.json"

    try:
        result = SampleStrategicVariants.execute(vital_levers_filepath=input_file)

        print(f"Successfully generated {len(result.sampled_variants)} sampled variants from a total solution space of {result.total_possible_variants}.")
        
        # Print the first 2 samples as an example
        print("\n--- Example Sampled Variants ---")
        for variant in result.sampled_variants[:2]:
            print(f"\n--- Variant ID: {variant.variant_id} ---")
            print(variant.description)
            # print(json.dumps(variant.settings, indent=2))
        
        if len(result.sampled_variants) > 2:
            print(f"\n...and {len(result.sampled_variants) - 2} more.")

        # Save the full results to a file
        result.save(output_file)
        logger.info(f"Full list of {len(result.sampled_variants)} sampled variants saved to '{output_file}'.")

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"An error occurred: {e}")
        logger.error(f"Please ensure '{input_file}' exists and is correctly formatted.")