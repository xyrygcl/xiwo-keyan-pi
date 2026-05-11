import { parsePPTX } from 'pptx-parser';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: '仅支持POST请求' });

  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const buffer = Buffer.concat(chunks);
    
    const rawSlides = await parsePPTX(buffer);
    const slides = rawSlides.map(slide => ({
      title: slide.title?.trim() || '无标题',
      bullets: (slide.bullets || []).map(b => b.trim()).filter(b => b),
      paragraphs: (slide.paragraphs || []).map(p => p.trim()).filter(p => p)
    }));

    res.status(200).json({ slides });
  } catch (error) {
    console.error('PPT解析错误:', error);
    res.status(500).json({ error: 'PPT解析失败：' + error.message });
  }
}
