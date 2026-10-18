"""Unlock the key once, then start a single local API worker."""

import argparse
import getpass

import uvicorn
from cryptography.hazmat.primitives import serialization

from app.config import Settings
from app.launcher import listener, stop_previous
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run independent-answer evaluation with real Gemma/Snowflake, then serve.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Gracefully replace only a verified existing DataMind server on this port.",
    )
    parser.add_argument(
        "--load-worldbank",
        action="store_true",
        help="Download World Bank WDI indicators and load them into Snowflake, then exit.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Start server in development mode without requiring Snowflake credentials.",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be in 1..65535.")
    if listener(args.port) is not None and not args.replace and not args.load_worldbank:
        raise SystemExit("DataMind already occupies this port. Use --replace or choose another --port.")
    settings = Settings()
    if args.dev:
        if args.replace:
            stop_previous(args.port)
        app = create_app(settings)
        print(f"DataMind server running in DEV mode on http://127.0.0.1:{args.port}...")
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
        return
    if not settings.snowflake_account or not settings.snowflake_user:
        raise SystemExit(
            "Missing account/login name. Copy .env.example to .env and edit it, or use --dev for local mode."
        )
    key_path = settings.snowflake_private_key_path.expanduser()
    if not key_path.is_file():
        raise SystemExit(f"Private key not found: {key_path}")
    secret = settings.snowflake_private_key_passphrase
    passphrase = secret.get_secret_value() if secret else getpass.getpass("Private-key passphrase: ")
    try:
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=passphrase.encode())
    except (ValueError, TypeError):
        raise SystemExit("Could not unlock the private key. Check the passphrase and key format.") from None
    private_key = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    del passphrase, key
    if args.load_worldbank:
        from scripts.worldbank_wdi import admin_session
        from scripts.worldbank_wdi import prepare_data as prepare_wdi
        from scripts.worldbank_wdi import provision as provision_wdi

        print("Loading World Bank WDI using ACCOUNTADMIN; the API stays DATAMIND_READER.", flush=True)
        with admin_session(settings, private_key) as connection:
            result = provision_wdi(connection, settings, prepare_wdi())
        print(f"Loaded and verified {result['row_count']:,} rows in {result['table']}.", flush=True)
        return
    app = create_app(settings, private_key)
    if args.evaluate:
        from scripts.evaluate import run_evaluation

        evaluation = run_evaluation(app, settings, private_key)
        if evaluation["passed"] != evaluation["total"]:
            raise SystemExit(
                "Evaluation failed; previous server was left running. Inspect data/evaluations/latest.json."
            )
    if args.replace:
        stop_previous(args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
