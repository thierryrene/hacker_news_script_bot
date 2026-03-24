import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const EVOLUTION_API_URL = process.env.EVOLUTION_API_URL;
const EVOLUTION_API_KEY = process.env.EVOLUTION_API_KEY;
const EVOLUTION_API_INSTANCE = process.env.EVOLUTION_API_INSTANCE;
const WHATSAPP_NUMBER = process.env.WHATSAPP_NUMBER; // Pode ser número ou JID de grupo

// Converte HTML básico (usado no Telegram) para Markdown do WhatsApp com encurtamento de links
async function htmlToWhatsApp(text) {
  if (!text) return '';
  let formatted = String(text)
    .replace(/<b>(.*?)<\/b>/g, '*$1*')
    .replace(/<strong>(.*?)<\/strong>/g, '*$1*')
    .replace(/<i>(.*?)<\/i>/g, '_$1_')
    .replace(/<em>(.*?)<\/em>/g, '_$1_')
    .replace(/<code>(.*?)<\/code>/g, '```$1```');

  const linkRegex = /<a\s+href="([^"]+)">(.*?)<\/a>/g;
  let match;
  const links = [];
  while ((match = linkRegex.exec(formatted)) !== null) {
    links.push({ full: match[0], url: match[1], label: match[2] });
  }

  for (const link of links) {
    try {
      const resp = await axios.get(`https://is.gd/create.php?format=simple&url=${encodeURIComponent(link.url)}`);
      formatted = formatted.replace(link.full, `${link.label}: ${resp.data.trim()}`);
    } catch (err) {
      formatted = formatted.replace(link.full, `${link.label}: ${link.url}`);
    }
  }

  return formatted.replace(/<[^>]*>/g, '');
}

async function sendMessage(text) {
  if (!EVOLUTION_API_URL || !EVOLUTION_API_KEY || !EVOLUTION_API_INSTANCE || !WHATSAPP_NUMBER) {
    console.log('⚠️ Evolution API não configurada corretamente no .env. Ignorando envio WhatsApp.');
    return;
  }

  const url = `${EVOLUTION_API_URL}/message/sendText/${EVOLUTION_API_INSTANCE}`;
  const formattedText = await htmlToWhatsApp(text);

  try {
    console.log(`📤 Enviando mensagem via Evolution API para ${WHATSAPP_NUMBER}...`);
    const response = await axios.post(url, {
      number: WHATSAPP_NUMBER,
      text: formattedText,
      delay: 1200, // Delay de segurança
      linkPreview: false
    }, {
      headers: {
        'apikey': EVOLUTION_API_KEY,
        'Content-Type': 'application/json'
      }
    });

    console.log('✅ Mensagem WhatsApp enviada com sucesso!');
    return response.data;
  } catch (error) {
    console.error('❌ Erro ao enviar mensagem Evolution API:', error.response?.data || error.message);
    // Não lança erro para não quebrar o fluxo principal se o WhatsApp falhar
  }
}

export default {
  sendMessage,
  htmlToWhatsApp
};
