import os
import json
import base64
import subprocess
from pathlib import Path
import tempfile

# === 你的 Python 脚本（适配 Vercel Linux） ===
PPT_TO_VIDEO_CODE = r"""
#!/usr/bin/env python3
import json
import subprocess
import sys
import re
from pathlib import Path

class VideoConfig:
    def __init__(self):
        self.subtitle_font_size = 75
        self.subtitle_margin_lr = 100
        self.subtitle_margin_v = 40
        self.video_font_size_title = 28
        self.video_font_size_content = 32

def probe_duration(audio_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(audio_path)],
            capture_output=True, text=True, check=True
        )
        return float(json.loads(result.stdout)["duration"])
    except:
        return 3.0

def escape_text(text):
    return text.replace("'", "'\\\\\\''").replace(":", "\\:")

def split_text(text, max_chars):
    if len(text) <= max_chars:
        return [text]
    lines = []
    current = ""
    for char in text:
        if len(current) >= max_chars:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines

def split_into_sentences(text):
    sentences = re.split(r'([。！？])', text)
    result = []
    for i in range(0, len(sentences)-1, 2):
        if sentences[i].strip():
            result.append(sentences[i] + (sentences[i+1] if i+1 < len(sentences) else ''))
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        result.append(sentences[-1])
    return [s.strip() for s in result if s.strip()]

def choose_layout(slide_data):
    bullets = slide_data.get('bullets', [])
    paragraphs = slide_data.get('paragraphs', [])
    if len(bullets) >= 3:
        return 'three_column'
    elif len(paragraphs) > 0 and len(paragraphs[0]) > 100:
        return 'three_column'
    elif len(bullets) == 2 or len(paragraphs) == 2:
        return 'two_column'
    else:
        return 'single_column'

def generate_base_layout(duration, slide_num):
    filters = []
    filters.append(f"color=c=#f5f5f5:s=1920x1080:d={duration}[bg]")
    filters.append("[bg]drawbox=x=100:y=80:w=180:h=50:color=#ff9800:t=fill[bg1]")
    filters.append(
        "[bg1]drawtext=text='知识要点':"
        "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=40:fontcolor=white:"
        "x=140:y=92[v0]"
    )
    return filters, "v0", 1

def layout_three_column(filters, current, layer_num, slide_data, slide_num):
    title = slide_data.get('title', f'第{slide_num}页')
    bullets = slide_data.get('bullets', [])
    paragraphs = slide_data.get('paragraphs', [])
    title_esc = escape_text(title)
    filters.append(
        f"[{current}]drawtext=text='{title_esc}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=64:fontcolor=#1a1a1a:"
        f"x=100:y=160[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    filters.append(
        f"[{current}]drawtext=text='重点看这几个维度。':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=32:fontcolor=#444444:"
        f"x=100:y=250[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    if bullets and len(bullets) >= 3:
        contents = bullets[:3]
    elif paragraphs:
        sentences = split_into_sentences(paragraphs[0])
        if len(sentences) >= 3:
            per_card = len(sentences) // 3;
            contents = [
                ''.join(sentences[:per_card]),
                ''.join(sentences[per_card:per_card*2]),
                ''.join(sentences[per_card*2:])
            ]
        elif len(sentences) == 2:
            contents = [sentences[0], sentences[1], ""]
        elif len(sentences) == 1:
            contents = [sentences[0], "", ""]
        else:
            contents = ["", "", ""]
    else:
        contents = ["", "", ""]
    for i in range(3):
        card_x = 100 + i * 580
        card_y = 350
        filters.append(
            f"[{current}]drawbox=x={card_x}:y={card_y}:w=520:h=600:color=white:t=fill[v{layer_num}]"
        )
        current = f"v{layer_num}"
        layer_num += 1
        filters.append(
            f"[{current}]drawbox=x={card_x}:y={card_y}:w=520:h=600:color=#e0e0e0:t=2[v{layer_num}]"
        )
        current = f"v{layer_num}"
        layer_num += 1
        filters.append(
            f"[{current}]drawtext=text='0{i+1}':"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=48:fontcolor=#2196f3:"
            f"x={card_x+30}:y={card_y+30}[v{layer_num}]"
        )
        current = f"v{layer_num}"
        layer_num += 1
        if i < len(contents) and contents[i]:
            lines = split_text(contents[i][:150], 12)
            y = card_y + 110
            for line in lines[:12]:
                line_esc = escape_text(line)
                filters.append(
                    f"[{current}]drawtext=text='{line_esc}':"
                    f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=32:fontcolor=#444444:"
                    f"x={card_x+30}:y={y}[v{layer_num}]"
                )
                current = f"v{layer_num}"
                layer_num += 1
                y += 45
    return filters, current, layer_num

def layout_two_column(filters, current, layer_num, slide_data, slide_num):
    title = slide_data.get('title', f'第{slide_num}页')
    bullets = slide_data.get('bullets', [])
    paragraphs = slide_data.get('paragraphs', [])
    title_esc = escape_text(title)
    filters.append(
        f"[{current}]drawtext=text='{title_esc}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=64:fontcolor=#1a1a1a:"
        f"x=100:y=160[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    if bullets and len(bullets) >= 2:
        contents = bullets[:2]
    elif paragraphs and len(paragraphs) >= 2:
        contents = paragraphs[:2]
    elif paragraphs:
        para = paragraphs[0]
        mid = len(para) // 2
        contents = [para[:mid], para[mid:]]
    else:
        contents = ["", ""]
    for i in range(2):
        card_x = 150 + i * 900
        card_y = 300
        filters.append(
            f"[{current}]drawbox=x={card_x}:y={card_y}:w=820:h=650:color=white:t=fill[v{layer_num}]"
        )
        current = f"v{layer_num}"
        layer_num += 1
        filters.append(
            f"[{current}]drawbox=x={card_x}:y={card_y}:w=820:h=650:color=#e0e0e0:t=2[v{layer_num}]"
        )
        current = f"v{layer_num}"
        layer_num += 1
        if i < len(contents) and contents[i]:
            lines = split_text(contents[i][:200], 18)
            y = card_y + 50
            for line in lines[:14]:
                line_esc = escape_text(line)
                filters.append(
                    f"[{current}]drawtext=text='{line_esc}':"
                    f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=28:fontcolor=#444444:"
                    f"x={card_x+40}:y={y}[v{layer_num}]"
                )
                current = f"v{layer_num}"
                layer_num += 1
                y += 45
    return filters, current, layer_num

def layout_single_column(filters, current, layer_num, slide_data, slide_num):
    title = slide_data.get('title', f'第{slide_num}页')
    paragraphs = slide_data.get('paragraphs', [])
    title_esc = escape_text(title)
    filters.append(
        f"[{current}]drawtext=text='{title_esc}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=72:fontcolor=#1a1a1a:"
        f"x=(w-text_w)/2:y=200[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    filters.append(
        f"[{current}]drawbox=x=200:y=350:w=1520:h=600:color=white:t=fill[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    filters.append(
        f"[{current}]drawbox=x=200:y=350:w=1520:h=600:color=#e0e0e0:t=2[v{layer_num}]"
    )
    current = f"v{layer_num}"
    layer_num += 1
    if paragraphs:
        lines = split_text(paragraphs[0][:300], 24)
        y = 400
        for line in lines[:12]:
            line_esc = escape_text(line)
            filters.append(
                f"[{current}]drawtext=text='{line_esc}':"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=32:fontcolor=#444444:"
                f"x=250:y={y}[v{layer_num}]"
            )
            current = f"v{layer_num}"
            layer_num += 1
            y += 50
    return filters, current, layer_num

def generate_slide(slide_data, audio_path, output_path, duration, slide_num):
    layout_type = choose_layout(slide_data)
    filters, current, layer_num = generate_base_layout(duration, slide_num)
    if layout_type == 'three_column':
        filters, current, layer_num = layout_three_column(filters, current, layer_num, slide_data, slide_num)
    elif layout_type == 'two_column':
        filters, current, layer_num = layout_two_column(filters, current, layer_num, slide_data, slide_num)
    else:
        filters, current, layer_num = layout_single_column(filters, current, slide_data, slide_num)
    filter_complex = ";".join(filters)
    cmd = ["ffmpeg", "-y"]
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{current}]", "-map", "0:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration), "-shortest", str(output_path)
    ])
    subprocess.run(cmd, check=True, capture_output=True)
    return layout_type

def generate_ass_from_srt(srt_path, output_path, config):
    ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVuSans,{config.subtitle_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,{config.subtitle_margin_lr},{config.subtitle_margin_lr},{config.subtitle_margin_v},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    srt_content = srt_path.read_text(encoding='utf-8')
    lines = srt_content.strip().split('\\n\\n')
    ass_events = []
    for block in lines:
        parts = block.split('\\n', 2)
        if len(parts) < 3:
            continue
        timestamp_line = parts[1]
        if '-->' not in timestamp_line:
            continue
        start, end = timestamp_line.split('-->')
        start = start.strip().replace(',', '.')[:-1]
        end = end.strip().replace(',', '.')[:-1]
        text = parts[2].replace('\\n', '\\N')
        ass_events.append(f"Dialogue: 0,{start},{end},Default,,0,0,,{text}")
    ass_content = ass_header + '\\n'.join(ass_events)
    output_path.write_text(ass_content, encoding='utf-8')

def burn_subtitles(video_path, ass_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path.name,
        "-vf", f"ass={ass_path.name}",
        "-c:a", "copy", output_path.name
    ], cwd=str(video_path.parent), check=True)

def main():
    if len(sys.argv) < 2:
        print("用法: python3 ppt_to_video.py <项目路径>")
        sys.exit(1)
    project = Path(sys.argv[1])
    config = VideoConfig()
    structure_file = project / "slide_structure.json"
    audio_dir = project / "audio"
    temp_dir = project / "temp_video"
    exports_dir = project / "exports"
    temp_dir.mkdir(exist_ok=True)
    exports_dir.mkdir(exist_ok=True)
    with open(structure_file, "r", encoding="utf-8") as f:
        slides = json.load(f)
    print(f"生成视频: {len(slides)} 页")
    segments = []
    for i, slide in enumerate(slides, 1):
        audio = audio_dir / f"page_{i:02d}.mp3"
        duration = probe_duration(audio) + 0.5 if audio.exists() else 5.0
        segment = temp_dir / f"seg_{i:03d}.mp4"
        generate_slide(slide, audio, segment, duration, i)
        segments.append(segment)
    concat_file = temp_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.name}'\\n")
    video_output = exports_dir / "final.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "concat.txt", "-c", "copy", str(video_output)
    ], cwd=str(temp_dir), check=True)
    print("完成")

if __name__ == "__main__":
    main()
"""

# === 把脚本写入临时文件 ===
def write_py_script():
    with open("/tmp/ppt_to_video.py", "w", encoding="utf-8") as f:
        f.write(PPT_TO_VIDEO_CODE)

# === 简单解析PPT结构 ===
def make_demo_structure():
    return [
        {"title":"第一页标题","paragraphs":["第一句话。第二句话。"]},
        {"title":"第二页标题","paragraphs":["第三句话。"]}
    ]

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        try:
            # 1. 写py脚本
            write_py_script()

            # 2. 读上传PPT
            content_length = int(self.headers.get("Content-Length", 0))
            ppt_bytes = self.rfile.read(content_length)

            # 3. 建临时项目目录
            tmp_root = tempfile.mkdtemp()
            project = Path(tmp_root)
            (project / "audio").mkdir(exist_ok=True)
            (project / "temp_video").mkdir(exist_ok=True)
            (project / "exports").mkdir(exist_ok=True)

            # 4. 写模拟结构
            structure = make_demo_structure()
            (project / "slide_structure.json").write_text(
                json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # 5. 运行py脚本
            subprocess.run(
                ["python3", "/tmp/ppt_to_video.py", str(project)],
                check=True, timeout=90
            )

            # 6. 读生成视频
            video_path = project / "exports" / "final.mp4"
            with open(video_path, "rb") as f:
                b64 = base64.encodebytes(f.read()).decode()

            self.wfile.write(json.dumps({"video": b64}).encode())

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
