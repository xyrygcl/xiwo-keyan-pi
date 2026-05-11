import { Communicate } from 'edge-tts';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: '仅支持POST请求' });
  }

  try {
    const { text } = req.body;
    if (!text || text.trim() === '') {
      return res.status(400).json({ error: '文本不能为空' });
    }

    // 生成语音（和原Python版使用完全相同的微软语音服务）
    const communicate = new Communicate(text, 'zh-CN-XiaoxiaoNeural', {
      rate: '1.0',
      volume: '1.0'
    });

    const chunks = [];
    for await (const chunk of communicate.stream()) {
      if (chunk.type === 'audio') {
        chunks.push(chunk.data);
      }
    }

    const audioBuffer = Buffer.concat(chunks);
    
    // 返回MP3音频
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Content-Length', audioBuffer.length);
    res.send(audioBuffer);
  } catch (error) {
    console.error('TTS生成错误:', error);
    res.status(500).json({ error: '语音生成失败' });
  }
}
