import math
import random
import string

from moonshot.src.redteaming.attack.attack_module import AttackModule
from moonshot.src.redteaming.attack.attack_module_arguments import AttackModuleArguments
from moonshot.src.utils.log import configure_logger
from nltk import word_tokenize
from nltk.tokenize.treebank import TreebankWordDetokenizer

# Create a logger for this module
logger = configure_logger(__name__)

# Configurble PARAMS - Number of prompts to be sent to target
DEFAULT_MAX_ITERATION = 10
# Configurble PARAMS - Percentage of words in a prompt that should be changed
DEFAULT_WORD_SWAP_RATIO = 0.2


class InsertPunctGenerator(AttackModule):
    def __init__(self, am_id: str, am_arguments: AttackModuleArguments | None = None):
        # Initialize super class
        super().__init__(am_id, am_arguments)
        self.name = "Insert Punctuation Attack"
        self.description = (
            "This module tests for adversarial textual robustness and creates perturbations through adding punctuation "
            "to the start of words in a prompt.\nParameters:\n1. DEFAULT_MAX_ITERATION - Number of prompts that "
            "should be sent to the target. [Default: 10]"
        )

    def get_metadata(self) -> dict:
        """
        Get metadata for the attack module.

        Returns:
            dict | None: A dictionary containing the 'id', 'name', 'description', 'endpoints' and 'configurations'
            or None if the metadata is not available.
        """
        endpoints = self.req_and_config.get("endpoints", [])
        configurations = self.req_and_config.get("configurations", {})

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description if hasattr(self, "description") else "",
            "endpoints": endpoints,
            "configurations": configurations,
        }

    def get_n_random(self, low: int, high: int, n: int) -> list:
        """
        Util function to generate random indices.
        Words of these indices after word tokenization will be subjected to perturbation.
        """
        result = []
        try:
            result = random.sample(range(low, high), n)
        except ValueError:
            logger.debug(
                f"[InsertPunctGenerator] Sample size of {n} exceeds population size of {high - low}"
            )
        return result

    async def execute(self):
        """
        Asynchronously executes the attack module.

        This method loads the dataset contents using the `load_dataset_contents` method,
        processes the dataset through a prompt template, retrieves the connector to the first
        Language Learning Model (LLM) and sends the processed dataset as a prompt to the LLM.
        """
        self.load_modules()
        return await self.perform_attack_manually()

    async def perform_attack_manually(self) -> list:
        """
        Asynchronously performs the attack manually. The user will need to pass in a list of prompts and
        the LLM connector endpoint to send the prompts to. In this example, there is a for loop to send the
        list of prepared prompts to all the LLM connectors defined.

        This method prepares prompts for each target Language Learning Model (LLM) using the provided prompt
        and sends them to the respective LLMs.
        """
        result_list = []

        # get the configurable params from the config JSON file. if they're not specified, use the default values
        configurations = self.req_and_config.get("configurations", {})
        max_iteration = configurations.get("max_iteration", DEFAULT_MAX_ITERATION)
        word_swap_ratio = configurations.get("word_swap_ratio", DEFAULT_WORD_SWAP_RATIO)

        # space of characters that we wish to insert for perturbation
        dec_space = string.punctuation + " "
        word_list = word_tokenize(self.prompt)
        word_list_len = len(word_list)
        num_perturb_words = math.ceil(word_list_len * word_swap_ratio)
        for _ in range(max_iteration):
            chosen_dec = dec_space[random.randint(0, len(string.punctuation))]
            # get random indices of words to undergo swapping algo
            random_words_idx = self.get_n_random(0, word_list_len, num_perturb_words)
            for idx in random_words_idx:
                if word_list[idx] not in dec_space:
                    word_list[idx] = chosen_dec + word_list[idx]
            new_prompt = TreebankWordDetokenizer().detokenize(word_list)
            result_list.append(await self._send_prompt_to_all_llm([new_prompt]))
            word_list = word_tokenize(self.prompt)
        for res in result_list:
            for x in res:
                logger.debug(f"[InsertPunctGenerator] Prompt: {x.prompt}")
                logger.debug(
                    f"[InsertPunctGenerator] Predicted Results: {x.predicted_results}\n"
                )
        return result_list
