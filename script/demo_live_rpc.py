import json
from urllib.request import Request, urlopen
from script.fetch_rpc_transfers import fetch_rpc_transfers
from urllib.error import HTTPError
import os


ENDPOINT = os.environ["BASE_RPC_URL"]
TOKEN = "0x914F6b6a0DaD39A3CB932dcf4D1af885C7c08EeB"
BLOCK = 41988939


def rpc_call(request):

    body = json.dumps(request).encode("utf-8")

    http_request = Request(
        url=ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json", 
            "User-Agent": "SourceMint-RPC-Demo/0.1",
        },
        method="POST",
    )

    try:
        with urlopen(http_request, timeout=10) as response:
            return json.load(response)
        
    except HTTPError as error:
        print("HTTP status:", error.code)
        print("Reason:", error.reason)
        print("Response headers:")
        print(error.headers)

        error_body = error.read().decode("utf-8", errors="replace")
        print("Response body:")
        print(error_body[:3000])

        raise


def main():
    transfers = fetch_rpc_transfers(TOKEN, BLOCK, BLOCK, rpc_call)

    print("Jumlah log:", len(transfers))
    print(json.dumps(transfers, indent=2))



if __name__ == "__main__":
    main()


