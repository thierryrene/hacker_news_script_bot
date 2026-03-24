import axios from 'axios';
import https from 'https';

// Força o uso de IPv4 nas requisições para evitar AggregateError no Node 20+
const agent = new https.Agent({
  family: 4
});

async function sendMessage(token, chatId, text, options = {}) {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  try {
    const response = await axios.post(url, {
      chat_id: chatId,
      text: text,
      parse_mode: options.parse_mode || 'HTML',
      disable_web_page_preview: options.disable_web_page_preview !== undefined ? options.disable_web_page_preview : true
    }, {
      httpsAgent: agent
    });
    return response.data;
  } catch (error) {
    console.error(`❌ Erro Telegram API:`, error.response?.data || error.message);
    throw error;
  }
}

export default {
  sendMessage
};
