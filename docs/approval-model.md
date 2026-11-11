# Approval model

Model tool calls are untrusted proposals. Registered model tools are reads only. Proposed ticket records remain in the proposal payload and are not inserted into `support_tickets` before approval.

The operator authenticates with a server-configured bearer token. The approval binds to a stored proposal ID, revision, serialized payload, and hash. The client cannot submit replacement action JSON. The execution transaction verifies the proposal, checks customer/order eligibility and duplicate tickets again, then writes support tickets and unique execution-ledger rows together. The resulting state is independently queried.

Rejecting a proposal changes workflow status but leaves business records untouched. Auditor credentials cannot approve or reject. Default tokens are public demo values. Keep the service on localhost; changing the tokens does not make network exposure safe.

Operators may request changes to a pending proposal. The backend supersedes the exact proposal, exits its approval interrupt without applying actions, and starts a fresh model run with the original request and the modification. The new run must produce a new proposal and receive a new approval.
