'use client';
import type {BusinessPlan,JobEvent,PlanJob} from '@/lib/types';

const labels:Record<string,string>={coordinator:'Coordinator',market:'Market research',competitors:'Competitor analysis',
 operations:'Operations planning',finance:'Financial model',validation:'Risk review',revision:'Revision',assemble:'Plan assembly'};

export function TaskProgress({job,events}:{job:PlanJob;events:JobEvent[]}){
 const current=events.filter(event=>event.attempt===job.attempts);
 const nodes=Object.keys(labels).filter(name=>name!=='revision'||current.some(event=>event.node===name));
 const usage=events.filter(event=>event.kind==='usage');
 const tokens=usage.reduce((sum,event)=>sum+Number(event.details.total_tokens||0),0);
 return <section className="progress-panel" aria-label="Agent progress"><h2>Agent progress</h2>
 <div className="progress-grid">{nodes.map(name=>{
  const timeline=current.filter(event=>event.node===name&&event.kind.startsWith('node_'));
  const last=timeline[timeline.length-1];
  const status=last?.kind==='node_completed'?'Completed':last?.kind==='node_failed'?'Failed':
   last?.kind==='node_started'?(job.status==='running'?'Running':'Interrupted'):'Pending';
  return <div className={'progress-node '+status.toLowerCase()} key={name}><strong>{labels[name]}</strong><span>{status}</span>{last?.details.duration_ms!==undefined&&<small>{(Number(last.details.duration_ms)/1000).toFixed(2)}s</small>}</div>;
 })}</div><p className="progress-meta">Attempt {job.attempts} of {job.max_attempts} · {tokens.toLocaleString()} provider tokens across all attempts
 {usage.length>0&&' · '+Array.from(new Set(usage.map(event=>event.details.model))).join(', ')}</p></section>;
}

export function Sources({result}:{result:BusinessPlan['market']|BusinessPlan['competitors']}){
 const safe=result.sources.filter(url=>url.startsWith('https://')||url.startsWith('http://'));
 return <div className="sources"><h3>Evidence</h3><p>Findings are assumptions unless supported by the cited material. Provider citations do not independently verify every claim.</p>
 {safe.length?<ul>{safe.map(url=>{
  const detail=result.source_details?.find(source=>source.url===url);
  return <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">{detail?.title||url}</a>{detail&&<small>Retrieved {new Date(detail.retrieved_at).toLocaleString()}</small>}</li>;
 })}</ul>:<p>No provider-cited sources. Treat these findings as unverified.</p>}</div>;
}

export function Scenarios({plan}:{plan:BusinessPlan}){
 return <><h3>Budget and payback</h3><p>Budget gap: {(plan.finance.budget_gap??0).toLocaleString()} {plan.idea.currency} · Payback: {plan.finance.payback_months==null?'Unavailable':plan.finance.payback_months+' months'}</p>
 {!!plan.finance.scenarios?.length&&<div className="table-scroll"><table className="scenario-table"><caption>Sales scenarios in {plan.idea.currency}</caption><thead><tr><th>Scenario</th><th>Units</th><th>Revenue</th><th>Profit</th><th>Payback months</th></tr></thead><tbody>{plan.finance.scenarios.map(s=><tr key={s.name}><td>{s.name}</td><td>{s.monthly_units}</td><td>{s.monthly_revenue.toLocaleString()}</td><td>{s.monthly_profit.toLocaleString()}</td><td>{s.payback_months??'Unavailable'}</td></tr>)}</tbody></table></div>}</>;
}
