import {test,expect} from '@playwright/test';

async function createAccount(page:import('@playwright/test').Page){
 await page.goto('/');
 await page.getByRole('button',{name:'New here? Create an account'}).click();
 await page.getByLabel('Email',{exact:true}).fill('browser-'+Date.now()+'@example.test');
 await page.getByLabel('Password',{exact:true}).fill('browser-test-password-123');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Mock environment')).toBeVisible();
}

test('account, project versions, agent progress, scenarios and exports',async({page})=>{
 const name='Browser project '+Date.now();
 await createAccount(page);
 await page.getByRole('button',{name:'Create a business plan',exact:true}).click();
 await page.getByLabel('Business name').fill(name);
 await page.getByRole('button',{name:'Generate business plan'}).click();
 await expect(page.getByText('Saved to database')).toBeVisible({timeout:20000});
 await expect(page.getByRole('region',{name:'Agent progress'})).toBeVisible();
 await page.getByRole('button',{name:'Finance',exact:true}).click();
 await expect(page.getByRole('cell',{name:'conservative',exact:true})).toBeVisible();
 await expect(page.getByRole('cell',{name:'optimistic',exact:true})).toBeVisible();
 for(const format of ['PDF','DOCX']){
  const pending=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export '+format,exact:true}).click();
  const download=await pending;
  expect(download.suggestedFilename()).toBe('business-plan.'+format.toLowerCase());
  expect(await download.failure()).toBeNull();
 }
 await page.getByRole('button',{name:'Edit and create next version'}).click();
 await page.getByLabel('Price per unit').fill('1700');
 await page.getByRole('button',{name:'Generate business plan'}).click();
 await expect(page.getByText('Saved to database')).toBeVisible({timeout:20000});
 await expect(page.getByText('GENERATED BUSINESS PLAN · VERSION 2')).toBeVisible();
 await page.reload();
 await page.getByRole('button',{name:new RegExp(name)}).first().click();
 await expect(page.getByText('GENERATED BUSINESS PLAN · VERSION 2')).toBeVisible();
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});

test('queued tasks and failures remain understandable after reload',async({page})=>{
 const now=new Date().toISOString();
 const queued={id:'00000000-0000-0000-0000-000000000123',project_id:null,version:1,status:'queued',attempts:1,max_attempts:3,
  agent_mode:'openai',input_data:{name:'Pending task'},result_data:null,
  error:'The AI service is temporarily unavailable.',created_at:now,started_at:now,finished_at:null,available_at:now};
 let status='queued';
 await page.route('**/auth/me',route=>route.fulfill({json:{id:'test-user',email:'test@example.test'}}));
 await page.route('**/config',route=>route.fulfill({json:{agent_mode:'openai',openai_configured:true,web_search_enabled:true}}));
 await page.route('**/projects',route=>route.fulfill({json:[]}));
 await page.route('**/jobs?*',route=>route.fulfill({json:[{...queued,status}]}));
 await page.route('**/jobs/'+queued.id,route=>route.fulfill({json:{...queued,status}}));
 await page.route('**/jobs/'+queued.id+'/events',route=>route.fulfill({json:[]}));
 await page.goto('/');
 await expect(page.getByText('OpenAI environment')).toBeVisible();
 await page.getByRole('button',{name:/Pending task/}).click();
 await expect(page.getByText('Attempt 1 of 3',{exact:true})).toBeVisible();
 await page.reload();
 await page.getByRole('button',{name:'Selected task',exact:true}).click();
 await expect(page.getByText('Attempt 1 of 3',{exact:true})).toBeVisible();
 status='failed';
 await expect(page.getByText('Generation failed',{exact:true})).toBeVisible({timeout:10000});
 await expect(page.getByRole('button',{name:'Review inputs and try again'})).toBeVisible();
});
