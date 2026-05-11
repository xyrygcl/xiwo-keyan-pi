import { parsePPTX } from 'pptx-parser';
import fs from 'fs';
import os from 'os';
import path from 'path';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: '仅支持POST请求' });
  }

  try {
    // 创建临时文件保存上传的PPT
    const tempDir = os.tmpdir();
    const tempPath = path.join(tempDir, `ppt-${Date.now()}.pptx`);
    
    // 读取请求体
    const chunks = [];
    for await (const chunk of req) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);
    fs.writeFileSync(tempPath, buffer);

    // 解析PPT
    const rawSlides = await parsePPTX(tempPath);
    
    // 转换为和原Python脚本完全兼容的格式
    const slides = rawSlides.map(slide => ({
      title: slide.title?.trim() || '',
      bullets: (slide.bullets || []).map(b => b.trim()).filter(b => b),
      paragraphs: (slide.paragraphs || []).map(p => p.trim()).filter(p => p)
    }));

    // 清理临时文件
    fs.unlinkSync(tempPath);

    res.status(200).json({ slides });
  } catch (error) {
    console.error('PPT解析错误:', error);
    res.status(500).json({ error: 'PPT解析失败，请确保文件是.pptx格式' });
  }
}
