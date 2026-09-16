import type { AuthenticationType } from "../../types/apiTesting";

export function AuthEditor({ type, config, onType, onConfig }: { type: AuthenticationType; config: Record<string, string>; onType: (type: AuthenticationType) => void; onConfig: (config: Record<string, string>) => void }) {
  const set = (key: string, value: string) => onConfig({ ...config, [key]: value });
  return <div><label className="field"><span>Authentication</span><select aria-label="Authentication type" value={type} onChange={(e) => onType(e.target.value as AuthenticationType)}>{["NONE", "BEARER", "BASIC", "API_KEY"].map((item) => <option key={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
    {type === "BEARER" && <label className="field"><span>Bearer token</span><input type="password" value={config.token ?? ""} onChange={(e) => set("token", e.target.value)} placeholder="{{access_token}}" /></label>}
    {type === "BASIC" && <div className="form-grid"><label className="field"><span>Username</span><input value={config.username ?? ""} onChange={(e) => set("username", e.target.value)} /></label><label className="field"><span>Password</span><input type="password" value={config.password ?? ""} onChange={(e) => set("password", e.target.value)} /></label></div>}
    {type === "API_KEY" && <div className="form-grid"><label className="field"><span>Key</span><input value={config.key ?? ""} onChange={(e) => set("key", e.target.value)} placeholder="X-API-Key" /></label><label className="field"><span>Value</span><input type="password" value={config.value ?? ""} onChange={(e) => set("value", e.target.value)} placeholder="{{api_key}}" /></label><label className="field"><span>Add to</span><select value={config.location ?? "header"} onChange={(e) => set("location", e.target.value)}><option value="header">Header</option><option value="query">Query parameter</option></select></label></div>}
  </div>;
}
