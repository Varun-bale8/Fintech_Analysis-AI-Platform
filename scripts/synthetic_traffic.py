from __future__ import annotations

import argparse
import os
import random
import time
import uuid

import requests

QUESTIONS = [
    # ---------------------------------------------------------
    # HDFC Bank
    # ---------------------------------------------------------
    "What was HDFC Bank's net profit in 2024?",
    "How did HDFC Bank's total deposits change from 2023 to 2024?",
    "What were HDFC Bank's total assets in 2024?",
    "Who was the Managing Director and CEO of HDFC Bank in 2024?",
    "What was HDFC Bank's Net Interest Margin (NIM) in 2024?",
    # ---------------------------------------------------------
    # ICICI Bank
    # ---------------------------------------------------------
    "What was ICICI Bank's profit after tax in 2024?",
    "How did ICICI Bank's total advances change from 2023 to 2024?",
    "What was ICICI Bank's Net NPA ratio in 2024?",
    "Who was the Managing Director and CEO of ICICI Bank in 2024?",
    "What were ICICI Bank's gross additions to NPAs in 2024?",
    # ---------------------------------------------------------
    # Paytm (One97 Communications)
    # ---------------------------------------------------------
    "What was Paytm's operational revenue in 2024?",
    "How did Paytm's contribution profit change from 2023 to 2024?",
    "How many active payment soundbox devices did Paytm deploy by 2024?",
    "Who was the Chief Executive Officer of Paytm in 2024?",
    "What was Paytm's EBITDA before ESOP cost in 2024?",
    # ---------------------------------------------------------
    # Cross-company comparisons
    # ---------------------------------------------------------
    "Compare the total assets of HDFC Bank and ICICI Bank in 2024.",
    "Compare the net profit after tax of HDFC Bank and ICICI Bank in 2024.",
    "Which of HDFC Bank and ICICI Bank reported a lower Net NPA ratio in 2024?",
    "Compare the revenue growth of HDFC Bank, ICICI Bank, and Paytm from 2023 to 2024.",
    "Who were the chief executives of HDFC Bank, ICICI Bank, and Paytm in 2024?",
]


def send_request(
    base_url: str,
    pipeline: str,
) -> None:

    question = random.choice(QUESTIONS)

    payload = {
        "question": question,
        "session_id": str(uuid.uuid4()),
        "pipeline": pipeline,
        "retrieval_mode": "hybrid",
        "top_k": 8,
        "ticker": None,
        "report_year": None,
        "model": "gemini-2.5-flash",
    }

    started = time.perf_counter()

    try:

        response = requests.post(
            f"{base_url}/api/v1/query",
            json=payload,
            timeout=180,
        )

        elapsed = time.perf_counter() - started

        if response.ok:

            result = response.json()

            print(f"✓ {pipeline.upper():5} | " f"{elapsed:6.2f}s | " f"{question}")

            response_id = result.get("response_id")

            if response_id:

                print(f"  response_id=" f"{response_id}")

        else:

            print(
                f"✗ {pipeline.upper():5} | "
                f"HTTP {response.status_code} | "
                f"{response.text[:200]}"
            )

    except requests.RequestException as exc:

        print(f"✗ {pipeline.upper():5} | " f"{exc}")


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--requests",
        type=int,
        default=10,
        help="Number of synthetic requests.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between requests.",
    )

    parser.add_argument(
        "--pipeline",
        choices=[
            "rag",
            "agent",
            "mixed",
        ],
        default="mixed",
    )

    args = parser.parse_args()

    base_url = os.getenv(
        "FASTAPI_BASE_URL",
        "http://localhost:8000",
    ).rstrip("/")

    print(f"\nSending {args.requests} " f"synthetic requests to {base_url}\n")

    for index in range(args.requests):

        if args.pipeline == "mixed":

            pipeline = random.choice(
                [
                    "rag",
                    "agent",
                ]
            )

        else:

            pipeline = args.pipeline

        print(
            f"[{index + 1}/{args.requests}]",
            end=" ",
        )

        send_request(
            base_url=base_url,
            pipeline=pipeline,
        )

        if index < args.requests - 1:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
