import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

export default {
 outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),
 async rewrites(){return [{source:'/api/:path*',destination:(process.env.INTERNAL_API_URL || 'http://127.0.0.1:8000')+'/:path*'}]},
};
