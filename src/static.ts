import express, { Router } from 'express';
import path from 'path';

export function mountStatic(app: express.Express) {
  const router = Router();
  const publicDir = path.join(process.cwd(), 'public');
  router.use('/', express.static(publicDir));
  app.use('/', router);
}


