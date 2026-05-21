import axios from 'axios';
import dotenv from 'dotenv';
import { GoogleGenerativeAI } from '@google/generative-ai';
import evolution from './evolution.js';
import telegram from './telegram.js';
import * as cheerio from 'cheerio';
import fs from 'fs';
import path from 'path';
import { initDb, getHash, getPostSummary, savePostSummary, getCommentSummary, saveCommentSummary } from './cache.js';

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

async function fetchTopComments(kids) {
  if (!kids || !Array.isArray(kids)) return '';
  const firstKids = kids.slice(0, 5);
  try {
    const promises = firstKids.map(id => 
      axios.get(`https://hacker-news.firebaseio.com/v0/item/${id}.json`).then(r => r.data).catch(() => null)
    );
    const comments = await Promise.all(promises);
    return comments.filter(c => c && c.text && !c.deleted && !c.dead)
      .map(c => c.text.replace(/<[^>]*>?/gm, ' ').substring(0, 400))
      .join(' | ');
  } catch(e) {
    return '';
  }
}

async function summarizeCommentsWithGemini(postsWithComments) {
  try {
    const modelName = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
    const model = genAI.getGenerativeModel({
      model: modelName,
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema: {
          type: "array",
          description: "Lista de resumos de opiniões da comunidade para cada post enviado, respeitando a ordem exata dos posts.",
          items: {
            type: "string",
            description: "1 a 2 frases em português resumindo a voz da comunidade do Hacker News sobre o post (divergências, elogios, discussões ou piadas). Sem formatação HTML."
          }
        }
      }
    });
    
    let prompt = `Você é um analista de comunidade discutindo links de tecnologia.
Abaixo estão os títulos dos posts e as opiniões mais relevantes da comunidade do Hacker News sobre eles.
Para cada post, gere um resumo conciso (1 a 2 frases) da voz da comunidade.

Posts:\n`;

    postsWithComments.forEach((post, index) => {
      prompt += `\n[Post ${index + 1}]
Título: ${post.title}
Comentários Brutos: ${post.rawComments || 'Sem comentários.'}\n`;
    });

    const result = await model.generateContent(prompt);
    const text = result.response.text().trim();
    return JSON.parse(text);
  } catch(e) {
    console.error("❌ Erro no resumo de comentários:", e.message);
    return [];
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
    const model = genAI.getGenerativeModel({
      model: modelName,
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema: {
          type: "array",
          description: "Lista de resumos e análises estruturadas para cada post enviado, mantendo a exata ordem dos posts.",
          items: {
            type: "object",
            properties: {
              emoji: {
                type: "string",
                description: "Um único emoji que represente visualmente a temática do post."
              },
              tldr: {
                type: "string",
                description: "1 a 2 frases em português resumindo a ideia central da notícia de forma rica e informativa."
              },
              porQueImporta: {
                type: "string",
                description: "1 a 2 frases em português explicando o impacto prático direto, consequência futura ou ação necessária para desenvolvedores e profissionais de tecnologia."
              },
              tags: {
                type: "array",
                description: "2 a 3 hashtags concisas em português e minúsculas categorizando o post (ex: #ia, #seguranca, #hardware).",
                items: {
                  type: "string"
                }
              }
            },
            required: ["emoji", "tldr", "porQueImporta", "tags"]
          }
        }
      }
    });

    let prompt = `Você é um sumarizador especialista de notícias tech. Recebi posts do Hacker News com o título e um trecho do seu conteúdo original.
Faça um resumo rico, denso e estruturado em português para cada um deles.

Posts:\n`;

    posts.forEach((post, index) => {
      prompt += `\n[Post ${index + 1}]
Título: ${post.title}
URL: ${post.url || 'N/A'}
Conteúdo extraído: ${post.fetchedText || post.text || 'Apenas o título está disponível.'}\n`;
    });

    const result = await model.generateContent(prompt);
    const text = result.response.text().trim();
    return JSON.parse(text);
  } catch (err) {
    console.error(`❌ Erro no Gemini ao resumir os posts:`, err.message);
    return [];
  }
}

(async () => {
  await initDb();
  console.log("📊 Buscando melhores posts do Hacker News...");
  const posts = await getHackerNewsTop();

  if (posts.length === 0) {
    console.log("Nenhum post recente com score > 50 encontrado.");
    return;
  }

  console.log(`📝 Extraindo conteúdo de ${posts.length} links concorrentemente...`);
  const scrapePromises = posts.map(async (post) => {
    if (post.url && !post.url.includes('news.ycombinator.com/item')) {
      console.log(`- Lendo: ${post.title}`);
      post.fetchedText = await fetchLinkContent(post.url);
    }
  });
  await Promise.all(scrapePromises);

  console.log("🗣️ Extraindo comentários top concorrentemente...");
  const commentPromises = posts.map(async (post) => {
    post.rawComments = await fetchTopComments(post.kids);
  });
  await Promise.all(commentPromises);
  
  console.log("💭 Resumindo opiniões da comunidade com Gemini (JSON)...");
  const commentSummaries = [];
  const uncachedCommentPosts = [];
  const commentCachedIndexes = [];

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i];
    const commentsHash = getHash(post.rawComments);
    const cachedSummary = await getCommentSummary(post.id, commentsHash);
    if (cachedSummary) {
      console.log(`- [Cache Hit] Comentários do Post ${post.id} carregados do SQLite`);
      commentSummaries[i] = cachedSummary;
    } else {
      commentSummaries[i] = null;
      uncachedCommentPosts.push(post);
      commentCachedIndexes.push(i);
    }
  }

  if (uncachedCommentPosts.length > 0) {
    console.log(`- Chamando Gemini para resumir comentários de ${uncachedCommentPosts.length} posts...`);
    const newCommentSummaries = await summarizeCommentsWithGemini(uncachedCommentPosts);
    const hasValidResults = newCommentSummaries && newCommentSummaries.length > 0;
    
    for (let j = 0; j < uncachedCommentPosts.length; j++) {
      const post = uncachedCommentPosts[j];
      const originalIndex = commentCachedIndexes[j];
      const summaryText = hasValidResults ? (newCommentSummaries[j] || "") : "";
      commentSummaries[originalIndex] = summaryText;

      // Apenas salva no cache se tivemos uma resposta válida da API
      if (hasValidResults && summaryText) {
        const commentsHash = getHash(post.rawComments);
        await saveCommentSummary(post.id, commentsHash, summaryText);
      }
    }
  }

  console.log(`📝 Enviando para resumo estruturado em lote no Gemini (JSON)...`);
  const summaries = [];
  const uncachedPosts = [];
  const postCachedIndexes = [];

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i];
    const textHash = getHash(post.fetchedText || post.title);
    const cachedSummary = await getPostSummary(post.id, textHash);
    if (cachedSummary) {
      console.log(`- [Cache Hit] Resumo do Post ${post.id} carregados do SQLite`);
      summaries[i] = cachedSummary;
    } else {
      summaries[i] = null;
      uncachedPosts.push(post);
      postCachedIndexes.push(i);
    }
  }

  if (uncachedPosts.length > 0) {
    console.log(`- Chamando Gemini para resumir ${uncachedPosts.length} posts...`);
    const newSummaries = await summarizeAllWithGemini(uncachedPosts);
    const hasValidResults = newSummaries && newSummaries.length > 0;

    for (let j = 0; j < uncachedPosts.length; j++) {
      const post = uncachedPosts[j];
      const originalIndex = postCachedIndexes[j];
      
      if (hasValidResults && newSummaries[j]) {
        const summaryObj = newSummaries[j];
        summaries[originalIndex] = summaryObj;
        
        // Apenas salva no cache se não for o fallback de erro
        if (summaryObj.tldr && summaryObj.tldr !== "Não foi possível gerar um resumo detalhado.") {
          const textHash = getHash(post.fetchedText || post.title);
          await savePostSummary(post.id, post.title, post.url || '', textHash, summaryObj);
        }
      } else {
        // Fallback temporário (não cacheado)
        summaries[originalIndex] = { 
          emoji: "📰", 
          tldr: "Não foi possível gerar um resumo detalhado.", 
          porQueImporta: "", 
          tags: [] 
        };
      }
    }
  }

  let fullMsg = `<b>📰 HACKER NEWS - TOP STORIES 🚀</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
  const exportedArray = [];

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i];
    const summary = summaries[i] || { emoji: "📰", tldr: "Não foi possível gerar um resumo detalhado.", porQueImporta: "", tags: [] };
    
    const emojiStr = summary.emoji || "📰";
    const tldrStr = summary.tldr || "";
    const whyItMattersStr = summary.porQueImporta || "";
    const tagsArray = summary.tags || [];
    const tagsStr = tagsArray.map(t => t.startsWith('#') ? t.toLowerCase() : `#${t.toLowerCase()}`).join(' ');

    const cleanComm = (commentSummaries[i] || "").trim();

    // Read time estimation (~200 words per minute)
    const wordCount = post.fetchedText ? post.fetchedText.trim().split(/\s+/).length : 0;
    const readTime = post.fetchedText ? Math.max(1, Math.round(wordCount / 200)) : 0;

    // Type Prefix Identification
    let typePrefix = '';
    const titleUpper = post.title.toUpperCase();
    if (titleUpper.startsWith('SHOW HN:')) {
      typePrefix = '🛠️ [SHOW HN] ';
    } else if (titleUpper.startsWith('ASK HN:')) {
      typePrefix = '❓ [ASK HN] ';
    } else if (post.url && post.url.toLowerCase().endsWith('.pdf')) {
      typePrefix = '📄 [PDF] ';
    } else if (!post.url || post.url.includes('news.ycombinator.com/item')) {
      typePrefix = '💬 [DISCUSSÃO] ';
    }

    const cleanTitle = post.title.replace(/^(SHOW HN:|ASK HN:)\s*/i, '').trim();

    exportedArray.push({
      id: post.id,
      title: cleanTitle,
      type_prefix: typePrefix,
      score: post.score,
      url: post.url || `https://news.ycombinator.com/item?id=${post.id}`,
      hn_url: `https://news.ycombinator.com/item?id=${post.id}`,
      emoji: emojiStr,
      tldr: tldrStr,
      porQueImporta: whyItMattersStr,
      read_time: readTime,
      tags: tagsStr,
      community: cleanComm
    });

    // Feedback visual baseado no score
    let badge = '📌';
    if (post.score >= 300) badge = '👑';
    else if (post.score >= 120) badge = '🔥';
    else if (post.score >= 80) badge = '📈';

    const formattedTitle = typePrefix ? `${typePrefix}${cleanTitle.toUpperCase()}` : cleanTitle.toUpperCase();

    fullMsg += `${badge} <b>${formattedTitle}</b> (${post.score} pts)\n`;
    const accessUrl = post.url || `https://news.ycombinator.com/item?id=${post.id}`;
    let metaLine = `  🔗 <a href="${accessUrl}">Notícia</a> | 💬 <a href="https://news.ycombinator.com/item?id=${post.id}">Discussão</a>`;
    if (readTime > 0) {
      metaLine += ` | ⏱️ ${readTime} min`;
    }
    fullMsg += `${metaLine}\n`;
    fullMsg += `  ${emojiStr} <b>TL;DR:</b> ${tldrStr.trim()}\n`;
    if (whyItMattersStr) {
      fullMsg += `  💡 <b>Por Que Importa:</b> ${whyItMattersStr.trim()}\n`;
    }
    if (cleanComm) {
      fullMsg += `  🗣️ <b>Comunidade:</b> ${cleanComm}\n`;
    }
    if (tagsStr) {
      fullMsg += `  🏷️ <i>${tagsStr}</i>\n`;
    }
    fullMsg += `\n===POST_SEPARATOR===\n\n`;
  }

  if (TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID) {
    const blocks = fullMsg.split('===POST_SEPARATOR===');
    let currentChunk = '';
    const chunks = [];

    for (const block of blocks) {
      const cleanBlock = block.trim();
      if (!cleanBlock) continue;

      // Limite do Telegram é 4096. Usamos 3900 como margem segura incluindo o divisor.
      if (currentChunk.length + cleanBlock.length + 25 > 3900) {
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
        const resp = await telegram.sendMessage(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, chunk, {
          parse_mode: 'HTML',
          disable_web_page_preview: true
        });
        console.log(`[DEBUG] Resposta API Telegram: ok=${resp.ok}, msg_id=${resp.result?.message_id}`);
      } catch (err) {
        console.error('❌ Erro envio Telegram:', err.message);
      }
      await new Promise(resolve => setTimeout(resolve, 500)); // Flood limit delay
    }
    console.log("✅ Resumo enviado para o Telegram!");
  }

  // Montagem da mensagem limpa para WhatsApp (sem o separador interno)
  const whatsAppMsg = fullMsg.split('===POST_SEPARATOR===').join('').trim();
  await evolution.sendMessage(whatsAppMsg);
  console.log("✅ Resumo enviado para o WhatsApp!");

  // Salvar Dump JSON Local
  const dataDir = path.resolve('./data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  const digestPayload = {
    updated_at: new Date().toISOString(),
    posts: exportedArray
  };
  fs.writeFileSync(path.join(dataDir, 'latest.json'), JSON.stringify(digestPayload, null, 2));
  console.log("✅ Dump JSON estático atualizado em /data/latest.json!");

})();
