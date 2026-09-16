import type { ApiEnvironment } from "../../types/apiTesting";

export function EnvironmentSelector({ environments, value, onChange, onManage }: { environments: ApiEnvironment[]; value: string; onChange: (id: string) => void; onManage: () => void }) {
  return <div className="environment-select"><span>Environment:</span><select aria-label="Environment" value={value} onChange={(e) => onChange(e.target.value)}><option value="">No environment</option>{environments.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><button onClick={onManage}>Manage</button></div>;
}
