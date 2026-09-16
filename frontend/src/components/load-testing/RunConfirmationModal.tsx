import type { LoadTest } from "../../types/loadTesting";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

export function RunConfirmationModal({ test, busy, onCancel, onConfirm }: { test: LoadTest; busy: boolean; onCancel: () => void; onConfirm: (productionConfirmed: boolean) => void }) {
  const production = test.environment_classification === "PRODUCTION";
  return <Modal title={production ? "Production load-test warning" : "Start load test?"} onClose={onCancel}>
    <div className={production ? "alert alert-error" : "load-confirm-summary"}>
      {production ? "This environment is classified as production. Load can degrade or interrupt real services." : "This will send real traffic from the dedicated load worker."}
    </div>
    <dl className="load-config-list"><dt>Target</dt><dd>{test.target_url}</dd><dt>Users</dt><dd>{test.virtual_users}</dd><dt>Spawn rate</dt><dd>{test.spawn_rate}/s</dd><dt>Duration</dt><dd>{test.duration_seconds}s</dd><dt>Target RPS</dt><dd>{test.target_rps ?? "Uncapped"}</dd></dl>
    <div className="modal-actions"><Button variant="secondary" onClick={onCancel}>Cancel</Button><Button variant={production ? "danger" : "primary"} isLoading={busy} onClick={() => onConfirm(production)}>{production ? "I understand, run in production" : "Start run"}</Button></div>
  </Modal>;
}
