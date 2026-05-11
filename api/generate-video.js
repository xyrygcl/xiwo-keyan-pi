import { parsePPTX } from 'pptx-parser';
import * as edgeTts from 'edge-tts';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

export const config = {
  maxDuration: 60
};

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: '仅支持POST请求' });
  }

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    // 1. 解析上传的PPT
    const chunks = [];
    for await (const chunk of req) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);

    const rawSlides = await parsePPTX(buffer);
    const slides = rawSlides.map(slide => ({
      title: slide.title?.trim() || '',
      bullets: (slide.bullets || []).map(b => b.trim()).filter(b => b),
      paragraphs: (slide.paragraphs || []).map(p => p.trim()).filter(p => p)
    }));

    // 2. 初始化FFmpeg
    const ffmpeg = new FFmpeg();
    const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.0/dist/umd';
    await ffmpeg.load({
      coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
      wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
    });

    // 3. 逐页生成语音和视频
    const slideNames = [];
    for (let i = 0; i < slides.length; i++) {
      // 生成语音
      const textParts = [slides[i].title, ...slides[i].bullets, ...slides[i].paragraphs];
      const text = textParts.filter(t => t).join('。') + '。';
      
      const communicate = new edgeTts.Communicate(text, 'zh-CN-XiaoxiaoNeural', {
        rate: '1.0',
        volume: '1.0'
      });

      const audioChunks = [];
      for await (const chunk of communicate.stream()) {
        if (chunk.type === 'audio') {
          audioChunks.push(chunk.data);
        }
      }
      const audioBuffer = Buffer.concat(audioChunks);
      const audioName = `audio_${i}.mp3`;
      await ffmpeg.writeFile(audioName, new Uint8Array(audioBuffer));

      // 获取语音时长
      const { stdout } = await ffmpeg.exec([
        '-i', audioName, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1'
      ]);
      const duration = parseFloat(stdout) + 0.5;

      // 生成视频画面
      const filters = [];
      filters.push(`color=c=#f5f5f5:s=1920x1080:d=${duration}[bg]`);
      filters.push("[bg]drawbox=x=100:y=80:w=180:h=50:color=#ff9800:t=fill[bg1]");
      filters.push(
        "[bg1]drawtext=text='知识要点':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=40:fontcolor=white:x=140:y=92[v0]"
      );

      let current = 'v0';
      let layerNum = 1;
      const title = slides[i].title || `第${i+1}页`;

      filters.push(
        `[${current}]drawtext=text='${title}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=72:fontcolor=#1a1a1a:x=(w-text_w)/2:y=200[v${layerNum}]`
      );
      current = `v${layerNum++}`;

      filters.push(`[${current}]drawbox=x=200:y=350:w=1520:h=600:color=white:t=fill[v${layerNum}]`);
      current = `v${layerNum++}`;
      filters.push(`[${current}]drawbox=x=200:y=350:w=1520:h=600:color=#e0e0e0:t=2[v${layerNum}]`);
      current = `v${layerNum++}`;

      if (slides[i].paragraphs.length > 0) {
        const text = slides[i].paragraphs[0].substring(0, 300);
        const lines = text.match(/.{1,24}/g) || [];
        let y = 400;
        for (let j = 0; j < Math.min(lines.length, 12); j++) {
          filters.push(
            `[${current}]drawtext=text='${lines[j]}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=32:fontcolor=#444444:x=250:y=${y}[v${layerNum}]`
          );
          current = `v${layerNum++}`;
          y += 50;
        }
      }

      const filterComplex = filters.join(';');
      const outputName = `slide_${i}.mp4`;

      await ffmpeg.exec([
        '-i', audioName, '-filter_complex', filterComplex,
        '-map', `[${current}]`, '-map', '0:a',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-t', duration.toString(),
        '-shortest', outputName
      ]);

      slideNames.push(outputName);
    }

    // 4. 合并所有视频
    const concatContent = slideNames.map(name => `file '${name}'`).join('\n');
    await ffmpeg.writeFile('concat.txt', concatContent);

    await ffmpeg.exec([
      '-f', 'concat', '-safe', '0', '-i', 'concat.txt',
      '-c', 'copy', 'output.mp4'
    ]);

    // 5. 返回生成的视频
    const data = await ffmpeg.readFile('output.mp4');
    
    res.setHeader('Content-Type', 'video/mp4');
    res.setHeader('Content-Length', data.length);
    res.send(Buffer.from(data.buffer));

  } catch (error) {
    console.error('生成错误:', error);
    res.status(500).json({ error: error.message });
  }
}
