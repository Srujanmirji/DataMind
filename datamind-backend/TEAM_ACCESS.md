# Snowflake access from teammates' laptops

Everyone can use the same Snowflake account and existing datasets with their own
Snowflake user. Each person should have the existing `DATAMIND_READER` role.
Do not distribute the account owner's password, private key or key passphrase.

Frontend-only work needs the backend API described in [UI_HANDOFF.md](UI_HANDOFF.md).
Snowflake credentials belong on the backend. The current server binds to
`127.0.0.1`, which only works on its host Mac. A shared backend URL/deployment is
needed for remote frontend access; pushing Git does not create that deployment.

## 1. Owner creates a separate user for each teammate

In Snowsight, use an authorized user administrator and open **Governance & security
→ Users & roles → + User**. Choose a unique user name, supply a unique temporary
password, and leave **Force user to change password on first time login** enabled.
Set the default role to `DATAMIND_READER` and warehouse to
`SNOWFLAKE_LEARNING_WH`. Each teammate changes their own password and completes
MFA enrollment when signing in.

Setting a default role does not grant it. An authorized role administrator must
run this once per newly created user, replacing the quoted placeholder with that
user's Snowflake **NAME**:

```sql
USE ROLE SECURITYADMIN;
GRANT ROLE DATAMIND_READER TO USER "TEAMMATE_USER_NAME";
```

The role already has access to this project's existing datasets in the owner's
account. Teammates do not need to import the data again or run the admin demo.
Do not grant ACCOUNTADMIN to connect a laptop.

Share the account's Snowsight sign-in link/account identifier and that person's
own login details privately. They sign into that account from their own browser;
they do not need a new Snowflake trial account.

## 2. Teammate verifies browser access

Run in their own Snowsight worksheet:

```sql
USE ROLE DATAMIND_READER;
USE WAREHOUSE SNOWFLAKE_LEARNING_WH;
SELECT CURRENT_USER(), CURRENT_ROLE();
SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS;
SELECT COUNT(*) FROM DATAMIND_DEMO.UCI.WINE_QUALITY_WORKING_V1;
```

Expected observation counts: **1,500,000 orders** and **6,497 wine samples**.
These are the existing account tables. Resolve permission errors through the
administrator rather than changing the application to ACCOUNTADMIN.

## 3. Optional: run the backend on their laptop

Browser-only access does not require the following steps. A teammate running
the Python backend needs their own key pair, Python environment and Ollama model.

Clone the project and install the backend dependencies (Python 3.13 was tested):

```bash
git clone https://github.com/ZERODAY-2026/Codex.git
cd Codex/datamind-backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

These shell commands target macOS/Linux. On Windows activate the environment
with `.venv\Scripts\Activate.ps1` and use an installed OpenSSL for key generation.
Create `.env` only if it does not exist; preserve any existing local configuration.

Generate an encrypted key **on that teammate's laptop**. The guard below preserves
an existing private key. Enter a private passphrase in the local terminal:

```bash
mkdir -p ~/.snowflake
chmod 700 ~/.snowflake
if [ -e ~/.snowflake/datamind_team_key.p8 ]; then
  echo "Key already exists; reuse it or choose another filename."
else
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
    -aes-256-cbc -out ~/.snowflake/datamind_team_key.p8
fi
chmod 600 ~/.snowflake/datamind_team_key.p8
openssl pkey -in ~/.snowflake/datamind_team_key.p8 -pubout \
  -out ~/.snowflake/datamind_team_key.pub
```

Send only the `.pub` file to the account administrator. The private `.p8` file and
its passphrase stay on the teammate's laptop. The administrator registers the
public key on that teammate's user, using the base64 body without PEM headers:

```sql
ALTER USER "TEAMMATE_USER_NAME"
  SET RSA_PUBLIC_KEY='PUBLIC_KEY_BODY_WITHOUT_PEM_HEADERS';
```

Set these values in that laptop's ignored `.env`:

```dotenv
SNOWFLAKE_ACCOUNT=OWNER_ORGANIZATION-OWNER_ACCOUNT
SNOWFLAKE_USER=TEAMMATE_LOGIN_NAME
SNOWFLAKE_ROLE=DATAMIND_READER
SNOWFLAKE_WAREHOUSE=SNOWFLAKE_LEARNING_WH
SNOWFLAKE_DATABASE=SNOWFLAKE_SAMPLE_DATA
SNOWFLAKE_SCHEMA=TPCH_SF1
SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/datamind_team_key.p8
OLLAMA_MODEL=gemma3:12b
```

Use their **LOGIN_NAME** for the connector if it differs from their Snowflake
user NAME. Leave the private-key passphrase out of `.env`.

With Ollama installed/running and `gemma3:12b` downloaded, launch:

```bash
ollama pull gemma3:12b
python run.py
```

Enter their own key passphrase privately and keep the terminal open. Open
`http://127.0.0.1:8000/docs` on that laptop. No `--demo` or admin privileges are
needed to use the already loaded datasets. See [README.md](README.md) for model
resource requirements, API usage and evaluation commands.

## Official references

- [Snowflake user creation and role assignment](https://docs.snowflake.com/en/user-guide/admin-user-management)
- [Key-pair authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth)
