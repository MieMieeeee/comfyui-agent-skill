"""Generate comfyui-agent-skill-mie decision tree SVG (Dark Terminal style)."""
import os

lines = []
W, H = 960, 2200

lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
lines.append('  <style>')
lines.append('    text { font-family: "SF Mono","Fira Code","Cascadia Code","Courier New","Microsoft YaHei","SimHei",monospace; fill:#e2e8f0; }')
lines.append('    .title{font-size:18px;font-weight:700;fill:#a855f7}')
lines.append('    .section{font-size:14px;font-weight:700;fill:#3b82f6}')
lines.append('    .label{font-size:12px;fill:#e2e8f0}')
lines.append('    .sub{font-size:10px;fill:#94a3b8}')
lines.append('    .error{font-size:11px;fill:#ef4444}')
lines.append('    .ok{font-size:11px;fill:#10b981}')
lines.append('    .al{font-size:10px;fill:#94a3b8}')
lines.append('  </style>')
lines.append('  <defs>')
lines.append('    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0f0f1a"/><stop offset="100%" stop-color="#1a1a2e"/></linearGradient>')
lines.append('    <marker id="ap" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#a855f7"/></marker>')
lines.append('    <marker id="ab" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#3b82f6"/></marker>')
lines.append('    <marker id="ag" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#10b981"/></marker>')
lines.append('    <marker id="ao" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#f97316"/></marker>')
lines.append('    <marker id="ar" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#ef4444"/></marker>')
lines.append('    <marker id="ay" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#eab308"/></marker>')
lines.append('    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
lines.append('  </defs>')
lines.append(f'  <rect width="{W}" height="{H}" fill="url(#bg)"/>')

# ═══════════════ TITLE ═══════════════
lines.append('  <text x="480" y="40" text-anchor="middle" class="title">comfyui-agent-skill-mie 决策树</text>')
lines.append('  <text x="480" y="58" text-anchor="middle" class="sub">Agent Skill for ComfyUI Workflows — Decision Flowchart</text>')

# ═══════════════ §1 用户意图路由 ═══════════════
s1 = 80
lines.append(f'  <rect x="20" y="{s1}" width="920" height="480" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s1+22}" class="section">§ 1  用户意图 → 工作流选择</text>')

# Entry
ey = s1+50
lines.append(f'  <rect x="370" y="{ey}" width="220" height="36" rx="18" fill="#1e1b4b" stroke="#7c3aed" stroke-width="1.5" filter="url(#glow)"/>')
lines.append(f'  <text x="480" y="{ey+23}" text-anchor="middle" class="label">用户请求到达</text>')

# Intent diamond
iy = ey+60
lines.append(f'  <polygon points="480,{iy} 580,{iy+40} 480,{iy+80} 380,{iy+40}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{iy+35}" text-anchor="middle" class="label">解析意图</text>')
lines.append(f'  <line x1="480" y1="{ey+36}" x2="480" y2="{iy}" stroke="#a855f7" stroke-width="1.5" marker-end="url(#ap)"/>')

# Workflow branches
bx = iy+80
branches = [
    # (x1_from, y1_from, x_to, y_to_label, text, fill, stroke, label_above)
    (380, iy+40, 160, bx+20, "z_image_turbo (默认)", "#052e16", "#10b981", "文本→图片"),
    (410, iy+60, 290, bx+20, "qwen_image (海报/文字)", "#052e16", "#10b981", None),
    (480, iy+80, 480, bx+10, "Vision→prompt→T2I", "#1e1b4b", "#a855f7", None),
    (510, iy+60, 650, bx+20, "klein_edit (编辑图)", "#1c1917", "#f97316", None),
    (540, iy+40, 810, bx+20, "ltx-23-t2v / i2v", "#052e16", "#10b981", "视频"),
]
for x1, y1, x2, y2, text, fill, stroke, above in branches:
    lines.append(f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1.5" marker-end="url(#ab)"/>')
    if above:
        mx, my = (x1+x2)//2, (y1+y2)//2 - 5
        lines.append(f'  <text x="{mx}" y="{my}" text-anchor="middle" class="al">{above}</text>')
    lines.append(f'  <rect x="{x2-95}" y="{y2-10}" width="190" height="30" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    lines.append(f'  <text x="{x2}" y="{y2+10}" text-anchor="middle" class="ok">{text}</text>')

# Row 2
bx2 = bx+55
lines.append(f'  <line x1="430" y1="{iy+70}" x2="300" y2="{bx2+10}" stroke="#3b82f6" stroke-width="1.5" marker-end="url(#ab)"/>')
lines.append(f'  <rect x="190" y="{bx2}" width="220" height="30" rx="6" fill="#052e16" stroke="#10b981" stroke-width="1.5"/>')
lines.append(f'  <text x="300" y="{bx2+19}" text-anchor="middle" class="ok">ace_step_15_music (音乐)</text>')

lines.append(f'  <line x1="530" y1="{iy+70}" x2="680" y2="{bx2+10}" stroke="#3b82f6" stroke-width="1.5" marker-end="url(#ab)"/>')
lines.append(f'  <rect x="560" y="{bx2}" width="240" height="30" rx="6" fill="#052e16" stroke="#10b981" stroke-width="1.5"/>')
lines.append(f'  <text x="680" y="{bx2+19}" text-anchor="middle" class="ok">qwen3_tts (语音合成)</text>')

# Prompt Enhancement
pe_y = bx2+55
lines.append(f'  <rect x="180" y="{pe_y}" width="600" height="120" rx="8" fill="#0f172a" stroke="#eab308" stroke-dasharray="5,3"/>')
lines.append(f'  <text x="480" y="{pe_y+18}" text-anchor="middle" class="label" fill="#eab308">Prompt Enhancement (Agent 侧预处理)</text>')

pe_items = [
    ("character.md", "人物/角色/肖像", 110),
    ("reference_to_image.md", "参考图→新图", 310),
    ("image_to_image.md", "编辑图片+--image", 510),
    ("text_to_speech.md", "语音合成拆参", 720),
]
for name, desc, x in pe_items:
    lines.append(f'  <rect x="{x-70}" y="{pe_y+30}" width="160" height="38" rx="6" fill="#1e1b4b" stroke="#7c3aed" stroke-width="1"/>')
    lines.append(f'  <text x="{x+10}" y="{pe_y+45}" text-anchor="middle" class="sub" fill="#a855f7">{name}</text>')
    lines.append(f'  <text x="{x+10}" y="{pe_y+60}" text-anchor="middle" class="sub">{desc}</text>')

# Error gates
err_items = [("NO_REFERENCE_IMAGE", 325), ("VISION_UNAVAILABLE", 500), ("NO_INPUT_IMAGE", 675)]
for code, x in err_items:
    lines.append(f'  <rect x="{x-70}" y="{pe_y+78}" width="140" height="20" rx="4" fill="#450a0a" stroke="#ef4444"/>')
    lines.append(f'  <text x="{x}" y="{pe_y+92}" text-anchor="middle" class="error">{code}</text>')

# ═══════════════ §2 CLI子命令路由 ═══════════════
s2 = s1+500
lines.append(f'  <rect x="20" y="{s2}" width="920" height="200" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s2+22}" class="section">§ 2  CLI 子命令路由 — cli.py</text>')

cy = s2+42
lines.append(f'  <rect x="330" y="{cy}" width="300" height="32" rx="16" fill="#1e1b4b" stroke="#7c3aed" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{cy+21}" text-anchor="middle" class="label">comfyui-skill / python -m comfyui</text>')

sy = cy+55
cmds = [("generate","#3b82f6",120),("check","#10b981",280),("doctor","#10b981",400),
        ("validate","#10b981",520),("save-server","#eab308",660),("import-workflow","#eab308",810)]
for name, color, x in cmds:
    lines.append(f'  <rect x="{x-45}" y="{sy}" width="100" height="26" rx="6" fill="#0f172a" stroke="{color}" stroke-width="1.5"/>')
    lines.append(f'  <text x="{x+5}" y="{sy+17}" text-anchor="middle" class="sub" fill="{color}">{name}</text>')

lines.append(f'  <line x1="480" y1="{cy+32}" x2="480" y2="{sy}" stroke="#a855f7" stroke-width="1.5" marker-end="url(#ap)"/>')

# Default fallback
lines.append(f'  <rect x="30" y="{sy+35}" width="160" height="22" rx="4" fill="#1c1917" stroke="#f97316"/>')
lines.append(f'  <text x="110" y="{sy+50}" text-anchor="middle" class="sub" fill="#f97316">无参数/以-开头→generate</text>')
lines.append(f'  <line x1="190" y1="{sy+46}" x2="120" y2="{sy+13}" stroke="#f97316" stroke-width="1" marker-end="url(#ao)" stroke-dasharray="4,2"/>')

# Unknown
lines.append(f'  <rect x="770" y="{sy+35}" width="140" height="22" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="840" y="{sy+50}" text-anchor="middle" class="error">未知→报错退出</text>')
lines.append(f'  <line x1="810" y1="{sy+26}" x2="840" y2="{sy+35}" stroke="#ef4444" stroke-width="1" marker-end="url(#ar)" stroke-dasharray="4,2"/>')

# ═══════════════ §3 参数校验 ═══════════════
s3 = s2+220
lines.append(f'  <rect x="20" y="{s3}" width="920" height="340" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s3+22}" class="section">§ 3  Generate 参数校验链</text>')

ny = s3+42
lines.append(f'  <rect x="370" y="{ny}" width="220" height="32" rx="16" fill="#1e1b4b" stroke="#7c3aed" stroke-width="1.5" filter="url(#glow)"/>')
lines.append(f'  <text x="480" y="{ny+21}" text-anchor="middle" class="label">generate 命令入口</text>')
lines.append(f'  <line x1="480" y1="{ny+32}" x2="480" y2="{ny+55}" stroke="#a855f7" stroke-width="1.5" marker-end="url(#ap)"/>')

# Diamond: workflow registered?
d1y = ny+55
lines.append(f'  <polygon points="480,{d1y} 560,{d1y+30} 480,{d1y+60} 400,{d1y+30}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{d1y+28}" text-anchor="middle" class="sub">已注册?</text>')

# No → error
lines.append(f'  <line x1="560" y1="{d1y+30}" x2="720" y2="{d1y+15}" stroke="#ef4444" stroke-width="1.5" marker-end="url(#ar)"/>')
lines.append(f'  <text x="620" y="{d1y+22}" text-anchor="middle" class="al">否</text>')
lines.append(f'  <rect x="720" y="{d1y+4}" width="180" height="22" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="810" y="{d1y+19}" text-anchor="middle" class="error">WORKFLOW_NOT_REGISTERED</text>')

# Yes → TTS check
d2y = d1y+70
lines.append(f'  <line x1="480" y1="{d1y+60}" x2="480" y2="{d2y}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <text x="492" y="{d1y+72}" class="al">是</text>')

lines.append(f'  <polygon points="480,{d2y} 560,{d2y+30} 480,{d2y+60} 400,{d2y+30}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{d2y+28}" text-anchor="middle" class="sub">TTS?</text>')

# TTS=Yes
lines.append(f'  <line x1="400" y1="{d2y+30}" x2="300" y2="{d2y+55}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <text x="340" y="{d2y+38}" class="al">是</text>')

d3y = d2y+55
lines.append(f'  <polygon points="300,{d3y} 380,{d3y+30} 300,{d3y+60} 220,{d3y+30}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="300" y="{d3y+28}" text-anchor="middle" class="sub">speech-text?</text>')

# No → error
lines.append(f'  <line x1="220" y1="{d3y+30}" x2="100" y2="{d3y+15}" stroke="#ef4444" stroke-width="1.5" marker-end="url(#ar)"/>')
lines.append(f'  <text x="155" y="{d3y+22}" class="al">否</text>')
lines.append(f'  <rect x="20" y="{d3y+4}" width="130" height="22" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="85" y="{d3y+19}" text-anchor="middle" class="error">缺少必要参数</text>')

# Yes → merge
lines.append(f'  <line x1="300" y1="{d3y+60}" x2="300" y2="{d3y+90}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <text x="312" y="{d3y+72}" class="al">是</text>')

# TTS=No → prompt check
lines.append(f'  <line x1="560" y1="{d2y+30}" x2="680" y2="{d3y}" stroke="#f97316" stroke-width="1.5" marker-end="url(#ao)"/>')
lines.append(f'  <text x="630" y="{d2y+38}" class="al">否</text>')

lines.append(f'  <polygon points="760,{d3y} 840,{d3y+30} 760,{d3y+60} 680,{d3y+30}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="760" y="{d3y+28}" text-anchor="middle" class="sub">有prompt?</text>')

lines.append(f'  <line x1="840" y1="{d3y+30}" x2="900" y2="{d3y+15}" stroke="#ef4444" stroke-width="1.5" marker-end="url(#ar)"/>')
lines.append(f'  <rect x="840" y="{d3y+4}" width="100" height="22" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="890" y="{d3y+19}" text-anchor="middle" class="error">EMPTY_PROMPT</text>')

# Yes → merge
lines.append(f'  <line x1="760" y1="{d3y+60}" x2="600" y2="{d3y+90}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')

# Merge: size check
lines.append(f'  <rect x="350" y="{d3y+90}" width="260" height="28" rx="6" fill="#0f172a" stroke="#eab308" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{d3y+109}" text-anchor="middle" class="label" fill="#eab308">校验 width/height 约束</text>')

# ═══════════════ §4 服务器 & Preflight ═══════════════
s4 = s3+360
lines.append(f'  <rect x="20" y="{s4}" width="920" height="380" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s4+22}" class="section">§ 4  服务器连接 &amp; 环境预检</text>')

svy = s4+42
lines.append(f'  <rect x="280" y="{svy}" width="400" height="28" rx="6" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{svy+19}" text-anchor="middle" class="label">解析 Server URL</text>')

# Priority chain
pry = svy+40
prio = [("--server",140),("ENV",310),("config.local.json",500),("127.0.0.1:8188",700)]
for i,(name,x) in enumerate(prio):
    lines.append(f'  <rect x="{x-60}" y="{pry}" width="130" height="22" rx="4" fill="#0f172a" stroke="#94a3b8"/>')
    lines.append(f'  <text x="{x+5}" y="{pry+15}" text-anchor="middle" class="sub">{name}</text>')
    if i < len(prio)-1:
        nx = prio[i+1][1]
        lines.append(f'  <line x1="{x+65}" y1="{pry+11}" x2="{nx-65}" y2="{pry+11}" stroke="#94a3b8" stroke-width="1" marker-end="url(#ab)" stroke-dasharray="4,2"/>')
lines.append(f'  <text x="480" y="{pry+32}" text-anchor="middle" class="sub">优先级: 左→右</text>')

# Health check
hcy = pry+45
lines.append(f'  <line x1="480" y1="{svy+28}" x2="480" y2="{hcy}" stroke="#a855f7" stroke-width="1.5" marker-end="url(#ap)"/>')
lines.append(f'  <polygon points="480,{hcy} 580,{hcy+35} 480,{hcy+70} 380,{hcy+35}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{hcy+25}" text-anchor="middle" class="sub">Health Check</text>')
lines.append(f'  <text x="480" y="{hcy+38}" text-anchor="middle" class="sub">GET /system_stats</text>')

lines.append(f'  <line x1="580" y1="{hcy+35}" x2="750" y2="{hcy+18}" stroke="#ef4444" stroke-width="1.5" marker-end="url(#ar)"/>')
lines.append(f'  <text x="650" y="{hcy+28}" class="al">不可达</text>')
lines.append(f'  <rect x="750" y="{hcy+7}" width="170" height="22" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="835" y="{hcy+22}" text-anchor="middle" class="error">SERVER_UNAVAILABLE</text>')

# Preflight
pfy = hcy+70
lines.append(f'  <line x1="480" y1="{hcy+70}" x2="480" y2="{pfy}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <text x="492" y="{hcy+82}" class="al">OK</text>')

lines.append(f'  <polygon points="480,{pfy} 580,{pfy+35} 480,{pfy+70} 380,{pfy+35}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{pfy+22}" text-anchor="middle" class="sub">Preflight</text>')
lines.append(f'  <text x="480" y="{pfy+38}" text-anchor="middle" class="sub">节点+模型+插件</text>')

lines.append(f'  <line x1="380" y1="{pfy+35}" x2="200" y2="{pfy+18}" stroke="#ef4444" stroke-width="1.5" marker-end="url(#ar)"/>')
lines.append(f'  <text x="280" y="{pfy+28}" class="al">缺失</text>')
lines.append(f'  <rect x="30" y="{pfy+3}" width="180" height="36" rx="4" fill="#450a0a" stroke="#ef4444"/>')
lines.append(f'  <text x="120" y="{pfy+17}" text-anchor="middle" class="error">PREFLIGHT_MISSING_</text>')
lines.append(f'  <text x="120" y="{pfy+31}" text-anchor="middle" class="error">NODES / MODELS</text>')

# Skip preflight
sky = pfy+70
lines.append(f'  <line x1="480" y1="{pfy+70}" x2="480" y2="{sky}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <polygon points="480,{sky} 580,{sky+35} 480,{sky+70} 380,{sky+35}" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{sky+25}" text-anchor="middle" class="sub">--skip-preflight?</text>')

lines.append(f'  <line x1="580" y1="{sky+35}" x2="750" y2="{sky+52}" stroke="#f97316" stroke-width="1.5" marker-end="url(#ao)"/>')
lines.append(f'  <text x="650" y="{sky+42}" class="al">是</text>')
lines.append(f'  <line x1="480" y1="{sky+70}" x2="480" y2="{sky+90}" stroke="#10b981" stroke-width="1.5" marker-end="url(#ag)"/>')
lines.append(f'  <text x="492" y="{sky+82}" class="al">否→执行</text>')

# ═══════════════ §5 执行引擎 ═══════════════
s5 = s4+400
lines.append(f'  <rect x="20" y="{s5}" width="920" height="350" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s5+22}" class="section">§ 5  执行引擎 &amp; 异步模式</text>')

amy = s5+42
lines.append(f'  <rect x="340" y="{amy}" width="280" height="32" rx="16" fill="#1e1b4b" stroke="#7c3aed" stroke-width="1.5" filter="url(#glow)"/>')
lines.append(f'  <text x="480" y="{amy+21}" text-anchor="middle" class="label">执行模式选择</text>')

bry = amy+55
# submit
lines.append(f'  <line x1="380" y1="{amy+32}" x2="160" y2="{bry}" stroke="#3b82f6" stroke-width="1.5" marker-end="url(#ab)"/>')
lines.append(f'  <text x="260" y="{amy+45}" class="al">--submit</text>')
lines.append(f'  <rect x="40" y="{bry}" width="240" height="55" rx="6" fill="#052e16" stroke="#10b981" stroke-width="1.5"/>')
lines.append(f'  <text x="160" y="{bry+18}" text-anchor="middle" class="ok">submitter.py</text>')
lines.append(f'  <text x="160" y="{bry+34}" text-anchor="middle" class="sub">验证→上传→排队→SQLite</text>')
lines.append(f'  <text x="160" y="{bry+48}" text-anchor="middle" class="ok">返回 job_id</text>')

# poll
lines.append(f'  <line x1="440" y1="{amy+32}" x2="380" y2="{bry}" stroke="#3b82f6" stroke-width="1.5" marker-end="url(#ab)"/>')
lines.append(f'  <text x="410" y="{amy+45}" class="al">--poll</text>')
lines.append(f'  <rect x="280" y="{bry}" width="200" height="55" rx="6" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="380" y="{bry+18}" text-anchor="middle" class="label">poller.py</text>')
lines.append(f'  <text x="380" y="{bry+34}" text-anchor="middle" class="sub">WS实时→HTTP回退</text>')
lines.append(f'  <text x="380" y="{bry+48}" text-anchor="middle" class="sub">下载完成输出</text>')

# poll-all
lines.append(f'  <line x1="520" y1="{amy+32}" x2="590" y2="{bry}" stroke="#3b82f6" stroke-width="1.5" marker-end="url(#ab)"/>')
lines.append(f'  <text x="560" y="{amy+45}" class="al">--poll-all</text>')
lines.append(f'  <rect x="500" y="{bry}" width="180" height="55" rx="6" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>')
lines.append(f'  <text x="590" y="{bry+18}" text-anchor="middle" class="label">轮询所有任务</text>')
lines.append(f'  <text x="590" y="{bry+34}" text-anchor="middle" class="sub">已提交/执行中</text>')

# sync → executor
lines.append(f'  <line x1="580" y1="{amy+32}" x2="810" y2="{bry}" stroke="#eab308" stroke-width="1.5" marker-end="url(#ay)"/>')
lines.append(f'  <text x="700" y="{amy+45}" class="al">同步(默认)</text>')
lines.append(f'  <rect x="720" y="{bry}" width="200" height="55" rx="6" fill="#1e1b4b" stroke="#a855f7" stroke-width="1.5" filter="url(#glow)"/>')
lines.append(f'  <text x="820" y="{bry+18}" text-anchor="middle" class="label">executor.py</text>')
lines.append(f'  <text x="820" y="{bry+34}" text-anchor="middle" class="sub">加载→注入→排队→WS等待</text>')
lines.append(f'  <text x="820" y="{bry+48}" text-anchor="middle" class="sub">→取结果→保存</text>')

# Executor detail
exy = bry+75
lines.append(f'  <rect x="620" y="{exy}" width="310" height="170" rx="8" fill="#0f172a" stroke="#7c3aed" stroke-dasharray="5,3"/>')
lines.append(f'  <text x="775" y="{exy+16}" text-anchor="middle" class="sub" fill="#a855f7">executor 详细流程</text>')
steps = ["1. 加载 workflow JSON","2. 创建 API 连接","3. 上传输入图片 (如有)","4. node_mapping 注入参数","5. 排队 prompt → WS 等待","6. history API 取结果","7. 保存到 results/YYYYMMDD/"]
for i,step in enumerate(steps):
    sy = exy+28+i*20
    lines.append(f'  <text x="640" y="{sy}" class="sub">{step}</text>')

# Node mapping
nmy = exy+70
lines.append(f'  <rect x="50" y="{nmy}" width="540" height="100" rx="8" fill="#0f172a" stroke="#eab308"/>')
lines.append(f'  <text x="320" y="{nmy+16}" text-anchor="middle" class="sub" fill="#eab308">Node Mapping — 核心抽象层</text>')
lines.append(f'  <text x="320" y="{nmy+30}" text-anchor="middle" class="sub">CLI 参数 → ComfyUI 工作流节点</text>')
maps = [("prompt→KSampler",80),("seed→KSampler",210),("w/h→latent",340),("image→LoadImage",470)]
for name,x in maps:
    lines.append(f'  <rect x="{x-15}" y="{nmy+40}" width="120" height="20" rx="3" fill="#1e1b4b" stroke="#7c3aed" stroke-width="0.8"/>')
    lines.append(f'  <text x="{x+45}" y="{nmy+54}" text-anchor="middle" class="sub">{name}</text>')

# ═══════════════ §6 输出 & 错误码 ═══════════════
s6 = s5+370
lines.append(f'  <rect x="20" y="{s6}" width="920" height="280" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s6+22}" class="section">§ 6  输出 &amp; 错误码速查</text>')

outy = s6+42
lines.append(f'  <rect x="330" y="{outy}" width="300" height="32" rx="6" fill="#052e16" stroke="#10b981" stroke-width="1.5"/>')
lines.append(f'  <text x="480" y="{outy+21}" text-anchor="middle" class="ok">JSON stdout + 文件 results/</text>')

oty = outy+45
otypes = [("image",".png",150,"#10b981"),("video",".mp4",350,"#3b82f6"),("audio",".mp3",550,"#a855f7"),("job_id","异步",750,"#eab308")]
for name,ext,x,color in otypes:
    lines.append(f'  <rect x="{x-55}" y="{oty}" width="120" height="24" rx="4" fill="#0f172a" stroke="{color}" stroke-width="1.5"/>')
    lines.append(f'  <text x="{x+5}" y="{oty+16}" text-anchor="middle" class="sub" fill="{color}">{name} {ext}</text>')

eey = oty+45
lines.append(f'  <text x="480" y="{eey}" text-anchor="middle" class="sub" fill="#ef4444">错误码速查</text>')
errs = [("SERVER_UNAVAILABLE","服务器不可达"),("WORKFLOW_NOT_REGISTERED","未注册"),("EMPTY_PROMPT","缺少prompt"),
        ("NO_REFERENCE_IMAGE","缺参考图"),("VISION_UNAVAILABLE","无Vision"),("NO_INPUT_IMAGE","缺输入图"),
        ("PREFLIGHT_MISSING_NODES","缺节点"),("PREFLIGHT_MISSING_MODELS","缺模型")]
for i,(code,desc) in enumerate(errs):
    col,row = i%2, i//2
    ex = 80+col*450
    ey = eey+15+row*26
    lines.append(f'  <rect x="{ex}" y="{ey}" width="200" height="20" rx="3" fill="#450a0a" stroke="#ef4444" stroke-width="0.8"/>')
    lines.append(f'  <text x="{ex+6}" y="{ey+14}" class="error" font-size="9">{code}</text>')
    lines.append(f'  <text x="{ex+210}" y="{ey+14}" class="sub" font-size="9">{desc}</text>')

# ═══════════════ §7 数据流全景 ═══════════════
s7 = s6+300
lines.append(f'  <rect x="20" y="{s7}" width="920" height="90" rx="8" fill="#0f172a" stroke="#334155"/>')
lines.append(f'  <text x="40" y="{s7+22}" class="section">§ 7  数据流全景</text>')

fly = s7+50
fnodes = [("用户",80,"#7c3aed"),("AI Agent",230,"#3b82f6"),("SKILL.md",380,"#eab308"),
          ("CLI",530,"#a855f7"),("ComfyUI",680,"#f97316"),("results/",830,"#10b981")]
for name,x,color in fnodes:
    lines.append(f'  <rect x="{x-50}" y="{fly}" width="110" height="30" rx="6" fill="#0f172a" stroke="{color}" stroke-width="1.5"/>')
    lines.append(f'  <text x="{x+5}" y="{fly+19}" text-anchor="middle" class="sub" fill="{color}">{name}</text>')

for i in range(len(fnodes)-1):
    x1 = fnodes[i][1]+60
    x2 = fnodes[i+1][1]-55
    lines.append(f'  <line x1="{x1}" y1="{fly+15}" x2="{x2}" y2="{fly+15}" stroke="{fnodes[i][2]}" stroke-width="1.5" marker-end="url(#ab)"/>')

# Footer
lines.append(f'  <text x="480" y="{H-15}" text-anchor="middle" class="sub">Generated by fireworks-tech-graph | Style 2: Dark Terminal | comfyui-agent-skill-mie v0.1.5</text>')
lines.append('</svg>')

svg = '\n'.join(lines)
out = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'decision-tree.svg')
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    f.write(svg)
print(f"SVG: {out} ({len(svg)} bytes)")
