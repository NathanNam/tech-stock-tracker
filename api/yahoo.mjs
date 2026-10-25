// Vercel function: GET /api/yahoo?symbols=AAPL,MSFT&range=1d|5d|1mo|1y
import { handle } from '../lib/yahoo.mjs';

export async function GET(request) {
  const { status, headers, body } = await handle(new URL(request.url).searchParams);
  return Response.json(body, { status, headers });
}
