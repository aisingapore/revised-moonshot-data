import logging
import os
import time

import tensorflow as tf
from moonshot.src.redteaming.attack.attack_module import AttackModule
from moonshot.src.redteaming.attack.attack_module_arguments import AttackModuleArguments
from moonshot.src.utils.log import configure_logger
from textattack.augmentation import Augmenter
from textattack.constraints.pre_transformation import (
    RepeatModification,
    StopwordModification,
)
from textattack.constraints.semantics.sentence_encoders import UniversalSentenceEncoder
from textattack.transformations import (
    CompositeTransformation,
    WordSwapEmbedding,
    WordSwapHomoglyphSwap,
    WordSwapNeighboringCharacterSwap,
    WordSwapRandomCharacterDeletion,
    WordSwapRandomCharacterInsertion,
)

# Create a logger for this module
logger = configure_logger(__name__)

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
tf.get_logger().setLevel(logging.ERROR)

# Configurble PARAMS - Percentage of words in a prompt that should be changed
DEFAULT_WORD_SWAP_RATIO = 0.2
# Configurble PARAMS - To select top 5 semantic words our of GloVe emedding
DEFAULT_TOP_K = 5
# Configurble PARAMS -Threshold for Universal Sentence Encoder
DEFAULT_THRESHOLD = 0.8
# Configurble PARAMS - Number of prompts to be sent to target
DEFAULT_MAX_ITERATION = 5


class BugGenerator(AttackModule):
    def __init__(self, am_id: str, am_arguments: AttackModuleArguments | None = None):
        # Initialize super class
        super().__init__(am_id, am_arguments)
        self.name = "TextBugger Attack"
        self.description = (
            "This module tests for adversarial textual robustness and implements the perturbations listed in the paper "
            "TEXTBUGGER: Generating Adversarial Text Against Real-world Applications.\nParameters:\n1. "
            "DEFAULT_MAX_ITERATION - Number of prompts that should be sent to the target. This is also the"
            "number of transformations that should be generated. [Default: 5]\n"
            "Note:\nUsage of this attack module requires the internet. Initial downloading of the "
            "GLoVe embedding occurs when the UniversalEncoder is called.\nEmbedding is retrieved from "
            "the following URL: https://textattack.s3.amazonaws.com/word_embeddings/paragramcf"
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
        top_k = configurations.get("top_k", DEFAULT_TOP_K)
        threshold = configurations.get("threshold", DEFAULT_THRESHOLD)

        transformation = CompositeTransformation(
            [
                # (1) Insert: Insert a space into the word.
                # Generally, words are segmented by spaces in English. Therefore,
                # we can deceive classifiers by inserting spaces into words.
                WordSwapRandomCharacterInsertion(
                    random_one=True,
                    letters_to_insert=" ",
                    skip_first_char=True,
                    skip_last_char=True,
                ),
                # (2) Delete: Delete a random character of the word except for the first
                # and the last character.
                WordSwapRandomCharacterDeletion(
                    random_one=True, skip_first_char=True, skip_last_char=True
                ),
                # (3) Swap: Swap random two adjacent letters in the word but do not
                # alter the first or last letter. This is a common occurrence when
                # typing quickly and is easy to implement.
                WordSwapNeighboringCharacterSwap(
                    random_one=True, skip_first_char=True, skip_last_char=True
                ),
                # (4) Substitute-C (Sub-C): Replace characters with visually similar
                # characters (e.g., replacing “o” with “0”, “l” with “1”, “a” with “@”)
                # or adjacent characters in the keyboard (e.g., replacing “m” with “n”).
                WordSwapHomoglyphSwap(),
                # (5) Substitute-W
                # (Sub-W): Replace a word with its topk nearest neighbors in a
                # context-aware word vector space. Specifically, we use the pre-trained
                # GloVe model [30] provided by Stanford for word embedding and set
                # topk = 5 in the experiment.
                WordSwapEmbedding(max_candidates=top_k),
            ]
        )
        constraints = [RepeatModification(), StopwordModification()]
        """
        In our experiment, we first use the Universal Sentence
        Encoder [7], a model trained on a number of natural language
        prediction tasks that require modeling the meaning of word
        sequences, to encode sentences into high dimensional vectors.
        Then, we use the cosine similarity to measure the semantic
        similarity between original texts and adversarial texts.
        ... 'Furthermore, the semantic similarity threshold \\eps is set
        as 0.8 to guarantee a good trade-off between quality and
        strength of the generated adversarial text.'
        """
        constraints.append(UniversalSentenceEncoder(threshold=threshold))
        augmenter = Augmenter(
            transformation=transformation,
            constraints=constraints,
            pct_words_to_swap=word_swap_ratio,
            transformations_per_example=max_iteration,
        )
        logger.debug(f"{'*'*10} [BugGenerator] Augmentation in Progress {'*'*10}")
        start = time.process_time()
        results = augmenter.augment(self.prompt)
        logger.debug(
            f"{'*'*10} [BugGenerator] Time Taken: {time.process_time() - start}s {'*'*10}"
        )
        for i in results:
            logger.debug(f"[BugGenerator] Index {i}")
            result_list.append(await self._send_prompt_to_all_llm([i]))
        for res in result_list:
            for x in res:
                logger.debug(f"[BugGenerator] Prompt: {x.prompt}")
                logger.debug(
                    f"[BugGenerator] Predicted Results: {x.predicted_results}\n"
                )
        return result_list
