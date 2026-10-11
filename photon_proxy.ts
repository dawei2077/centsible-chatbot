import { Spectrum } from 'spectrum-ts';
import { imessage } from 'spectrum-ts/providers/imessage';
import 'dotenv/config';
import http from 'http';
import fs from 'fs';
import path from 'path';

console.log("Loaded Project ID:", process.env.PHOTON_PROJECT_ID ? "Found" : "MISSING!");
console.log("Loaded Project Secret:", process.env.PHOTON_PROJECT_SECRET ? "Found" : "MISSING!");

const UPLOADS_DIR = path.join(__dirname, 'temp_uploads');
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// Memory to store active conversation spaces so we can send outbound/proactive texts!
const activeSpaces = new Map<string, any>();

async function start() {
  console.log("Starting Photon bridge... connecting to iMessage gRPC stream.");

  const app = await Spectrum({
    projectId: process.env.PHOTON_PROJECT_ID || "",
    projectSecret: process.env.PHOTON_PROJECT_SECRET || "",
    providers: [imessage.config()],
  });

  // Start a local HTTP server to receive outbound messages from Python
  http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/send-imessage') {
      let body = '';
      req.on('data', chunk => { body += chunk.toString(); });
      req.on('end', async () => {
        try {
          const payload = JSON.parse(body);
          const cachedSpace = activeSpaces.get(payload.phone_number);
          if (cachedSpace) {
            try {
              await cachedSpace.send(payload.text);
              console.log(`Sent outbound message to ${payload.phone_number}`);
              res.writeHead(200);
              res.end("Message sent");
              return;
            } catch (cacheErr: any) {
              console.warn(`Cached space send failed for ${payload.phone_number}, falling back to dynamic creation:`, cacheErr.message);
              activeSpaces.delete(payload.phone_number);
            }
          }

          // Dynamic space creation: allows the bot to text first even before receiving incoming texts!
          try {
            const imRuntime = (app as any).__internal?.platforms?.get('imessage');
            if (imRuntime) {
              const newSpace = await imRuntime.definition.space.create({
                input: { users: [{ id: payload.phone_number }] },
                client: imRuntime.client
              });
              await imRuntime.definition.send({
                space: newSpace,
                content: { type: 'text', text: payload.text },
                client: imRuntime.client
              });
              // Cache so subsequent sends are immediate
              activeSpaces.set(payload.phone_number, {
                send: async (textMsg: string) => {
                  return imRuntime.definition.send({
                    space: newSpace,
                    content: { type: 'text', text: textMsg },
                    client: imRuntime.client
                  });
                }
              });
              console.log(`Sent first outbound text to ${payload.phone_number} (initiated by bot)`);
              res.writeHead(200);
              res.end("Message sent");
              return;
            }
          } catch (dynErr: any) {
            console.error(`Dynamic space send failed for ${payload.phone_number}:`, dynErr.message);
          }

          console.error(`Cannot send: No space available for ${payload.phone_number}`);
          res.writeHead(404);
          res.end("Space not found");
        } catch (e: any) {
          console.error("Internal proxy error:", e.message);
          res.writeHead(500);
          res.end("Internal Error");
        }
      });
    } else {
      res.writeHead(404);
      res.end("Not Found");
    }
  }).listen(8001, () => {
    console.log("TypeScript Outbound Server listening on port 8001");
  });

  console.log("Photon bridge connected and listening! No ngrok required.");

  for await (const [space, message] of app.messages) {
    // 1. Strictly ignore outbound messages sent by the bot to prevent echo feedback loops
    if (message.direction === 'outbound') {
      continue;
    }

    const senderStr = typeof message.sender === 'object' ? (message.sender as any)?.id : (message.sender ? String(message.sender) : null);
    if (!senderStr || senderStr === 'undefined') {
      continue;
    }

    // Save the space so we can send proactive outbound messages later
    activeSpaces.set(senderStr, space);

    // 2. Extract text and media attachments
    let textContent: string | null = null;
    let mediaBase64: string | null = null;
    let mediaMimeType: string = "image/jpeg";
    let mediaUrl: string | null = null;

    if (typeof (message as any).text === 'string' && (message as any).text.trim()) {
      textContent = (message as any).text.trim();
    }

    const processItem = async (item: any) => {
      if (!item) return;
      if (item.type === 'text' && typeof item.text === 'string') {
        textContent = (textContent ? textContent + ' ' : '') + item.text.trim();
      } else if (item.type === 'markdown' && typeof item.markdown === 'string') {
        textContent = (textContent ? textContent + ' ' : '') + item.markdown.trim();
      } else if (item.type === 'attachment') {
        mediaMimeType = item.mimeType || 'image/jpeg';
        if (typeof item.read === 'function') {
          try {
            const buf = await item.read();
            if (buf && buf.length > 0) {
              const buffer = Buffer.from(buf);
              mediaBase64 = buffer.toString('base64');
              const ext = mediaMimeType.includes('png') ? '.png' : mediaMimeType.includes('pdf') ? '.pdf' : '.jpg';
              const filename = `media_${Date.now()}_${Math.random().toString(36).substring(7)}${ext}`;
              const filePath = path.join(UPLOADS_DIR, filename);
              await fs.promises.writeFile(filePath, buffer);
              mediaUrl = filePath;
              console.log(`Saved attachment to local disk: ${filePath} (${buffer.length} bytes)`);
            }
          } catch (e: any) {
            console.error('Error downloading attachment buffer:', e.message);
          }
        }
      }
    };

    if (message.content) {
      if (message.content.type === 'group' && Array.isArray(message.content.items)) {
        for (const child of message.content.items) {
          await processItem(child.content || child);
        }
      } else {
        await processItem(message.content);
      }
    }

    // Also check raw message.attachments if present
    if (!mediaBase64 && Array.isArray((message as any).attachments) && (message as any).attachments.length > 0) {
      for (const att of (message as any).attachments) {
        await processItem({ type: 'attachment', ...att });
      }
    }

    // 4. Ignore non-message events (read receipts, reactions/tapbacks, typing indicators)
    if (!textContent && !mediaBase64 && !mediaUrl) {
      console.log(`[Proxy] Ignored non-content event (${(message.content as any)?.type || 'event'}) from ${senderStr}`);
      continue;
    }

    console.log(`Received incoming iMessage from ${senderStr}: text="${textContent || ''}" hasMedia=${Boolean(mediaBase64 || mediaUrl)}`);

    try {
      // Forward the payload directly to our local Python FastAPI backend
      const response = await fetch('http://127.0.0.1:8000/imessage-webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number: senderStr,
          text: textContent,
          media_url: mediaUrl,
          media_base64: mediaBase64,
          media_mime_type: mediaMimeType,
          message_id: message.id
        })
      });

      if (response.ok) {
        console.log("Successfully forwarded to local Python backend.");
      } else {
        console.error("Python backend returned an error:", response.statusText);
      }
    } catch (error: any) {
      console.error("Failed to reach Python backend. Is main.py running?", error.message);
    }
  }
}

start();
