#!/usr/bin/env python3

import sys

from validate_runbook_contract import main


if __name__ == "__main__":
    sys.exit(
        main(
            default_contract="config/runtime-integration-runbook-contract.json",
            description="Validate runtime integration runbook contract",
        )
    )
