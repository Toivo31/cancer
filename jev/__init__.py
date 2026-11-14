"""JEV: the decision-model interface of the pathway platform (docs/platform/specs/02-jev-interface.md).

Contract types and JSON encoding (:mod:`jev.contract`), the engine adapter
(:class:`jev.BackendPolicy`), and the backends.
"""

from .adapter import MODES, BackendPolicy, OptionCatalogue, build_context
from .contract import (CONTRACT_VERSION, TOLERANCE, BackendError, BackendInfo, ContractError, DecisionBackend,
                       DecisionRequest, DecisionResponse, check_probs, check_responses, decode_request,
                       decode_response, encode_request, encode_response, uniform_probs)

__all__ = [
    "BackendError", "BackendInfo", "BackendPolicy", "CONTRACT_VERSION", "ContractError", "DecisionBackend",
    "DecisionRequest", "DecisionResponse", "MODES", "OptionCatalogue", "TOLERANCE", "build_context",
    "check_probs", "check_responses", "decode_request", "decode_response", "encode_request",
    "encode_response", "uniform_probs",
]
