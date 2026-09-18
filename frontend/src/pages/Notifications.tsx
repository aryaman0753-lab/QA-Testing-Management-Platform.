import { useEffect, useState } from "react";
import { getNotificationPreferences, listNotifications, markNotificationRead, saveNotificationPreferences } from "../api/operations";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { useToast } from "../context/ToastContext";

export function Notifications() {
  const { showToast } = useToast(); const [items,setItems]=useState<any[]>([]); const [prefs,setPrefs]=useState({project_id:null,in_app_enabled:true,email_enabled:false,webhook_enabled:true,events:[]} as any);
  function refresh(){ listNotifications().then(r=>setItems(r.data)); getNotificationPreferences().then(r=>{const global=r.data.find((x:any)=>!x.project_id); if(global)setPrefs(global);}); }
  useEffect(refresh,[]);
  async function save(){ try{await saveNotificationPreferences(prefs); showToast("Notification preferences saved.","success");}catch{showToast("Preferences could not be saved.","error");}}
  return <AppLayout><div className="page-header"><div><h1>Notifications</h1><p className="muted">Failure alerts and project activity without duplicate noise.</p></div></div><section className="panel"><h2>Default channels</h2><div className="button-row"><label><input type="checkbox" checked={prefs.in_app_enabled} onChange={e=>setPrefs({...prefs,in_app_enabled:e.target.checked})}/> In-app</label><label><input type="checkbox" checked={prefs.email_enabled} onChange={e=>setPrefs({...prefs,email_enabled:e.target.checked})}/> Email</label><label><input type="checkbox" checked={prefs.webhook_enabled} onChange={e=>setPrefs({...prefs,webhook_enabled:e.target.checked})}/> Webhook</label><Button onClick={save}>Save</Button></div></section><section className="panel"><h2>Inbox</h2>{items.length===0?<p className="muted">No notifications yet.</p>:<table className="table"><thead><tr><th>Event</th><th>Message</th><th>When</th><th/></tr></thead><tbody>{items.map(row=><tr key={row.id}><td>{row.event}</td><td><strong>{row.title}</strong><br/><span className="muted">{row.message}</span></td><td>{new Date(row.created_at).toLocaleString()}</td><td>{!row.is_read&&<Button variant="secondary" onClick={()=>markNotificationRead(row.id).then(refresh)}>Mark read</Button>}</td></tr>)}</tbody></table>}</section></AppLayout>;
}
