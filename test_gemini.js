import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';
dotenv.config();

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
  console.error("❌ GEMINI_API_KEY não encontrada!");
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

(async () => {
  try {
    console.log("Teste de Geração com gemini-2.5-flash...");
    const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });
    const result = await model.generateContent("Resuma em uma frase: O céu é azul porque a atmosfera espalha a luz solar.");
    console.log("\n✅ Resposta do Gemini:");
    console.log(result.response.text().trim());
  } catch (err) {
    console.error("\n❌ Erro com gemini-2.5-flash:", err.message);
  }
})();
