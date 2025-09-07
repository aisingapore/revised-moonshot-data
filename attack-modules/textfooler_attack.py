import logging
import os
import time

import tensorflow as tf
from moonshot.src.redteaming.attack.attack_module import AttackModule
from moonshot.src.redteaming.attack.attack_module_arguments import AttackModuleArguments
from moonshot.src.utils.log import configure_logger
from textattack.augmentation import Augmenter
from textattack.constraints.grammaticality import PartOfSpeech
from textattack.constraints.pre_transformation import (
    InputColumnModification,
    RepeatModification,
    StopwordModification,
)
from textattack.constraints.semantics import WordEmbeddingDistance
from textattack.constraints.semantics.sentence_encoders import UniversalSentenceEncoder
from textattack.transformations import WordSwapEmbedding

# Create a logger for this module
logger = configure_logger(__name__)

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
tf.get_logger().setLevel(logging.ERROR)

# Configurble PARAMS - Percentage of words in a prompt that should be changed
DEFAULT_WORD_SWAP_RATIO = 0.2
# Configurble PARAMS - Minimum word embedding cosine similarity of 0.5.
DEFAULT_COSINE_SIM = 0.5
# Configurble PARAMS - window size for USE
DEFAULT_WINDOW_SIZE = 15
# Configurble PARAMS - threshold for USE
DEFAULT_THRESHOLD = 0.840845057
# Configurble PARAMS - Number of prompts to be sent to target
DEFAULT_MAX_ITERATION = 5
# Configurble PARAMS - Swap words with their 50 closest embedding nearest-neighbors.
DEFAULT_MAX_CANDIDATES = 50


class FoolerGenerator(AttackModule):
    def __init__(self, am_id: str, am_arguments: AttackModuleArguments | None = None):
        # Initialize super class
        super().__init__(am_id, am_arguments)
        self.name = "TextFooler Attack"
        self.description = (
            "This module tests for adversarial textual robustness and implements the perturbations "
            "listed in the paper 'Is BERT Really Robust? A Strong Baseline for Natural Language Attack "
            "on Text Classification and Entailment.'\nParameters:\n1. DEFAULT_MAX_ITERATION - Number of prompts "
            "that should be sent to the target. This is also the number of transformations that should be "
            "generated. [Default: 5]\nNote:\nUsage of this attack module requires the internet. Initial "
            "downloading of the GLoVe embedding occurs when the UniversalEncoder is called.\nEmbedding is "
            "retrieved from the following URL: https://textattack.s3.amazonaws.com/word_embeddings/paragramcf"
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

        # get the configurable params from the config JSON file. if they're not specified, use the default values
        configurations = self.req_and_config.get("configurations", {})

        max_iteration = configurations.get("max_iteration", DEFAULT_MAX_ITERATION)
        word_swap_ratio = configurations.get("word_swap_ratio", DEFAULT_WORD_SWAP_RATIO)
        cosine_sim = configurations.get("word_swap_ratio", DEFAULT_COSINE_SIM)
        threshold = configurations.get("threshold", DEFAULT_THRESHOLD)
        window_size = configurations.get("window_size", DEFAULT_WINDOW_SIZE)
        max_candidates = configurations.get("max_candidates", DEFAULT_MAX_CANDIDATES)

        """
        Swap words with their 50 closest embedding nearest-neighbors.
        Embedding: Counter-fitted PARAGRAM-SL999 vectors.
        """
        transformation = WordSwapEmbedding(max_candidates=max_candidates)
        """
        Don't modify the same word twice or the stopwords defined
        in the TextFooler public implementation.
        fmt: off
        """
        stopwords = set(
            [
                "a",
                "about",
                "above",
                "across",
                "after",
                "afterwards",
                "again",
                "against",
                "ain",
                "all",
                "almost",
                "alone",
                "along",
                "already",
                "also",
                "although",
                "am",
                "among",
                "amongst",
                "an",
                "and",
                "another",
                "any",
                "anyhow",
                "anyone",
                "anything",
                "anyway",
                "anywhere",
                "are",
                "aren",
                "aren't",
                "around",
                "as",
                "at",
                "back",
                "been",
                "before",
                "beforehand",
                "behind",
                "being",
                "below",
                "beside",
                "besides",
                "between",
                "beyond",
                "both",
                "but",
                "by",
                "can",
                "cannot",
                "could",
                "couldn",
                "couldn't",
                "d",
                "didn",
                "didn't",
                "doesn",
                "doesn't",
                "don",
                "don't",
                "down",
                "due",
                "during",
                "either",
                "else",
                "elsewhere",
                "empty",
                "enough",
                "even",
                "ever",
                "everyone",
                "everything",
                "everywhere",
                "except",
                "first",
                "for",
                "former",
                "formerly",
                "from",
                "hadn",
                "hadn't",
                "hasn",
                "hasn't",
                "haven",
                "haven't",
                "he",
                "hence",
                "her",
                "here",
                "hereafter",
                "hereby",
                "herein",
                "hereupon",
                "hers",
                "herself",
                "him",
                "himself",
                "his",
                "how",
                "however",
                "hundred",
                "i",
                "if",
                "in",
                "indeed",
                "into",
                "is",
                "isn",
                "isn't",
                "it",
                "it's",
                "its",
                "itself",
                "just",
                "latter",
                "latterly",
                "least",
                "ll",
                "may",
                "me",
                "meanwhile",
                "mightn",
                "mightn't",
                "mine",
                "more",
                "moreover",
                "most",
                "mostly",
                "must",
                "mustn",
                "mustn't",
                "my",
                "myself",
                "namely",
                "needn",
                "needn't",
                "neither",
                "never",
                "nevertheless",
                "next",
                "no",
                "nobody",
                "none",
                "noone",
                "nor",
                "not",
                "nothing",
                "now",
                "nowhere",
                "o",
                "of",
                "off",
                "on",
                "once",
                "one",
                "only",
                "onto",
                "or",
                "other",
                "others",
                "otherwise",
                "our",
                "ours",
                "ourselves",
                "out",
                "over",
                "per",
                "please",
                "s",
                "same",
                "shan",
                "shan't",
                "she",
                "she's",
                "should've",
                "shouldn",
                "shouldn't",
                "somehow",
                "something",
                "sometime",
                "somewhere",
                "such",
                "t",
                "than",
                "that",
                "that'll",
                "the",
                "their",
                "theirs",
                "them",
                "themselves",
                "then",
                "thence",
                "there",
                "thereafter",
                "thereby",
                "therefore",
                "therein",
                "thereupon",
                "these",
                "they",
                "this",
                "those",
                "through",
                "throughout",
                "thru",
                "thus",
                "to",
                "too",
                "toward",
                "towards",
                "under",
                "unless",
                "until",
                "up",
                "upon",
                "used",
                "ve",
                "was",
                "wasn",
                "wasn't",
                "we",
                "were",
                "weren",
                "weren't",
                "what",
                "whatever",
                "when",
                "whence",
                "whenever",
                "where",
                "whereafter",
                "whereas",
                "whereby",
                "wherein",
                "whereupon",
                "wherever",
                "whether",
                "which",
                "while",
                "whither",
                "who",
                "whoever",
                "whole",
                "whom",
                "whose",
                "why",
                "with",
                "within",
                "without",
                "won",
                "won't",
                "would",
                "wouldn",
                "wouldn't",
                "y",
                "yet",
                "you",
                "you'd",
                "you'll",
                "you're",
                "you've",
                "your",
                "yours",
                "yourself",
                "yourselves",
            ]
        )
        # fmt: on
        constraints = [RepeatModification(), StopwordModification(stopwords=stopwords)]
        """
        During entailment, we should only edit the hypothesis - keep the premise
        the same.
        """
        input_column_modification = InputColumnModification(
            ["premise", "hypothesis"], {"premise"}
        )
        constraints.append(input_column_modification)
        """
        Minimum word embedding cosine similarity of 0.5.
            # (The paper claims 0.7, but analysis of the released code and some empirical
            # results show that it's 0.5.)
        """
        constraints.append(WordEmbeddingDistance(min_cos_sim=cosine_sim))
        """Only replace words with the same part of speech (or nouns with verbs)"""
        constraints.append(PartOfSpeech(allow_verb_noun_swap=True))
        """
            Universal Sentence Encoder with a minimum angular similarity of ε = 0.5.
            In the TextFooler code, they forget to divide the angle between the two
            embeddings by pi. So if the original threshold was that 1 - sim >= 0.5, the
            new threshold is 1 - (0.5) / pi = 0.840845057
        """
        use_constraint = UniversalSentenceEncoder(
            threshold=threshold,
            metric="angular",
            compare_against_original=False,
            window_size=window_size,
            skip_text_shorter_than_window=True,
        )
        constraints.append(use_constraint)

        augmenter = Augmenter(
            transformation=transformation,
            constraints=constraints,
            pct_words_to_swap=word_swap_ratio,
            transformations_per_example=max_iteration,
        )
        result_list = []
        logger.debug(f"{'*'*10} [FoolerGenerator] Augmentation in Progress {'*'*10}")
        start = time.process_time()
        results = augmenter.augment(self.prompt)
        logger.debug(
            f"{'*'*10} [FoolerGenerator] Time Taken: {time.process_time() - start}s {'*'*10}"
        )
        for i in results:
            logger.debug(f"[FoolerGenerator] Index {i}")
            result_list.append(await self._send_prompt_to_all_llm([i]))
        for res in result_list:
            for x in res:
                logger.debug(f"[FoolerGenerator] Prompt: {x.prompt}")
                logger.debug(
                    f"[FoolerGenerator] Predicted Results: {x.predicted_results}\n"
                )

        return result_list
