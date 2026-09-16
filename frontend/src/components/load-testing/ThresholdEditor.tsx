import type { LoadThresholds } from "../../types/loadTesting";

const fields: { key: keyof LoadThresholds; label: string; suffix: string }[] = [
  { key: "max_p95_ms", label: "Maximum p95", suffix: "ms" },
  { key: "max_p99_ms", label: "Maximum p99", suffix: "ms" },
  { key: "max_average_ms", label: "Maximum average", suffix: "ms" },
  { key: "max_failure_rate", label: "Maximum failure rate", suffix: "%" },
  { key: "min_rps", label: "Minimum throughput", suffix: "req/s" },
  { key: "max_error_count", label: "Maximum errors", suffix: "" },
];

export function ThresholdEditor({ value, onChange }: { value: LoadThresholds; onChange: (value: LoadThresholds) => void }) {
  return <div className="threshold-grid">{fields.map((field) => <label className="field" key={field.key}><span>{field.label}</span><div className="input-suffix"><input aria-label={field.label} type="number" min="0" step="any" value={value[field.key] ?? ""} onChange={(event) => onChange({ ...value, [field.key]: event.target.value === "" ? null : Number(event.target.value) })} /><small>{field.suffix}</small></div></label>)}</div>;
}
