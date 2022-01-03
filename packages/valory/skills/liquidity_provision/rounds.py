# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This module contains the data classes for the liquidity provision ABCI application."""
import json
from abc import ABC
from enum import Enum
from types import MappingProxyType
from typing import Dict, Mapping, Optional, Tuple, Type, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    BasePeriodState,
    CollectDifferentUntilThresholdRound,
    CollectSameUntilThresholdRound,
    OnlyKeeperSendsRound,
    VotingRound,
)
from packages.valory.skills.liquidity_provision.payloads import (
    StrategyEvaluationPayload,
    StrategyType,
)
from packages.valory.skills.oracle_deployment_abci.rounds import (
    RandomnessOracleRound as RandomnessRound,
)
from packages.valory.skills.price_estimation_abci.payloads import TransactionHashPayload
from packages.valory.skills.transaction_settlement_abci.payloads import (
    FinalizationTxPayload,
    SignaturePayload,
    TransactionType,
    ValidatePayload,
)
from packages.valory.skills.transaction_settlement_abci.rounds import (
    ResetAndPauseRound,
    ResetRound,
)


class Event(Enum):
    """Event enumeration for the liquidity provision demo."""

    DONE = "done"
    EXIT = "exit"
    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    RESET_TIMEOUT = "reset_timeout"
    WAIT = "wait"


class PeriodState(
    BasePeriodState
):  # pylint: disable=too-many-instance-attributes,too-many-statements,too-many-public-methods
    """
    Class to represent a period state.

    This state is replicated by the tendermint application.
    """

    @property
    def most_voted_strategy(self) -> dict:
        """Get the most_voted_strategy."""
        return cast(dict, self.db.get_strict("most_voted_strategy"))

    @property
    def participant_to_votes(self) -> Mapping[str, ValidatePayload]:
        """Get the participant_to_votes."""
        return cast(
            Mapping[str, ValidatePayload], self.db.get_strict("participant_to_votes")
        )

    @property
    def participant_to_strategy(self) -> Mapping[str, StrategyEvaluationPayload]:
        """Get the participant_to_votes."""
        return cast(
            Mapping[str, StrategyEvaluationPayload],
            self.db.get_strict("participant_to_strategy"),
        )

    @property
    def participant_to_tx_hash(self) -> Mapping[str, TransactionHashPayload]:
        """Get the participant_to_tx_hash."""
        return cast(
            Mapping[str, TransactionHashPayload],
            self.db.get_strict("participant_to_tx_hash"),
        )

    @property
    def most_voted_keeper_address(self) -> str:
        """Get the most_voted_keeper_address."""
        return cast(str, self.db.get_strict("most_voted_keeper_address"))

    @property
    def safe_contract_address(self) -> str:
        """Get the safe contract address."""
        return cast(str, self.db.get_strict("safe_contract_address"))

    @property
    def multisend_contract_address(self) -> str:
        """Get the multisend contract address."""
        return cast(str, self.db.get_strict("multisend_contract_address"))

    @property
    def router_contract_address(self) -> str:
        """Get the router02 contract address."""
        return cast(str, self.db.get_strict("router_contract_address"))

    @property
    def participant_to_signature(self) -> Mapping[str, SignaturePayload]:
        """Get the participant_to_signature."""
        return cast(
            Mapping[str, SignaturePayload],
            self.db.get_strict("participant_to_signature"),
        )

    @property
    def most_voted_tx_hash(self) -> str:
        """Get the most_voted_enter_pool_tx_hash."""
        return cast(str, self.db.get_strict("most_voted_tx_hash"))

    @property
    def most_voted_tx_data(self) -> str:
        """Get the most_voted_enter_pool_tx_data."""
        return cast(str, self.db.get_strict("most_voted_tx_data"))

    @property
    def final_tx_hash(self) -> str:
        """Get the final_enter_pool_tx_hash."""
        return cast(str, self.db.get_strict("final_tx_hash"))


class LiquidityProvisionAbstractRound(AbstractRound[Event, TransactionType], ABC):
    """Abstract round for the liquidity provision skill."""

    @property
    def period_state(self) -> PeriodState:
        """Return the period state."""
        return cast(PeriodState, self._state)

    def _return_no_majority_event(self) -> Tuple[PeriodState, Event]:
        """
        Trigger the NO_MAJORITY event.

        :return: a new period state and a NO_MAJORITY event
        """
        return self.period_state, Event.NO_MAJORITY


class TransactionHashBaseRound(
    CollectSameUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """
    This class represents the 'tx-hash' round.

    Input: a period state with the prior round data
    Ouptut: a new period state with the prior round data and the votes for each tx hash

    It schedules the CollectSignatureRound.
    """

    round_id = "tx_hash"
    allowed_tx_type = TransactionHashPayload.transaction_type
    payload_attribute = "tx_hash"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            dict_ = json.loads(self.most_voted_payload)
            state = self.period_state.update(
                participant_to_tx_hash=MappingProxyType(self.collection),
                most_voted_tx_hash=dict_["tx_hash"],
                most_voted_tx_data=dict_["tx_data"],
            )
            return state, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.period_state.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class TransactionSignatureBaseRound(
    CollectDifferentUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """This class represents the 'abstract_signature' round."""

    round_id = "abstract_signature"
    allowed_tx_type = SignaturePayload.transaction_type
    payload_attribute = "signature"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        if self.collection_threshold_reached:
            state = self.period_state.update(
                participant_to_signature=MappingProxyType(self.collection),
            )
            return state, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.period_state.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class TransactionSendBaseRound(OnlyKeeperSendsRound, LiquidityProvisionAbstractRound):
    """
    This class represents the finalization Safe round.

    Input: a period state with the prior round data
    Output: a new period state with the prior round data and the hash of the Safe transaction

    It schedules the ValidateTransactionRound.
    """

    round_id = "finalization"
    allowed_tx_type = FinalizationTxPayload.transaction_type
    payload_attribute = "tx_hash"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        # if reached participant threshold, set the result
        if self.has_keeper_sent_payload:
            state = self.period_state.update(final_tx_hash=self.keeper_payload)
            return state, Event.DONE
        return None


class TransactionValidationBaseRound(VotingRound, LiquidityProvisionAbstractRound):
    """
    This class represents the validate round.

    Input: a period state with the set of participants, the keeper and the Safe contract address.
    Output: a period state with the set of participants, the keeper, the Safe contract address and a validation of the Safe contract address.
    """

    round_id = "transaction_valid_round"
    allowed_tx_type = ValidatePayload.transaction_type
    exit_event: Event = Event.EXIT
    payload_attribute = "vote"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        # if reached participant threshold, set the result
        if self.positive_vote_threshold_reached:
            state = self.period_state.update(
                participant_to_votes=MappingProxyType(self.collection)
            )
            return state, Event.DONE
        if self.negative_vote_threshold_reached:
            state = self.period_state.update()
            return state, self.exit_event
        if not self.is_majority_possible(
            self.collection, self.period_state.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class StrategyEvaluationRound(
    CollectSameUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """This class represents the strategy evaluation round.

    Input: a set of participants (addresses)
    Output: a set of participants (addresses) and the strategy

    It schedules the WaitRound or the SwapRound.
    """

    round_id = "strategy_evaluation"
    allowed_tx_type = StrategyEvaluationPayload.transaction_type
    payload_attribute = "strategy"

    def end_block(self) -> Optional[Tuple[BasePeriodState, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            state = self.period_state.update(
                participant_to_strategy=MappingProxyType(self.collection),
                most_voted_strategy=self.most_voted_payload,
            )
            event = (
                Event.DONE
                if state.most_voted_strategy["action"] == StrategyType.GO  # type: ignore
                else Event.RESET_TIMEOUT
            )
            return state, event
        if not self.is_majority_possible(
            self.collection, self.period_state.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class EnterPoolTransactionHashRound(TransactionHashBaseRound):
    """This class represents the SwapBack transaction hash round."""

    round_id = "enter_pool_tx_hash"


class EnterPoolTransactionSignatureRound(TransactionSignatureBaseRound):
    """This class represents the SwapBack signature round."""

    round_id = "enter_pool_tx_signature"


class EnterPoolTransactionSendRound(TransactionSendBaseRound):
    """This class represents the SwapBack send round."""

    round_id = "enter_pool_tx_send"


class EnterPoolTransactionValidationRound(TransactionValidationBaseRound):
    """This class represents the SwapBack validation round."""

    round_id = "enter_pool_tx_validation"


class EnterPoolRandomnessRound(RandomnessRound):
    """Enter pool randomness round."""

    round_id = "enter_pool_randomness"


class EnterPoolSelectKeeperRound(
    CollectSameUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """This class represents the SwapBack select keeper round."""

    round_id = "enter_pool_select_keeper"


class ExitPoolTransactionHashRound(TransactionHashBaseRound):
    """This class represents the SwapBack transaction hash round."""

    round_id = "exit_pool_tx_hash"


class ExitPoolTransactionSignatureRound(TransactionSignatureBaseRound):
    """This class represents the SwapBack signature round."""

    round_id = "exit_pool_tx_signature"


class ExitPoolTransactionSendRound(TransactionSendBaseRound):
    """This class represents the SwapBack send round."""

    round_id = "exit_pool_tx_send"


class ExitPoolTransactionValidationRound(TransactionValidationBaseRound):
    """This class represents the SwapBack validation round."""

    round_id = "exit_pool_tx_validation"


class ExitPoolRandomnessRound(RandomnessRound):
    """Exit pool randomness round."""

    round_id = "exit_pool_randomness"


class ExitPoolSelectKeeperRound(
    CollectSameUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """This class represents the SwapBack select keeper round."""

    round_id = "exit_pool_select_keeper"


class SwapBackTransactionHashRound(TransactionHashBaseRound):
    """This class represents the SwapBack transaction hash round."""

    round_id = "swap_back_tx_hash"


class SwapBackTransactionSignatureRound(TransactionSignatureBaseRound):
    """This class represents the SwapBack signature round."""

    round_id = "swap_back_tx_signature"


class SwapBackTransactionSendRound(TransactionSendBaseRound):
    """This class represents the SwapBack send round."""

    round_id = "swap_back_tx_send"


class SwapBackTransactionValidationRound(TransactionValidationBaseRound):
    """This class represents the SwapBack validation round."""

    round_id = "swap_back_tx_validation"


class SwapBackRandomnessRound(RandomnessRound):
    """Exit pool randomness round."""

    round_id = "swap_back_randomness"


class SwapBackSelectKeeperRound(
    CollectSameUntilThresholdRound, LiquidityProvisionAbstractRound
):
    """This class represents the SwapBack select keeper round."""

    round_id = "swap_back_select_keeper"


class LiquidityProvisionAbciApp(AbciApp[Event]):
    """Liquidity Provision ABCI application."""

    initial_round_cls: Type[AbstractRound] = ResetRound
    transition_function: AbciAppTransitionFunction = {
        ResetRound: {
            Event.DONE: StrategyEvaluationRound,
        },
        StrategyEvaluationRound: {
            Event.DONE: EnterPoolTransactionHashRound,
            Event.WAIT: ResetAndPauseRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        EnterPoolTransactionHashRound: {
            Event.DONE: EnterPoolTransactionSignatureRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        EnterPoolTransactionSignatureRound: {
            Event.DONE: EnterPoolTransactionSendRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        EnterPoolTransactionSendRound: {
            Event.DONE: EnterPoolTransactionValidationRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        EnterPoolTransactionValidationRound: {
            Event.DONE: ResetAndPauseRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
            Event.ROUND_TIMEOUT: EnterPoolRandomnessRound,
        },
        EnterPoolRandomnessRound: {
            Event.DONE: EnterPoolSelectKeeperRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        EnterPoolSelectKeeperRound: {
            Event.DONE: ExitPoolTransactionHashRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ExitPoolTransactionHashRound: {
            Event.DONE: ExitPoolTransactionSignatureRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ExitPoolTransactionSignatureRound: {
            Event.DONE: ExitPoolTransactionSendRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ExitPoolTransactionSendRound: {
            Event.DONE: ExitPoolTransactionValidationRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ExitPoolTransactionValidationRound: {
            Event.DONE: SwapBackTransactionHashRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
            Event.ROUND_TIMEOUT: ExitPoolRandomnessRound,
        },
        ExitPoolRandomnessRound: {
            Event.DONE: ExitPoolSelectKeeperRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ExitPoolSelectKeeperRound: {
            Event.DONE: ExitPoolTransactionHashRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        SwapBackTransactionHashRound: {
            Event.DONE: SwapBackTransactionSignatureRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        SwapBackTransactionSignatureRound: {
            Event.DONE: SwapBackTransactionSendRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        SwapBackTransactionSendRound: {
            Event.DONE: SwapBackTransactionValidationRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        SwapBackTransactionValidationRound: {
            Event.DONE: ResetAndPauseRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
            Event.ROUND_TIMEOUT: SwapBackRandomnessRound,
        },
        SwapBackRandomnessRound: {
            Event.DONE: SwapBackSelectKeeperRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        SwapBackSelectKeeperRound: {
            Event.DONE: SwapBackTransactionHashRound,
            Event.ROUND_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
        ResetAndPauseRound: {
            Event.DONE: StrategyEvaluationRound,
            Event.RESET_TIMEOUT: ResetRound,
            Event.NO_MAJORITY: ResetRound,
        },
    }
    event_to_timeout: Dict[Event, float] = {
        Event.EXIT: 5.0,
        Event.ROUND_TIMEOUT: 30.0,
    }
