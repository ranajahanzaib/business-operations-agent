# Workflow behavior

The workflow accepts a bounded request, persists run metadata, asks the configured provider to select registered read or proposal tools, validates and executes those calls, then creates a hashed proposal. Supported proposals cover delayed-delivery tickets, inventory reservations, and ticket-priority escalation. LangGraph checkpoints the bounded run state and pauses at a human approval interrupt.

On approval the API validates the operator and proposal, checks the hash and current business state, writes business rows and ledger entries in one transaction, then queries committed records to verify the relevant invariants. The workflow checkpoint resumes after the application transaction. Rejection resumes the interrupt without applying business state.

All business fixtures use synthetic identities and a documented reference timestamp. The delayed comparison is strict: a promise exactly five days before the reference time does not match a “more than five days” request.
