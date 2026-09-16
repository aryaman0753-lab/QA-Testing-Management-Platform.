import type { KeyValueItem } from "../../types/apiTesting";

export function KeyValueEditor({ items, onChange, valueType = "text" }: { items: KeyValueItem[]; onChange: (items: KeyValueItem[]) => void; valueType?: "text" | "password" }) {
  function update(index: number, patch: Partial<KeyValueItem>) { onChange(items.map((item, i) => i === index ? { ...item, ...patch } : item)); }
  return <div className="kv-editor">{items.map((item, index) => <div className="kv-row" key={index}>
    <input aria-label={`Enable row ${index + 1}`} type="checkbox" checked={item.enabled} onChange={(e) => update(index, { enabled: e.target.checked })} />
    <input aria-label={`Key ${index + 1}`} placeholder="Key" value={item.key} onChange={(e) => update(index, { key: e.target.value })} />
    <input aria-label={`Value ${index + 1}`} type={valueType} placeholder="Value" value={item.value} onChange={(e) => update(index, { value: e.target.value })} />
    <button type="button" className="icon-button" aria-label={`Remove row ${index + 1}`} onClick={() => onChange(items.filter((_, i) => i !== index))}>×</button>
  </div>)}<button type="button" className="inline-link" onClick={() => onChange([...items, { key: "", value: "", enabled: true }])}>+ Add row</button></div>;
}
