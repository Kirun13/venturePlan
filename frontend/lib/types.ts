export interface BusinessIdeaInput { name:string; description:string; region:string; target_audience:string; initial_budget:number; currency:'KZT'|'USD'|'EUR'; unit_price:number; estimated_monthly_units:number }
export interface CostItem {name:string;amount:number}
export interface AppConfig {agent_mode:'mock'|'openai';openai_configured:boolean;web_search_enabled:boolean}
export interface PlanJob {
 project_id:string|null;version:number;
 id:string;status:'queued'|'running'|'completed'|'failed';attempts:number;max_attempts:number;
 agent_mode:string;input_data:BusinessIdeaInput;result_data:BusinessPlan|null;error:string|null;
 created_at:string;started_at:string|null;finished_at:string|null;available_at:string;
}
export interface BusinessPlan {
 idea:BusinessIdeaInput;
 market:{audience:string;demand_summary:string;assumptions:string[];sources:string[];source_details?:ResearchSource[]};
 competitors:{competitors:string[];positioning:string;assumptions:string[];sources:string[];source_details?:ResearchSource[]};
 operations:{launch_steps:string[];startup_costs:CostItem[];monthly_fixed_costs:CostItem[];variable_cost_per_unit:number;staffing:string[];assumptions:string[]};
 finance:{currency:string;monthly_revenue:number;monthly_fixed_costs:number;monthly_variable_costs:number;monthly_profit:number;startup_costs:number;break_even_units:number|null;assumptions:string[];budget_gap?:number;payback_months?:number|null;scenarios?:FinanceScenario[]};
 validation:{risks:string[];warnings:string[];is_consistent:boolean;issues?:string[];revision_required?:boolean};status:'draft';revision_count?:number;
}
export interface User {id:string;email:string}
export interface Project {id:string;name:string;created_at:string}
export interface ResearchSource {url:string;title:string;retrieved_at:string}
export interface FinanceScenario {name:string;monthly_units:number;monthly_revenue:number;monthly_profit:number;payback_months:number|null}
export interface JobEvent {id:number;kind:string;node:string|null;attempt:number|null;details:Record<string,string|number>;message:string;created_at:string}
export const sampleIdea:BusinessIdeaInput={name:'Coffee kiosk',description:'A small takeaway coffee kiosk near an office district, offering affordable specialty coffee and quick service.',region:'Astana, Kazakhstan',target_audience:'Office workers and students aged 18–40',initial_budget:2000000,currency:'KZT',unit_price:1500,estimated_monthly_units:1000};
