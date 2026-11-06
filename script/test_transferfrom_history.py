from functools import partial
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

if __package__:
    from . import verify_ledger as verifier
else:
    import verify_ledger as verifier

alice = "0x" + "0" * 35 + "A11CE"
bob = "0x" + "0" * 37 + "B0B"
charlie = "0x" + "11" * 20

TRANSFER_TOPIC = verifier.TRANSFER_TOPIC
APPROVAL_TOPIC = verifier.APPROVAL_TOPIC
TOKEN = "0x914F6b6a0DaD39A3CB932dcf4D1af885C7c08EeB"
BLOCK_HASH = "0x" + "ab" * 32
UNLIMITED = 2**256 - 1
INITIAL_SUPPLY = 100 * 10**18
TRANSFER_AMOUNT = 40 * 10**18


def encode_uint256(value):
    return "0x" + format(value, "064x")


def encode_address(address):
    return "0x" + address[2:].zfill(64)


transactions = [
    {
      "address": TOKEN,
      "topics": [
        TRANSFER_TOPIC,
        encode_address(verifier.ZERO_ADDRESS),
        encode_address(alice)
      ],
      "data": encode_uint256(INITIAL_SUPPLY),
      "blockNumber": hex(1),
      "transactionHash": "0x9ebd9461d1973d565c0a53c054e3eb058b1b2a14d0982cea11db488b455a7dab",
      "removed": False,
      "logIndex": "0x0",
      "transactionIndex": "0x0",
      "blockHash": BLOCK_HASH,
    },
    {
      "address": TOKEN,
      "topics": [
        APPROVAL_TOPIC,
        encode_address(alice),
        encode_address(bob)
      ],
      "data": encode_uint256(UNLIMITED),
      "blockNumber": hex(100),
      "transactionHash": "0x86a5bd78d3dc4fd44a343a32442ba6a360c898854760992b5f07a910c61662b4",
      "removed": False,
      "logIndex": "0x0",
      "transactionIndex": "0x0",
      "blockHash": BLOCK_HASH,
    },
    {
      "address": TOKEN,
      "topics": [
        TRANSFER_TOPIC,
        encode_address(alice),
        encode_address(charlie)
      ],
      "data": encode_uint256(TRANSFER_AMOUNT),
      "blockNumber": hex(200),
      "transactionHash": "0xfb5ddb6a645715d2ce34e02db73ca26cf996a61501fca847a0ab382da8cea1af",
      "removed": False,
      "logIndex": "0x0",
      "transactionIndex": "0x0",
      "blockHash": BLOCK_HASH,
    },
    {
      "address": TOKEN,
      "topics": [
        TRANSFER_TOPIC,
        encode_address(charlie),
        encode_address(alice)
      ],
      "data": encode_uint256(TRANSFER_AMOUNT),
      "blockNumber": hex(201),
      "transactionHash": "0x0404040404040404040404040404040404040404040404040404040404040404",
      "removed": False,
      "logIndex": "0x0",
      "transactionIndex": "0x0",
      "blockHash": BLOCK_HASH,
    },
    {
      "address": TOKEN,
      "topics": [
        APPROVAL_TOPIC,
        encode_address(alice),
        encode_address(bob)
      ],
      "data": encode_uint256(0),
      "blockNumber": hex(202),
      "transactionHash": "0x0505050505050505050505050505050505050505050505050505050505050505",
      "removed": False,
      "logIndex": "0x0",
      "transactionIndex": "0x0",
      "blockHash": BLOCK_HASH,
    },
]

transaction_senders = {1: alice, 100: alice, 200: bob, 201: charlie, 202: alice}


def mock_rpc(method, params, *, latest_block=200):
    if method == "eth_getTransactionCount":
        address, block = params
        block = latest_block if block == "latest" else int(block, 16)
        nonce = sum(
            1 for number, sender in transaction_senders.items()
            if number <= block and sender.lower() == address.lower()
        )
        return hex(nonce)

    elif method == "eth_getLogs":
        filters = params[0]
        start = filters.get("fromBlock", "0x0")
        end = filters.get("toBlock", "latest")
        start = latest_block if start == "latest" else int(start, 16)
        end = latest_block if end == "latest" else int(end, 16)
        address = filters.get("address", TOKEN)
        print(f"eth_getLogs read block {start} to {end}")
        return [
            log for log in transactions
            if start <= int(log["blockNumber"], 16) <= end
            and log["address"].lower() == address.lower()
        ]

    elif method == "eth_getBlockByNumber":
        block, full_transactions = params
        block = latest_block if block == "latest" else int(block, 16)
        if block > latest_block:
            return None
        block_transactions = [
            {"hash": log["transactionHash"],
             "from": transaction_senders[block], "to": TOKEN}
            if full_transactions else log["transactionHash"]
            for log in transactions if int(log["blockNumber"], 16) == block
        ]
        return {"number": hex(block), "hash": BLOCK_HASH,
                "transactions": block_transactions}

    elif method == "eth_blockNumber":
        return hex(latest_block)

    elif method == "eth_call":
        call, block = params
        assert call["to"].lower() == TOKEN.lower(), "Unexpected token"
        block = latest_block if block == "latest" else int(block, 16)
        data = call["data"].lower()

        if data == verifier.TOTAL_SUPPLY_SELECTOR:
            return encode_uint256(INITIAL_SUPPLY if block >= 1 else 0)

        if data.startswith(verifier.BALANCE_OF_SELECTOR):
            address = "0x" + data[-40:]
            moved = TRANSFER_AMOUNT if block == 200 else 0
            balances = {
                alice.lower(): (INITIAL_SUPPLY if block >= 1 else 0) - moved,
                charlie.lower(): moved,
            }
            return encode_uint256(balances.get(address, 0))

        if data.startswith(verifier.ALLOWANCE_SELECTOR):
            raise verifier.SourceUnavailable("Mock allowance RPC failure")
            owner = "0x" + data[10:74][-40:]
            spender = "0x" + data[74:138][-40:]
            approved = 100 <= block < 202 and owner == alice.lower() and spender == bob.lower()
            return encode_uint256(UNLIMITED if approved else 0)

        raise AssertionError(f"Unexpected eth_call data: {data}")

    raise AssertionError(f"Unexpected RPC method: {method}")


def mock_rpc_response(payload, endpoint=None, *, latest_block=200):
    return {
        "jsonrpc": "2.0",
        "id": payload["id"],
        "result": mock_rpc(payload["method"], payload["params"], latest_block=latest_block),
    }


def make_mock_ledger():
    return {
        "token": TOKEN,
        "chain_id": 8453,
        "project_wallets": {"alice": alice},
        "entries": [{
            "tx": transactions[0]["transactionHash"],
            "date": "2026-11-02",
            "from": "mint",
            "to": alice,
            "amount": "100",
            "reason": "Initial mint",
        }],
    }


def run_main(ledger, *, latest_block=200):
    output = io.StringIO()
    with (
        patch.object(verifier, "DEPLOYMENT_BLOCK", 1),
        patch.object(verifier, "LIVE_SPENDERS", []),
        patch.object(verifier, "LEDGER_PATH") as ledger_path,
        patch.object(
            verifier,
            "rpc_call",
            side_effect=partial(mock_rpc_response, latest_block=latest_block),
        ),
        redirect_stdout(output),
    ):
        ledger_path.read_text.return_value = json.dumps(ledger)
        code = verifier.main()
    return code, output.getvalue()


class RegressionTest(unittest.TestCase):

    def test_confirmed_violation_survives_allowance_rpc_failure(self):
        ledger = make_mock_ledger()
        ledger["project_wallets"]["bob"] = bob

        code, output = run_main(ledger, latest_block=202)

        self.assertEqual(code, 1, msg=output)
        print(output)

    def test_round_trip_then_revoke(self):
        ledger = make_mock_ledger()

        code, output = run_main(ledger, latest_block=202)

        self.assertEqual(code, 1, msg=output)
        print(output)

    def test_allowance_always_infinite(self):
        calldata = verifier.ALLOWANCE_SELECTOR + encode_address(alice)[2:] + encode_address(bob)[2:]
        call = {"to": TOKEN, "data": calldata}

        result199 = mock_rpc("eth_call", [call, hex(199)])
        result200 = mock_rpc("eth_call", [call, hex(200)])

        self.assertEqual(int(result199, 16), UNLIMITED)
        self.assertEqual(int(result200, 16), UNLIMITED)

    def test_empty_block_returns_empty_list(self):
        result = mock_rpc("eth_getBlockByNumber", [hex(50), True])
        self.assertEqual(result["transactions"], [])
        print(result)

    def test_main_reports_transfer_when_bobs_block_is_found(self):
        ledger = make_mock_ledger()
        ledger["project_wallets"]["bob"] = bob

        code, output = run_main(ledger)

        self.assertEqual(code, 1)
        self.assertIn("ledger entries matched: 1/1", output)
        self.assertIn("UNACCOUNTED on-chain movements", output)
        self.assertIn(transactions[2]["transactionHash"], output)
        self.assertIn(f"{alice.lower()} -> {charlie} : 40 SRCMNT", output)
        self.assertIn("RESULT: FAIL", output)

    def test_main_detects_short_balance_when_bob_is_not_tracked(self):
        code, output = run_main(make_mock_ledger())

        self.assertEqual(code, 1)
        self.assertIn("ledger entries matched: 1/1", output)
        self.assertNotIn("UNACCOUNTED on-chain movements", output)
        self.assertIn("BALANCE UNEXPLAINED", output)
        self.assertIn("holds 60 SRCMNT", output)
        self.assertIn("ledger accounts for 100", output)
        self.assertIn("-40 unaccounted", output)
        self.assertIn("OUTSTANDING ALLOWANCES", output)
        self.assertIn("unlimited SRCMNT", output)
        self.assertIn("RESULT: FAIL", output)


if __name__ == "__main__":
    unittest.main()