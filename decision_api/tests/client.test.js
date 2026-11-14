import test from 'node:test';
import assert from 'node:assert/strict';
import {createDecisionClient, DecisionAPIError} from '../client.js';

const id = 'a'.repeat(32);
function mockClient(response = {ok:true,status:200,json:async()=>({id})}) {
  const calls = [];
  const client = createDecisionClient({fetch:async(...args)=>{calls.push(args);return response;}});
  return {client,calls};
}
test('construction, metadata and saved examples never call live routes', async()=>{
  const {client,calls} = mockClient();
  assert.equal(calls.length,0);
  await client.examples();await client.precomputed('example-1');
  assert.deepEqual(calls.map(c=>c[0]),['/api/decision/examples','/api/decision/examples/example-1/decision']);
});
test('score retains stable IDs and only sends explicit input',async()=>{
  const {client,calls}=mockClient();
  const input={context:'Visible information',questions:[{id:'node',text:'Next?',choices:[{id:'wait',text:'Review'},{id:'ask',text:'Ask for information'}]}]};
  await client.score(input);
  assert.deepEqual(JSON.parse(calls[0][1].body),input);
  assert.equal(calls[0][0],'/api/decision/score');
  assert.equal(calls[0][1].headers.Authorization,undefined);
});
test('reviews use a separate endpoint and original question/action IDs',async()=>{
  const {client,calls}=mockClient();
  const review={question_id:'q',action_id:'action-2',reviewer:'Demo'};
  await client.review(id,review);
  assert.equal(calls[0][0],`/api/decision/decisions/${id}/review`);
  assert.deepEqual(JSON.parse(calls[0][1].body),review);
});
test('invalid identifiers never make a network request',()=>{
  const {client,calls}=mockClient();
  assert.throws(()=>client.decision('../secret'),TypeError);
  assert.throws(()=>client.scoreExample('../other'),TypeError);
  assert.throws(()=>client.precomputed('not-a-bundled-example'),TypeError);
  assert.equal(calls.length,0);
});
test('startup failure is an error, never an automatic replay or retry',async()=>{
  const {client,calls}=mockClient({ok:false,status:503,json:async()=>({detail:'Model starting'})});
  await assert.rejects(client.score({}),error=>error instanceof DecisionAPIError&&error.retryable&&error.status===503);
  assert.equal(calls.length,1);
});
test('non-JSON upstream errors stay readable',async()=>{
  const {client}=mockClient({ok:false,status:502,json:async()=>{throw new Error('HTML');}});
  await assert.rejects(client.health(),error=>error.status===502&&error.retryable);
});
test('timeout aborts instead of leaving an indefinitely pending call',async()=>{
  const client=createDecisionClient({timeoutMs:10,fetch:async(url,{signal})=>new Promise((resolve,reject)=>{
    signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true});
  })});
  await assert.rejects(client.health(),error=>error instanceof DecisionAPIError&&error.retryable);
});
test('reasoning settings are explicit, bounded data sent on a separate route',async()=>{
  const {client,calls}=mockClient();
  const payload={example_id:'pathway',reasoning:{enabled:true,max_tokens:128,additional_prompt:'Give a quick review'}};
  await client.reason(payload);
  assert.equal(calls[0][0],'/api/decision/reason');
  assert.deepEqual(JSON.parse(calls[0][1].body),payload);
  assert.equal(calls.length,1);
});
test('tool preview is separate from scoring and has no implicit model call',async()=>{
  const {client,calls}=mockClient();
  await client.refinePreview({example_id:'pathway',reasoning:{enabled:true,max_tokens:64}});
  assert.deepEqual(calls.map(c=>c[0]),['/api/decision/refine-preview']);
});
