import { parsePPTX } from 'pptx-parser';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

export const config = {
  maxDuration: 60 // Vercel免费版最大支持60秒
};

// 直接调用微软官方TTS接口，不需要任何第三方包
async function generateSpeech(text) {
  const endpoint = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1";
  const headers = {
    "Content-Type": "application/ssml+xml",
    "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
  };

  const ssml = `
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
  <voice name="zh-CN-XiaoxiaoNeural">
    <prosody rate="1.0" pitch="1.0">
      ${text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}
    </prosody>
  </voice>
</speak>`;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: headers,
    body: ssml
  });

  if (!response.ok) throw new Error('TTS语音生成失败');
  return Buffer.from(await response.arrayBuffer());
}

export default async function handler(req, res) {
  // CORS跨域设置
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: '仅支持POST请求' });

  try {
    // 1. 接收并解析PPT文件
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const buffer = Buffer.concat(chunks);
    const rawSlides = await parsePPTX(buffer);
    
    const slides = rawSlides.map(slide => ({
      title: slide.title?.trim() || '无标题',
      content: [...(slide.bullets || []), ...(slide.paragraphs || [])]
        .map(t => t.trim()).filter(t => t).join('。')
    }));

    // 2. 初始化FFmpeg
    const ffmpeg = new FFmpeg();
    await ffmpeg.load({
      coreURL: await toBlobURL('https://unpkg.com/@ffmpeg/core@0.12.0/dist/umd/ffmpeg-core.js', 'text/javascript'),
      wasmURL: await toBlobURL('https://unpkg.com/@ffmpeg/core@0.12.0/dist/umd/ffmpeg-core.wasm', 'application/wasm'),
    });

    // 3. 逐页生成语音和视频
    const slideFiles = [];
    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const fullText = `${slide.title}。${slide.content}`;
      
      // 生成语音
      const audioBuffer = await generateSpeech(fullText);
      const audioName = `audio_${i}.mp3`;
      await ffmpeg.writeFile(audioName, new Uint8Array(audioBuffer));

      // 获取语音时长
      const { stdout } = await ffmpeg.exec([
        '-i', audioName, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1'
      ]);
      const duration = parseFloat(stdout) + 0.5;

      // 生成视频画面（极简风格，确保FFmpeg能正常渲染）
      const outputName = `slide_${i}.mp4`;
      await ffmpeg.exec([
        '-f', 'lavfi', `-i`, `color=c=#f5f5f5:s=1920x1080:d=${duration}`,
        '-i', audioName,
        '-vf', `drawtext=text='${slide.title.replace(/'/g, "'\\''")}':fontsize=72:fontcolor=#1a1a1a:x=(w-text_w)/2:y=200:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,
                drawtext=text='${slide.content.substring(0, 200).replace(/'/g, "'\\''")}':fontsize=32:fontcolor=#444444:x=200:y=400:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', outputName
      ]);

      slideFiles.push(outputName);
    }

    // 4. 合并所有视频片段
    const concatContent = slideFiles.map(f => `file '${f}'`).join('\n');
    await ffmpeg.writeFile('concat.txt', concatContent);
    
    await ffmpeg.exec([
      '-f', 'concat', '-safe', '0', '-i', 'concat.txt',
      '-c', 'copy', 'output.mp4'
    ]);

    // 5. 返回最终视频
    const data = await ffmpeg.readFile('output.mp4');
    res.setHeader('Content-Type', 'video/mp4');
    res.setHeader('Content-Length', data.length);
    res.send(Buffer.from(data.buffer));

  } catch (error) {
    console.error('生成错误:', error);
    res.status(500).json({ error: error.message });
  }
}
