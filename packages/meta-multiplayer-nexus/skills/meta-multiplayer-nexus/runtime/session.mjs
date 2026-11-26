import {createTransport} from './transport.mjs';
import {createServerTransport} from './colyseus-transport.mjs';
import {createLocalPhysics} from './physics.mjs';
// Optional P2P controller replaces (never duplicates) existing local movement.
export async function createSession({mode,localPhysics,...options}){
 if(mode==='server'){if(localPhysics)throw Error('Server owns physics; prediction requires explicit reconciliation');return createServerTransport(options);}
 if(mode!=='p2p')throw Error('Select p2p or server');
 if(!localPhysics)return createTransport(options);
 const {R,...config}=localPhysics;await R.init();const sim=createLocalPhysics(R,config);
 try{const transport=createTransport({...options,sample:sim.sample});return {...transport,advancePhysics:sim.advance,sampleLocal:sim.sample,async leave(){try{await transport.leave();}finally{sim.dispose();}}};}catch(e){sim.dispose();throw e;}
}
