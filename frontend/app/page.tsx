'use client';
import {useCallback,useEffect,useState} from 'react';
import {ApiError,getMe,signIn,signOut} from '@/lib/api';
import type {User} from '@/lib/types';
import Workspace from './workspace';

export default function Home(){
 const [user,setUser]=useState<User|null>(null);
 const [loading,setLoading]=useState(true);
 const [register,setRegister]=useState(false);
 const [email,setEmail]=useState('');const [password,setPassword]=useState('');
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 useEffect(()=>{getMe().then(setUser).catch(err=>{
  if(!(err instanceof ApiError&&err.status===401))setError('Could not connect to the server. Refresh to retry.');
 }).finally(()=>setLoading(false))},[]);
 const logout=useCallback(async()=>{
  try{await signOut();setUser(null);setPassword('')}catch{setError('Could not sign out. Please retry.')}
 },[]);
 async function submit(e:React.FormEvent){
  e.preventDefault();setBusy(true);setError('');
  try{setUser(await signIn(email,password,register));setPassword('')}
  catch(err){setError(err instanceof Error?err.message:'Sign-in failed')}finally{setBusy(false)}
 }
 if(loading)return <div className="auth-shell">Loading workspace…</div>;
 if(user)return <><Workspace key={user.id} user={user} onLogout={logout}/>{error&&<div className="error-banner" role="alert">{error}</div>}</>;
 return <main className="auth-shell"><form className="auth-card" onSubmit={submit}>
  <div className="eyebrow">VENTUREPLAN</div><h1>{register?'Create your account':'Welcome back'}</h1>
  <p>Your business projects, research and plan versions in one workspace.</p>
  <label className="field"><span className="field-label">Email</span><input required type="email" maxLength={254} autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)}/></label>
  <label className="field"><span className="field-label">Password</span><input required aria-label="Password" aria-describedby="password-help" type="password" minLength={12} maxLength={128} autoComplete={register?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)}/><small id="password-help">At least 12 characters</small></label>
  {error&&<div className="error-banner" role="alert">{error}</div>}
  <button className="primary-btn" disabled={busy} type="submit">{busy?'Please wait…':register?'Create account':'Sign in'}</button>
  <button className="ghost-btn auth-switch" type="button" onClick={()=>{setRegister(!register);setError('')}}>{register?'Already registered? Sign in':'New here? Create an account'}</button>
 </form></main>;
}
