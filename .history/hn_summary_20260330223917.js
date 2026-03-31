import axios from 'axios';
import dotenv from 'dotenv';
import { GoogleGenerativeAI } from '@google/generative-ai';
import evolution from './evolution.js';
import telegram from './telegram.js';
import * as cheerio from 'cheerio';

// Corrigir erro AggregateError no Node 20+ (preferir IPv4)
import dns from 'node:dns';
if (dns.setDefaultResultOrder) {
  dns.setDefaultResultOrder('ipv4first');
}

dotenv.config({ override: true });

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';

if (!GEMINI_API_KEY) {
  console.error("❌ Erro: GEMINI_API_KEY não encontrada no arquivo .env");
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

async function fetchLinkContent(url) {
  if (!url) return '';
  try {
    const res = await axios.get(url, {
      timeout: 5000,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    });
    const $ = cheerio.load(res.data);
    $('script, style, iframe, nav, header, footer').remove();
    const text = $('p').map((i, el) => $(el).text()).get().join(' ');
    // Fallback se não houver tag p
    if (!text.trim()) return $('body').text().substring(0, 1500).replace(/\s+/g, ' ');
    return text.substring(0, 1500).replace(/\s+/g, ' ');
  } catch (err) {
    return '';
  }
}

async function getHackerNewsTop() {
  try {
    // Busca os Top Stories (IDs)
    const res = await axios.get('https://hacker-news.firebaseio.com/v0/topstories.json');
    const ids = res.data.slice(0, 60); // Avalia os 60 primeiros
    
    // Busca os detalhes de todos os posts concorrentemente (Muito mais rápido!)
    const itemPromises = ids.map(id => 
      axios.get(`https://hacker-news.firebaseio.com/v0/item/${id}.json`)
        .then(r => r.data)
        .catch(() => null) // Garante resiliência contra falhas de rede individuais
    );
    const rawItems = await Promise.all(itemPromises);

    // Filtra itens válidos e com pontuação superior a 50
    const items = rawItems.filter(item => item && item.score > 50 && item.title);

    // Ordena pela pontuação (score) do maior para o menor
    items.sort((a, b) => b.score - a.score);

    // Retorna apenas os 15 melhores
    return items.slice(0, 15);
  } catch (err) {
    console.error("Erro ao carregar Hacker News:", err.message);
    return [];
  }
}

async function summarizeAllWithGemini(posts) {
  try {
    const modelName = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
    const model = genAI.getGenerativeModel({ model: modelName });

    let prompt = `Você é um sumarizador especialista de notícias tech. Recebi posts do Hacker News com o título e um trecho do seu conteúdo original. 
Faça um resumo rico e estruturado em português para cada um deles.

Sua resposta DEVE conter EXATAMENTE uma linha por post (sem quebras de linha no meio de um post), no formato abaixo:
1. [Emoji] <b>TL;DR:</b> [1 a 2 frases com a ideia central] 💡 <b>Insight:</b> [1 a 2 frases com a consequência ou ação] 🏷️ [2 a 3 hashtags curtas, ex: #AI #Dev]
2. [Emoji] <b>TL;DR:</b> ...

Lembre-se: NÃO use quebras de linha (\\n) dentro do resumo de um mesmo post. Apenas 1 linha de retorno para cada post enviado. Especialmente o formato deve manter as tags HTML corretas "<b>TL;DR:</b>".

Posts:\n`;

    posts.forEach((post, index) => {
      prompt += `\n[Post ${index + 1}]
Título: ${post.title}
URL: ${post.url || 'N/A'}
Conteúdo extraído: ${post.fetchedText || post.text || 'Apenas o título está disponível.'}\n`;
    });

    const result = await model.generateContent(prompt);
    const responseText = result.response.text().trim();
    
    const summaries = responseText.split('\n')
      .map(l => l.replace(/^\d+[\.\)]\s*/, '').trim())
      .filter(l => l.length > 5);

    return summaries;
  } catch (err) {
    console.error(`❌ Erro no Gemini ao resumir os posts:`, err.message);
    return [];
  }
}

(async () => {
  console.log("📊 Buscando melhores posts do Hacker News...");
  const posts = await getHackerNewsTop();

  if (posts.length === 0) {
    console.log("Nenhum post recente com score > 50 encontrado.");
    return;
  }

  console.log(`📝 Extraindo conteúdo de ${posts.length} links...`);
  for (const post of posts) {
    if (post.url && !post.url.includes('news.ycombinator.com/item')) {
      console.log(`- Lendo: ${post.title}`);
      post.fetchedText = await fetchLinkContent(post.url);
    }
  }

  console.log(`📝 Enviando para resumo em lote no Gemini...`);
  const summaries = await summarizeAllWithGemini(posts);

  let fullMsg = `<b>📰 HACKER NEWS - TOP STORIES 🚀</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i];
    const summary = summaries[i] || "Não foi possível gerar um resumo detalhado.";
    
    // Feedback visual baseado no score
    let badge = '📌';
    if (post.score >= 300) badge = '👑 Destaque:';
    else if (post.score >= 120) badge = '🔥 Quente:';
    else if (post.score >= 80) badge = '📈 Relevante:';

    fullMsg += `${badge} <b>${post.title}</b> (${post.score} pts)\n`;
    if (post.url) fullMsg += `  🔗 <a href="${post.url}">Acessar link</a>\n`;
    fullMsg += `  � <a href="https://news.ycombinator.com/item?id=${post.id}">Discussão (HN)</a>\n`;
    fullMsg += `  📝 ${summary.trim()}\n\n===POST_SEPARATOR===\n\n`;
  }

  if (TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID) {
    const blocks = fullMsg.split('===POST_SEPARATOR===');
    let currentChunk = '';
    const chunks = [];

    for (const block of blocks) {
      const cleanBlock = block.trim();
      if (!cleanBlock) continue;

      if (currentChunk.length + cleanBlock.length + 2 > 3900) {
        chunks.push(currentChunk);
        currentChunk = cleanBlock;
      } else {
        currentChunk += (currentChunk ? '\n\n' : '') + cleanBlock;
      }
    }
    if (currentChunk) chunks.push(currentChunk);

    console.log(`[DEBUG] Quantidade de chunks a enviar: ${chunks.length}`);

    for (const chunk of chunks) {
      console.log(`[DEBUG] Tamanho do chunk atual: ${chunk.length} caracteres`);
      try {
        await telegram.sendMessage(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, chunk, {
          parse_mode: 'HTML',
          disable_web_page_preview: true
        });
      } catch (err) {
        console.error('❌ Erro envio Telegram:', err.message);
      }
      await new Promise(resolve => setTimeout(resolve, 500)); // Flood limit delay
    }
    console.log("✅ Resumo enviado para o Telegram!");
  }

  const whatsAppMsg = fullMsg.split('===POST_SEPARATOR===').join('').trim();
  await evolution.sendMessage(whatsAppMsg);
  console.log("✅ Resumo enviado para o WhatsApp!");

})();
