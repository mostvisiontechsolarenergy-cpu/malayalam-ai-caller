# Local n8n connection

This setup adds n8n as an internal automation service beside the existing Dcreation
frontend and backend. It does not route live phone audio through n8n.

## Local addresses

- Dcreation frontend: `http://localhost:3000`
- Dcreation backend: `http://localhost:8000`
- n8n editor: `http://localhost:5678`

Inside Docker, n8n reaches the backend at `http://backend:8000/api/v1`.

## Start the services

1. Start Docker Desktop and wait until the engine reports that it is running.
2. Open PowerShell in this project directory.
3. Run:

   ```powershell
   docker compose up --build -d
   docker compose ps
   ```

4. Open `http://localhost:5678` and create the local n8n owner account.

The Compose defaults are for localhost development only. Before production, set strong
unique values in `.env` for:

```dotenv
AUTOMATION_SHARED_SECRET=
N8N_POSTGRES_PASSWORD=
N8N_ENCRYPTION_KEY=
```

Each value must be a different long random value. Never reuse the JWT secret and never
publish `.env`.

## Import the connection check

1. In n8n, select **Create Workflow**.
2. Open the workflow menu and choose **Import from File**.
3. Select `n8n/workflows/dcreation-local-connection.json`.
4. Open the imported workflow.
5. Select **Execute Workflow**.

The final node should return:

```json
{
  "status": "ready",
  "connector": "automation"
}
```

The request is authenticated with the internal `X-Automation-Secret` header. The secret
is injected into both containers and is not stored in the workflow file.

## Safe implementation order after the connection check

1. Add proposal-request recording to Maya and Soorya.
2. Add proposal approval and an authenticated `proposal.approved` event.
3. Connect a WhatsApp Business Cloud test account.
4. Add the proposal-delivery n8n workflow.
5. Add payment orders and signed payment webhooks.
6. Generate an invoice only after a verified captured payment.
7. Add the invoice-delivery n8n workflow.

Do not add WhatsApp or payment secrets until their provider accounts are ready. Live
payment webhooks must terminate in the Dcreation backend so the raw signature can be
verified before n8n receives any invoice event.
