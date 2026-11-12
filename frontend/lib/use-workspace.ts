'use client';
import {useCallback,useEffect,useState} from 'react';
import {ApiError,getConfig,getJob,getEvents,listJobs,listProjects,submitJob} from './api';
import type {AppConfig,BusinessIdeaInput,PlanJob,Project,JobEvent} from './types';

export function useWorkspace(userId:string){
 const key='ventureplan.selected-job.'+userId;
 const [jobs,setJobs]=useState<PlanJob[]>([]);
 const [projects,setProjects]=useState<Project[]>([]);
 const [events,setEvents]=useState<JobEvent[]>([]);
 const [selected,setSelected]=useState<PlanJob|null>(null);
 const [selectedId,setSelectedId]=useState<string|null>(null);
 const [config,setConfig]=useState<AppConfig|null>(null);
 const [error,setError]=useState('');
 const [unauthorized,setUnauthorized]=useState(false);
 const [loading,setLoading]=useState(true);
 const [restored,setRestored]=useState(false);
 const [offset,setOffset]=useState(0);
 const [projectFilter,setFilter]=useState('');
 useEffect(()=>{
  try{setSelectedId(localStorage.getItem(key))}catch{}
  setRestored(true);
 },[key]);
 const selectJob=useCallback((job:PlanJob)=>{
  setSelected(job);setSelectedId(job.id);setEvents([]);
  try{localStorage.setItem(key,job.id)}catch{}
 },[key]);
 const setProjectFilter=(id:string)=>{setOffset(0);setFilter(id)};
 useEffect(()=>{
  if(!restored)return;
  let disposed=false;const controller=new AbortController();
  let timer:ReturnType<typeof setTimeout>;
  async function refresh(){
   try{
    const [history,currentConfig,allProjects,current]=await Promise.all([
     listJobs(offset,projectFilter,controller.signal),getConfig(controller.signal),listProjects(controller.signal),
     selectedId?getJob(selectedId,controller.signal).catch(err=>{
      if(err instanceof ApiError&&err.status===404)return null;throw err;
     }):Promise.resolve(null)
    ]);
    const timeline=current?await getEvents(current.id,controller.signal):[];
    if(disposed)return;
    setJobs(history);setConfig(currentConfig);setProjects(allProjects);setSelected(current);setEvents(timeline);setError('');
   }catch(err){
    if(!disposed){
     if(err instanceof ApiError&&err.status===401)setUnauthorized(true);
     else setError(err instanceof Error?err.message:'Could not load the workspace');
    }
   }finally{
    if(!disposed){setLoading(false);timer=setTimeout(refresh,2000)}
   }
  }
  void refresh();
  return ()=>{disposed=true;controller.abort();clearTimeout(timer)};
 },[restored,selectedId,offset,projectFilter]);
 const createJob=useCallback(async(idea:BusinessIdeaInput,projectId='')=>{
  const job=await submitJob(idea,projectId);
  setJobs(items=>[job,...items.filter(item=>item.id!==job.id)].slice(0,20));
  selectJob(job);return job;
 },[selectJob]);
 return {jobs,projects,events,selected,config,error,loading,unauthorized,selectJob,createJob,
  offset,setOffset,projectFilter,setProjectFilter};
}
