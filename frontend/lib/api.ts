import type {AppConfig,BusinessIdeaInput,PlanJob,Project,JobEvent,User} from './types';
const base=process.env.NEXT_PUBLIC_API_URL || '/api';
export class ApiError extends Error {
 constructor(message:string,public status:number){super(message)}
}
async function request<T>(path:string,options:RequestInit={}):Promise<T>{
 const signal=options.signal?AbortSignal.any([options.signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000);
 const res=await fetch(base+path,{...options,signal,credentials:'include',cache:'no-store'});
 if(!res.ok){
  const body=await res.json().catch(()=>null);
  throw new ApiError(typeof body?.detail==='string'?body.detail:
   res.status===422?'Please check the form fields. Passwords need at least 12 characters.':'API error ('+res.status+')',res.status);
 }
 return res.status===204?undefined as T:res.json();
}
const json=(data:unknown)=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
export const getMe=()=>request<User>('/auth/me');
export const signIn=(email:string,password:string,register:boolean)=>request<User>(register?'/auth/register':'/auth/login',json({email,password}));
export const signOut=()=>request<void>('/auth/logout',{method:'POST'});
export const getConfig=(signal?:AbortSignal)=>request<AppConfig>('/config',{signal});
export const listJobs=(offset=0,projectId='',signal?:AbortSignal)=>request<PlanJob[]>('/jobs?limit=20&offset='+offset+(projectId?'&project_id='+encodeURIComponent(projectId):''),{signal});
export const listProjects=(signal?:AbortSignal)=>request<Project[]>('/projects',{signal});
export const renameProject=(id:string,name:string)=>request<Project>('/projects/'+encodeURIComponent(id),{...json({name}),method:'PATCH'});
export const getJob=(id:string,signal?:AbortSignal)=>request<PlanJob>('/jobs/'+encodeURIComponent(id),{signal});
export const getEvents=(id:string,signal?:AbortSignal)=>request<JobEvent[]>('/jobs/'+encodeURIComponent(id)+'/events',{signal});
export const submitJob=(idea:BusinessIdeaInput,projectId='')=>request<PlanJob>('/jobs'+(projectId?'?project_id='+encodeURIComponent(projectId):''),json(idea));
export async function downloadPlan(id:string,format:'pdf'|'docx'|'json'){
 const res=await fetch(base+'/jobs/'+encodeURIComponent(id)+'/export/'+format,{credentials:'include',signal:AbortSignal.timeout(30000)});
 if(!res.ok)throw new Error('Could not export this plan. Please try again.');
 const url=URL.createObjectURL(await res.blob());
 const link=document.createElement('a');link.href=url;link.download='business-plan.'+format;link.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
}
