# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022 Valory AG
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

"""This module contains the class to connect to the Service Registry contract."""

import hashlib
import logging
from typing import Any, Dict, Tuple, cast

from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi, LedgerApi

# test_contract and test_agents, respectively...
DEPLOYED_BYTECODE_MD5_HASH = "288a5ecfe0b685d93f174ec24f743458679a4948d6517d77957fd67b72e5982eb85f543329059eabada38428eef9d548e407b1e0d60dd83af60099ea76bf5a76"
DEPLOYED_BYTECODE_MD5_HASH = "2efb3d8756e0c16b79f15785774d02b7a7f1103c322fa000137bfda2fe4ed1b90352bd8e2f0c0be47357476332c88c8e477df8037ea35347e8275feccf58c4d9"
DEPLOYED_BYTECODE_MD5_HASH = "fa67f4a5dff3f392b506c42816bc90086422a22a64103a11aa59640f036b8f8c70facdea13f8af9f893c25a0c838a9d0b03fed4a6c77b1d36f0beefe92b9379a"
DEPLOYED_BYTECODE_MD5_HASH = "75d2a79df580ba1353211f93c479a9d6b78cc8f14e724290329e274fdcab4dc8cc04adbd8efbbce00a01af2dd6873f7e66a8c338a3d4f87a31ab0e283eef89de"

ConfigHash = Tuple[bytes, int, int]
AgentParams = Tuple[int, int]

PUBLIC_ID = PublicId.from_str("valory/service_registry:0.1.0")

_logger = logging.getLogger(
    f"aea.packages.{PUBLIC_ID.author}.contracts.{PUBLIC_ID.name}.contract"
)


class ServiceRegistryContract(Contract):
    """The Service Registry contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def verify_contract(
        cls, ledger_api: LedgerApi, contract_address: str
    ) -> Dict[str, bool]:
        """
        Verify the contract's bytecode

        :param ledger_api: the ledger API object
        :param contract_address: the contract address
        :return: the verified status
        """
        ledger_api = cast(EthereumApi, ledger_api)
        deployed_bytecode = ledger_api.api.eth.get_code(contract_address).hex()
        sha512_hash = hashlib.sha512(deployed_bytecode.encode("utf-8")).hexdigest()
        verified = DEPLOYED_BYTECODE_MD5_HASH == sha512_hash
        return dict(verified=verified, sha512_hash=sha512_hash)

    @classmethod
    def exists(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        service_id: int,
    ) -> bool:
        """Check if the service id exists"""

        contract_instance = cls.get_instance(ledger_api, contract_address)
        exists = ledger_api.contract_method_call(
            contract_instance=contract_instance,
            method_name="exists",
            serviceId=service_id,
        )

        return cast(bool, exists)

    @classmethod
    def get_service_info(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        service_id: int,
    ) -> Dict[str, Any]:
        """Retrieve on-chain service information"""

        contract_instance = cls.get_instance(ledger_api, contract_address)
        service_info = ledger_api.contract_method_call(
            contract_instance=contract_instance,
            method_name="getServiceInfo",
            serviceId=service_id,
        )

        return dict(
            owner=service_info[0],
            name=service_info[1],
            description=service_info[2],
            config_hash=service_info[3],
            threshold=service_info[4],
            num_agent_ids=service_info[5],
            agent_ids=service_info[6],
            agent_params=service_info[7],
            num_agent_instances=service_info[8],
            agent_instances=service_info[9],
            multisig=service_info[10],
        )
